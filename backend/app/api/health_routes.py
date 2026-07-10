from flask import Blueprint, jsonify, Response
import time
import logging
import json
from functools import wraps

logger = logging.getLogger(__name__)

health = Blueprint("health", __name__)


def timed_check(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            response = func(*args, **kwargs)
            elapsed_ms = round((time.time() - start_time) * 1000, 2)

            if isinstance(response, tuple):
                resp_data, status_code = response
                if isinstance(resp_data, dict):
                    resp_data["response_time_ms"] = elapsed_ms
                    return jsonify(resp_data), status_code
                elif isinstance(resp_data, Response):
                    try:
                        data = json.loads(resp_data.get_data(as_text=True))
                        data["response_time_ms"] = elapsed_ms
                        return jsonify(data), status_code
                    except (json.JSONDecodeError, ValueError):
                        pass
                return response

            if isinstance(response, dict):
                response["response_time_ms"] = elapsed_ms
                return jsonify(response)

            if isinstance(response, Response):
                try:
                    data = json.loads(response.get_data(as_text=True))
                    data["response_time_ms"] = elapsed_ms
                    return jsonify(data), response.status_code
                except (json.JSONDecodeError, ValueError):
                    return response

            return response
        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return jsonify({"status": "error", "error": str(e), "response_time_ms": elapsed_ms})
    return wrapper


def check_database():
    try:
        from app.api import get_services
        vector_store, rag_engine, db, dm_vector_store, dm_rag_engine, dm_db = get_services()

        if db is None:
            return {"status": "down", "message": "Database not initialized"}

        db.session.execute("SELECT 1")
        return {"status": "healthy", "message": "Database connection OK"}
    except Exception as e:
        logger.error("Database health check failed: %s", str(e))
        return {"status": "down", "message": str(e)}


def check_redis():
    try:
        from app.services.redis_cache import get_redis_cache

        cache = get_redis_cache()
        is_fallback = cache.is_fallback_mode()
        stats = cache.get_stats()

        if is_fallback:
            return {
                "status": "degraded",
                "message": "Redis unavailable, using memory fallback",
                "mode": "memory_fallback",
            }

        return {
            "status": "healthy",
            "message": "Redis connection OK",
            "mode": "redis",
            "connected_clients": stats.get("connected_clients", 0),
            "used_memory": stats.get("used_memory_human", "unknown"),
        }
    except Exception as e:
        logger.error("Redis health check failed: %s", str(e))
        return {"status": "down", "message": str(e)}


def check_llm_api():
    try:
        from app.api import get_services
        from app.services.llm_provider import LLMProviderWithFallback

        vector_store, rag_engine, db, dm_vector_store, dm_rag_engine, dm_db = get_services()

        if rag_engine is None or rag_engine.provider is None:
            return {"status": "down", "message": "LLM provider not initialized"}

        provider = rag_engine.provider
        if isinstance(provider, LLMProviderWithFallback):
            primary_healthy = provider.primary.health_check()
            fallbacks_healthy = [fb.health_check() for fb in provider.fallbacks]

            if primary_healthy:
                return {"status": "healthy", "message": "Primary LLM available"}
            elif any(fallbacks_healthy):
                return {"status": "degraded", "message": "Primary LLM down, fallback available"}
            else:
                return {"status": "down", "message": "All LLM providers unavailable"}
        else:
            healthy = provider.health_check()
            if healthy:
                return {"status": "healthy", "message": "LLM API available"}
            else:
                return {"status": "down", "message": "LLM API health check failed"}
    except Exception as e:
        logger.error("LLM API health check failed: %s", str(e))
        return {"status": "down", "message": str(e)}


def check_vector_search():
    try:
        from app.api import get_services

        vector_store, rag_engine, db, dm_vector_store, dm_rag_engine, dm_db = get_services()

        if vector_store is None:
            return {"status": "down", "message": "Vector store not initialized"}

        results = vector_store.search("test", n_results=1)
        return {"status": "healthy", "message": "Vector search operational"}
    except Exception as e:
        logger.error("Vector search health check failed: %s", str(e))
        return {"status": "down", "message": str(e)}


@health.route("/health", methods=["GET"])
@timed_check
def health_check():
    components = {}
    for name, check_fn in [
        ("database", check_database),
        ("redis", check_redis),
        ("llm_api", check_llm_api),
        ("vector_search", check_vector_search),
    ]:
        try:
            components[name] = check_fn()
        except Exception as e:
            components[name] = {"status": "error", "message": str(e)}

    statuses = [c["status"] for c in components.values()]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "down" for s in statuses):
        overall = "degraded"
    else:
        overall = "degraded"

    return jsonify({
        "status": overall,
        "components": components,
        "timestamp": time.time(),
    })


@health.route("/health/ready", methods=["GET"])
@timed_check
def readiness_check():
    components = {}
    for name, check_fn in [
        ("database", check_database),
        ("redis", check_redis),
        ("llm_api", check_llm_api),
        ("vector_search", check_vector_search),
    ]:
        try:
            components[name] = check_fn()
        except Exception as e:
            components[name] = {"status": "error", "message": str(e)}

    all_ready = all(c["status"] in ("healthy", "degraded") for c in components.values())

    if not all_ready:
        return jsonify({
            "ready": False,
            "components": components,
            "timestamp": time.time(),
        }), 503

    return jsonify({
        "ready": True,
        "components": components,
        "timestamp": time.time(),
    })


@health.route("/health/live", methods=["GET"])
@timed_check
def liveness_check():
    try:
        from app.api import get_services

        vector_store, rag_engine, db, dm_vector_store, dm_rag_engine, dm_db = get_services()

        app_alive = True

        return jsonify({
            "alive": app_alive,
            "timestamp": time.time(),
        })
    except Exception as e:
        return jsonify({
            "alive": False,
            "error": str(e),
            "timestamp": time.time(),
        }), 503
