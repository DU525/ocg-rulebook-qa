"""定时监控调度模块 - 基于 APScheduler 的后台监控调度器

功能:
- 健康检查 (每5分钟)
- 指标采集 (每15分钟)
- 告警检测 (每30分钟)
- 数据清理 (每天凌晨2点)
- 管理 API 接口

配置项 (.env):
- MONITORING_ENABLED=true/false          总开关
- MONITORING_HEALTH_CHECK_INTERVAL=5     健康检查间隔(分钟)
- MONITORING_METRICS_INTERVAL=15         指标采集间隔(分钟)
- MONITORING_ALERT_INTERVAL=30           告警检测间隔(分钟)
- MONITORING_CLEANUP_HOUR=2              数据清理执行小时(0-23)
- MONITORING_TASKS_ENABLED=health_check,metrics,alerts,cleanup  启用的任务列表
- MONITORING_SILENT=false                静默模式
- MONITORING_FRONTEND_URL=http://localhost:3011  前端服务地址
- MONITORING_BACKEND_URL=http://localhost:5000   后端服务地址
"""

import os
import uuid
import json
import time
import logging
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv
load_dotenv()

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None
_scheduler_lock = threading.Lock()
_monitoring_state: Dict[str, Any] = {
    "running": False,
    "started_at": None,
    "last_runs": {},
    "task_statuses": {},
    "metrics_cache": {},
}


class MonitoringConfig:
    """监控配置, 从 .env 读取"""

    ENABLED = os.environ.get("MONITORING_ENABLED", "true").lower() == "true"

    HEALTH_CHECK_INTERVAL = int(
        os.environ.get("MONITORING_HEALTH_CHECK_INTERVAL", "5")
    )
    METRICS_INTERVAL = int(os.environ.get("MONITORING_METRICS_INTERVAL", "15"))
    ALERT_INTERVAL = int(os.environ.get("MONITORING_ALERT_INTERVAL", "30"))
    CLEANUP_HOUR = int(os.environ.get("MONITORING_CLEANUP_HOUR", "2"))

    TASKS_ENABLED = os.environ.get(
        "MONITORING_TASKS_ENABLED", "health_check,metrics,alerts,cleanup"
    )
    TASKS_ENABLED_LIST = [t.strip() for t in TASKS_ENABLED.split(",")]

    SILENT = os.environ.get("MONITORING_SILENT", "false").lower() == "true"

    FRONTEND_URL = os.environ.get("MONITORING_FRONTEND_URL", "http://localhost:3011")
    BACKEND_URL = os.environ.get("MONITORING_BACKEND_URL", "http://localhost:5000")

    ALERT_QPS_THRESHOLD = int(os.environ.get("MONITORING_ALERT_QPS_THRESHOLD", "1000"))
    ALERT_P99_THRESHOLD = int(os.environ.get("MONITORING_ALERT_P99_THRESHOLD", "5"))
    ALERT_CACHE_HIT_THRESHOLD = float(
        os.environ.get("MONITORING_ALERT_CACHE_HIT_THRESHOLD", "0.5")
    )
    ALERT_FAITHFULNESS_THRESHOLD = float(
        os.environ.get("MONITORING_ALERT_FAITHFULNESS_THRESHOLD", "0.8")
    )

    @classmethod
    def is_task_enabled(cls, task_name: str) -> bool:
        return task_name in cls.TASKS_ENABLED_LIST


def _log(msg: str, level: int = logging.INFO) -> None:
    if MonitoringConfig.SILENT:
        return
    logger.log(level, msg)


def _get_db_session():
    try:
        from app.api.routes import db
        if db is not None:
            return db.get_session()
    except Exception:
        pass
    try:
        from app.api.dm_routes import dm_db
        if dm_db is not None:
            return dm_db.get_session()
    except Exception:
        pass
    return None


def _get_alert_model():
    try:
        from app.db.models import Alert
        return Alert
    except Exception:
        return None


def _record_alert(rule_type: str, message: str) -> None:
    Alert = _get_alert_model()
    if Alert is None:
        _log(f"[MONITOR] Alert model not available: {rule_type} - {message}")
        return
    session = _get_db_session()
    if session is None:
        _log(f"[MONITOR] DB session not available for alert: {rule_type}")
        return
    try:
        alert = Alert(
            id=str(uuid.uuid4()),
            rule_type=rule_type,
            message=message,
            created_at=datetime.utcnow(),
            is_read=0,
        )
        session.add(alert)
        session.commit()
        _log(f"[MONITOR] Alert recorded [{rule_type}]: {message}")
    except Exception as e:
        logger.error(f"[MONITOR] Failed to record alert: {e}")
    finally:
        session.close()


# ============================================================
# Task: Health Check
# ============================================================

def task_health_check() -> None:
    try:
        _log("[MONITOR][health_check] Starting health check...")
        results = {"backend": None, "frontend": None}

        backend_url = f"{MonitoringConfig.BACKEND_URL}/api/v1/health"
        try:
            resp = requests.get(backend_url, timeout=5)
            results["backend"] = {
                "status_code": resp.status_code,
                "healthy": resp.status_code == 200,
                "response_time_ms": int(resp.elapsed.total_seconds() * 1000),
                "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None,
            }
            _log(f"[MONITOR][health_check] Backend: {resp.status_code} ({results['backend']['response_time_ms']}ms)")
        except requests.RequestException as e:
            results["backend"] = {
                "status_code": 0,
                "healthy": False,
                "response_time_ms": 0,
                "error": str(e),
            }
            _log(f"[MONITOR][health_check] Backend FAILED: {e}", logging.WARNING)
            _record_alert("health_check", f"Backend health check failed: {e}")

        frontend_url = MonitoringConfig.FRONTEND_URL
        try:
            resp = requests.get(frontend_url, timeout=5)
            results["frontend"] = {
                "status_code": resp.status_code,
                "healthy": resp.status_code < 500,
                "response_time_ms": int(resp.elapsed.total_seconds() * 1000),
            }
            _log(f"[MONITOR][health_check] Frontend: {resp.status_code} ({results['frontend']['response_time_ms']}ms)")
        except requests.RequestException as e:
            results["frontend"] = {
                "status_code": 0,
                "healthy": False,
                "response_time_ms": 0,
                "error": str(e),
            }
            _log(f"[MONITOR][health_check] Frontend FAILED: {e}", logging.WARNING)
            _record_alert("health_check", f"Frontend health check failed: {e}")

        _monitoring_state["last_runs"]["health_check"] = {
            "time": datetime.utcnow().isoformat(),
            "results": results,
            "all_healthy": all(
                r.get("healthy", False) for r in results.values() if r is not None
            ),
        }
        _log("[MONITOR][health_check] Completed.")
    except Exception as e:
        logger.error(f"[MONITOR][health_check] Unexpected error: {e}")


# ============================================================
# Task: Metrics Collection
# ============================================================

def task_metrics_collection() -> None:
    try:
        _log("[MONITOR][metrics] Starting metrics collection...")
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "cache": {},
            "vector_search": {},
            "llm_latency": {},
            "ragas_evaluation": {},
        }

        _collect_cache_metrics(metrics)
        _collect_vector_search_metrics(metrics)
        _collect_llm_latency_metrics(metrics)
        _collect_ragas_metrics(metrics)

        _monitoring_state["metrics_cache"] = metrics
        _monitoring_state["last_runs"]["metrics"] = {
            "time": datetime.utcnow().isoformat(),
            "success": True,
        }
        _log(f"[MONITOR][metrics] Completed. Cache: {metrics['cache'].get('combined_hit_rate', 'N/A')}")
    except Exception as e:
        logger.error(f"[MONITOR][metrics] Unexpected error: {e}")
        _monitoring_state["last_runs"]["metrics"] = {
            "time": datetime.utcnow().isoformat(),
            "success": False,
            "error": str(e),
        }


def _collect_cache_metrics(metrics: Dict[str, Any]) -> None:
    try:
        from app.services.query_cache import get_l1_cache
        from app.services.vector_cache import get_query_cache

        l1_stats = get_l1_cache().get_stats()
        l2_stats = get_query_cache().get_stats()

        l1_hit_rate = l1_stats.get("hit_rate", 0.0)
        l2_hit_rate = l2_stats.get("hit_rate", 0.0)
        combined_rate = (l1_hit_rate + l2_hit_rate) / 2.0 if l1_hit_rate > 0 or l2_hit_rate > 0 else 0.0

        metrics["cache"] = {
            "l1": l1_stats,
            "l2": l2_stats,
            "combined_hit_rate": round(combined_rate, 4),
        }
        _log(f"[MONITOR][metrics] Cache L1 hit rate: {l1_hit_rate:.4f}, L2: {l2_hit_rate:.4f}")
    except Exception as e:
        logger.warning(f"[MONITOR][metrics] Cache collection failed: {e}")
        metrics["cache"] = {"error": str(e)}


def _collect_vector_search_metrics(metrics: Dict[str, Any]) -> None:
    try:
        from app.api.routes import db
        if db is None:
            return
        session = db.get_session()
        try:
            from app.db.models import PerformanceLog
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=1)
            logs = (
                session.query(PerformanceLog)
                .filter(PerformanceLog.created_at >= cutoff)
                .order_by(PerformanceLog.response_time_ms)
                .all()
            )
            if logs:
                times = [log.response_time_ms for log in logs]
                times_sorted = sorted(times)
                p50 = times_sorted[int(len(times_sorted) * 0.5)]
                p90 = times_sorted[int(len(times_sorted) * 0.9)]
                p99 = times_sorted[min(int(len(times_sorted) * 0.99), len(times_sorted) - 1)]
                avg = int(sum(times) / len(times))

                metrics["vector_search"] = {
                    "p50_ms": p50,
                    "p90_ms": p90,
                    "p99_ms": p99,
                    "avg_ms": avg,
                    "sample_count": len(times),
                    "period_minutes": 60,
                }
                _log(f"[MONITOR][metrics] Vector search p99: {p99}ms, avg: {avg}ms")
            else:
                metrics["vector_search"] = {"sample_count": 0, "period_minutes": 60}
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"[MONITOR][metrics] Vector search metrics failed: {e}")
        metrics["vector_search"] = {"error": str(e)}


def _collect_llm_latency_metrics(metrics: Dict[str, Any]) -> None:
    try:
        from app.api.routes import db
        if db is None:
            return
        session = db.get_session()
        try:
            from app.db.models import PerformanceLog
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=1)
            logs = (
                session.query(PerformanceLog)
                .filter(PerformanceLog.created_at >= cutoff)
                .filter(
                    PerformanceLog.endpoint.contains("/chat/")
                )
                .all()
            )
            if logs:
                times = [log.response_time_ms for log in logs]
                avg = int(sum(times) / len(times))
                metrics["llm_latency"] = {
                    "avg_ms": avg,
                    "min_ms": min(times),
                    "max_ms": max(times),
                    "sample_count": len(times),
                    "period_minutes": 60,
                }
                _log(f"[MONITOR][metrics] LLM latency avg: {avg}ms")
            else:
                metrics["llm_latency"] = {"sample_count": 0, "period_minutes": 60}
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"[MONITOR][metrics] LLM latency collection failed: {e}")
        metrics["llm_latency"] = {"error": str(e)}


def _collect_ragas_metrics(metrics: Dict[str, Any]) -> None:
    try:
        import os
        dataset_path = os.path.join(
            os.path.dirname(__file__),
            "../../tests/test_dataset.json",
        )
        if not os.path.exists(dataset_path):
            metrics["ragas_evaluation"] = {"error": "test_dataset.json not found"}
            return

        from tests.ragas_evaluator import RAGASEvaluator, RAGAS_AVAILABLE
        if not RAGAS_AVAILABLE:
            metrics["ragas_evaluation"] = {"error": "ragas not installed"}
            return

        from app.config import Config
        evaluator = RAGASEvaluator(
            llm_api_key=getattr(Config, "OPENAI_API_KEY", None),
            llm_api_base=getattr(Config, "OPENAI_API_BASE", None),
            llm_model=getattr(Config, "OPENAI_MODEL_NAME", "gpt-3.5-turbo"),
        )

        dataset = evaluator.load_test_dataset(dataset_path)
        sample_size = min(100, len(dataset))
        sample = dataset[:sample_size]

        results = evaluator.evaluate(sample, metrics=["faithfulness"], batch_size=10)
        metrics["ragas_evaluation"] = {
            "sample_size": sample_size,
            "total_dataset_size": len(dataset),
            "results": results,
        }
        _log(f"[MONITOR][metrics] RAGAS evaluation completed on {sample_size} samples")
    except Exception as e:
        logger.warning(f"[MONITOR][metrics] RAGAS evaluation failed: {e}")
        metrics["ragas_evaluation"] = {"error": str(e), "sample_size": 0}


# ============================================================
# Task: Alert Detection
# ============================================================

def task_alert_detection() -> None:
    try:
        _log("[MONITOR][alerts] Starting alert detection...")
        alerts_generated = 0

        alerts_generated += _check_qps_alert()
        alerts_generated += _check_p99_alert()
        alerts_generated += _check_cache_hit_rate_alert()
        alerts_generated += _check_faithfulness_alert()

        _monitoring_state["last_runs"]["alerts"] = {
            "time": datetime.utcnow().isoformat(),
            "alerts_generated": alerts_generated,
        }
        _log(f"[MONITOR][alerts] Completed. {alerts_generated} alert(s) generated.")
    except Exception as e:
        logger.error(f"[MONITOR][alerts] Unexpected error: {e}")


def _check_qps_alert() -> int:
    try:
        from app.api.routes import db
        if db is None:
            return 0
        session = db.get_session()
        try:
            from app.db.models import PerformanceLog
            now = datetime.utcnow()
            cutoff = now - timedelta(minutes=5)
            count = (
                session.query(PerformanceLog)
                .filter(PerformanceLog.created_at >= cutoff)
                .count()
            )
            qps = count / 300.0
            threshold = MonitoringConfig.ALERT_QPS_THRESHOLD
            if qps < threshold:
                _record_alert(
                    "performance",
                    f"QPS {qps:.2f} < threshold {threshold}",
                )
                return 1
            _log(f"[MONITOR][alerts] QPS: {qps:.2f} (threshold: {threshold})")
            return 0
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"[MONITOR][alerts] QPS check failed: {e}")
        return 0


def _check_p99_alert() -> int:
    metrics = _monitoring_state.get("metrics_cache", {})
    vector_search = metrics.get("vector_search", {})
    p99 = vector_search.get("p99_ms")
    if p99 is None:
        _log("[MONITOR][alerts] P99 data not available, skipping")
        return 0
    threshold = MonitoringConfig.ALERT_P99_THRESHOLD
    if p99 > threshold:
        _record_alert(
            "performance",
            f"p99 latency {p99}ms > threshold {threshold}ms",
        )
        return 1
    _log(f"[MONITOR][alerts] P99: {p99}ms (threshold: {threshold}ms)")
    return 0


def _check_cache_hit_rate_alert() -> int:
    metrics = _monitoring_state.get("metrics_cache", {})
    cache = metrics.get("cache", {})
    hit_rate = cache.get("combined_hit_rate")
    if hit_rate is None:
        _log("[MONITOR][alerts] Cache hit rate data not available, skipping")
        return 0
    threshold = MonitoringConfig.ALERT_CACHE_HIT_THRESHOLD
    if hit_rate < threshold:
        _record_alert(
            "performance",
            f"Cache hit rate {hit_rate:.4f} < threshold {threshold:.4f}",
        )
        return 1
    _log(f"[MONITOR][alerts] Cache hit rate: {hit_rate:.4f} (threshold: {threshold:.4f})")
    return 0


def _check_faithfulness_alert() -> int:
    metrics = _monitoring_state.get("metrics_cache", {})
    ragas = metrics.get("ragas_evaluation", {})
    results = ragas.get("results", {})
    faithfulness = results.get("faithfulness", {})
    mean_score = faithfulness.get("mean")
    if mean_score is None:
        _log("[MONITOR][alerts] Faithfulness data not available, skipping")
        return 0
    threshold = MonitoringConfig.ALERT_FAITHFULNESS_THRESHOLD
    if mean_score < threshold:
        _record_alert(
            "quality",
            f"Faithfulness {mean_score:.4f} < threshold {threshold:.4f}",
        )
        return 1
    _log(f"[MONITOR][alerts] Faithfulness: {mean_score:.4f} (threshold: {threshold:.4f})")
    return 0


# ============================================================
# Task: Data Cleanup
# ============================================================

def task_data_cleanup() -> None:
    try:
        _log("[MONITOR][cleanup] Starting data cleanup...")
        deleted = {
            "performance_logs": 0,
            "alerts": 0,
            "cache_stats": 0,
        }

        deleted["performance_logs"] += _cleanup_performance_logs()
        deleted["alerts"] += _cleanup_alerts()
        deleted["cache_stats"] += _cleanup_cache_data()

        _monitoring_state["last_runs"]["cleanup"] = {
            "time": datetime.utcnow().isoformat(),
            "deleted": deleted,
        }
        _log(f"[MONITOR][cleanup] Completed. Deleted: {deleted}")
    except Exception as e:
        logger.error(f"[MONITOR][cleanup] Unexpected error: {e}")


def _cleanup_performance_logs() -> int:
    try:
        from app.api.routes import db
        if db is None:
            return 0
        session = db.get_session()
        try:
            from app.db.models import PerformanceLog
            cutoff = datetime.utcnow() - timedelta(days=30)
            count = (
                session.query(PerformanceLog)
                .filter(PerformanceLog.created_at < cutoff)
                .delete()
            )
            session.commit()
            _log(f"[MONITOR][cleanup] Deleted {count} expired performance logs")
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"[MONITOR][cleanup] Performance log cleanup failed: {e}")
        return 0


def _cleanup_alerts() -> int:
    try:
        from app.api.routes import db
        if db is None:
            return 0
        session = db.get_session()
        try:
            from app.db.models import Alert
            cutoff = datetime.utcnow() - timedelta(days=30)
            count = (
                session.query(Alert)
                .filter(Alert.created_at < cutoff)
                .delete()
            )
            session.commit()
            _log(f"[MONITOR][cleanup] Deleted {count} expired alerts")
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"[MONITOR][cleanup] Alert cleanup failed: {e}")
        return 0


def _cleanup_cache_data() -> int:
    try:
        from app.services.query_cache import get_l1_cache
        from app.services.vector_cache import get_query_cache
        l1_cleaned = get_l1_cache().evict_expired()
        l2_cleaned = get_query_cache()._evict_expired()
        total = l1_cleaned + l2_cleaned
        _log(f"[MONITOR][cleanup] Cache cleanup: L1={l1_cleaned}, L2={l2_cleaned}")
        return total
    except Exception as e:
        logger.warning(f"[MONITOR][cleanup] Cache cleanup failed: {e}")
        return 0


# ============================================================
# Scheduler Management
# ============================================================

def _register_jobs(scheduler: BackgroundScheduler) -> List[Job]:
    jobs = []

    if MonitoringConfig.is_task_enabled("health_check"):
        job = scheduler.add_job(
            func=task_health_check,
            trigger=IntervalTrigger(minutes=MonitoringConfig.HEALTH_CHECK_INTERVAL),
            id="health_check",
            name="Health Check",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=60,
        )
        jobs.append(job)
        _log(f"[MONITOR] Scheduled health_check every {MonitoringConfig.HEALTH_CHECK_INTERVAL}min")

    if MonitoringConfig.is_task_enabled("metrics"):
        job = scheduler.add_job(
            func=task_metrics_collection,
            trigger=IntervalTrigger(minutes=MonitoringConfig.METRICS_INTERVAL),
            id="metrics",
            name="Metrics Collection",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=120,
        )
        jobs.append(job)
        _log(f"[MONITOR] Scheduled metrics every {MonitoringConfig.METRICS_INTERVAL}min")

    if MonitoringConfig.is_task_enabled("alerts"):
        job = scheduler.add_job(
            func=task_alert_detection,
            trigger=IntervalTrigger(minutes=MonitoringConfig.ALERT_INTERVAL),
            id="alerts",
            name="Alert Detection",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=120,
        )
        jobs.append(job)
        _log(f"[MONITOR] Scheduled alerts every {MonitoringConfig.ALERT_INTERVAL}min")

    if MonitoringConfig.is_task_enabled("cleanup"):
        job = scheduler.add_job(
            func=task_data_cleanup,
            trigger=CronTrigger(
                hour=MonitoringConfig.CLEANUP_HOUR,
                minute=0,
            ),
            id="cleanup",
            name="Data Cleanup",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,
        )
        jobs.append(job)
        _log(f"[MONITOR] Scheduled cleanup at {MonitoringConfig.CLEANUP_HOUR}:00 daily")

    return jobs


def start_scheduler() -> Optional[BackgroundScheduler]:
    global _scheduler
    if not MonitoringConfig.ENABLED:
        _log("[MONITOR] Monitoring scheduler disabled by configuration.")
        return None

    with _scheduler_lock:
        if _scheduler is not None and _scheduler.running:
            _log("[MONITOR] Scheduler already running.")
            return _scheduler

        _log("[MONITOR] Starting background scheduler...")
        scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
            }
        )

        jobs = _register_jobs(scheduler)
        scheduler.start()

        _scheduler = scheduler
        _monitoring_state["running"] = True
        _monitoring_state["started_at"] = datetime.utcnow().isoformat()

        _log(f"[MONITOR] Scheduler started with {len(jobs)} job(s).")
        return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            _log("[MONITOR] Stopping scheduler...")
            try:
                _scheduler.shutdown(wait=True)
            except Exception as e:
                logger.error(f"[MONITOR] Error stopping scheduler: {e}")
            _scheduler = None
            _monitoring_state["running"] = False
            _log("[MONITOR] Scheduler stopped.")


def get_scheduler() -> Optional[BackgroundScheduler]:
    return _scheduler


def get_monitoring_status() -> Dict[str, Any]:
    return {
        "running": _monitoring_state["running"],
        "started_at": _monitoring_state["started_at"],
        "config": {
            "enabled": MonitoringConfig.ENABLED,
            "tasks_enabled": MonitoringConfig.TASKS_ENABLED_LIST,
            "health_check_interval_min": MonitoringConfig.HEALTH_CHECK_INTERVAL,
            "metrics_interval_min": MonitoringConfig.METRICS_INTERVAL,
            "alert_interval_min": MonitoringConfig.ALERT_INTERVAL,
            "cleanup_hour": MonitoringConfig.CLEANUP_HOUR,
            "silent": MonitoringConfig.SILENT,
        },
        "last_runs": _monitoring_state.get("last_runs", {}),
    }


def get_schedule_info() -> List[Dict[str, Any]]:
    scheduler = get_scheduler()
    if scheduler is None or not scheduler.running:
        return []

    schedule = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time.isoformat() if job.next_run_time else None
        schedule.append({
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run": next_run,
            "max_instances": job.max_instances,
        })
    return schedule


def run_job_now(job_id: str) -> Dict[str, Any]:
    scheduler = get_scheduler()
    if scheduler is None or not scheduler.running:
        return {"success": False, "error": "Scheduler not running"}

    job = scheduler.get_job(job_id)
    if job is None:
        return {"success": False, "error": f"Job '{job_id}' not found"}

    task_map = {
        "health_check": task_health_check,
        "metrics": task_metrics_collection,
        "alerts": task_alert_detection,
        "cleanup": task_data_cleanup,
    }

    task_func = task_map.get(job_id)
    if task_func is None:
        return {"success": False, "error": f"No task function for job '{job_id}'"}

    try:
        task_func()
        return {
            "success": True,
            "job_id": job_id,
            "executed_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
