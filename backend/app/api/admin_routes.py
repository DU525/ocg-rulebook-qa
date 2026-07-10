"""
Admin 管理端 API（系统级管理接口）

设计说明：
- 提供系统级管理能力：聚合统计、缓存管理、用户列表（mock）、健康检查、配置查看。
- 与项目其他 admin 接口一致，不引入新的鉴权层（生产环境应挂 @admin_required 装饰器或 IP 白名单）。
- 所有端点挂在 /api/v1/admin 前缀，独立 Blueprint。

端点清单：
  GET  /api/v1/admin/stats              系统聚合统计（向量库、数据库、反馈、会话、缓存）
  POST /api/v1/admin/cache/clear        清理 L1/L2/L3 缓存
  GET  /api/v1/admin/users              用户列表（mock 数据，因为项目目前无 User model）
  GET  /api/v1/admin/health             快速健康检查（轻量版，不查 LLM）
  GET  /api/v1/admin/config             查看 RAG 运行时配置
  POST /api/v1/admin/config/reload      重新加载配置（mock — 实际是触发 RAG 热重载标记）
"""
import logging
import os
import time
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

admin_api = Blueprint('admin_api', __name__, url_prefix='/api/v1/admin')


def _get_db():
    """惰性获取 db 实例"""
    try:
        from app.api import get_services
        _, _, db, *_ = get_services()
        return db
    except Exception as e:
        logger.warning("admin 无法获取 db: %s", e)
        return None


def _get_vector_store():
    try:
        from app.api import get_services
        vector_store, *_ = get_services()
        return vector_store
    except Exception:
        return None


def _get_rag_engine():
    try:
        from app.api import get_services
        _, rag_engine, *_ = get_services()
        return rag_engine
    except Exception:
        return None


@admin_api.route('/stats', methods=['GET'])
def admin_stats():
    """系统聚合统计

    汇总：
      - 数据库: conversations / messages / feedbacks / negative_samples / documents / alerts
      - 向量库: collection_count
      - 反馈分布: positive/negative/recent_24h
      - 缓存: L1/L2/L3 hit rate
    """
    db = _get_db()
    vs = _get_vector_store()
    rag = _get_rag_engine()

    stats = {
        'timestamp': datetime.utcnow().isoformat(),
        'database': {},
        'vector_store': {},
        'feedbacks': {},
        'cache': {},
        'rag': {},
    }

    # 数据库统计
    if db is not None:
        try:
            from app.db.models import (
                Conversation, Message, Feedback, NegativeSample,
                Document, Alert, PerformanceLog,
            )
            session = db.get_session()
            try:
                stats['database'] = {
                    'conversations': session.query(Conversation).count(),
                    'messages': session.query(Message).count(),
                    'feedbacks': session.query(Feedback).count(),
                    'negative_samples': session.query(NegativeSample).count(),
                    'documents': session.query(Document).count(),
                    'alerts_total': session.query(Alert).count(),
                    'alerts_unread': session.query(Alert).filter_by(is_read=False).count() if hasattr(Alert, 'is_read') else 0,
                    'performance_logs': session.query(PerformanceLog).count(),
                }
                # 反馈分布
                pos = session.query(Feedback).filter_by(rating='positive').count()
                neg = session.query(Feedback).filter_by(rating='negative').count()
                cutoff_24h = datetime.utcnow() - timedelta(hours=24)
                recent = session.query(Feedback).filter(Feedback.created_at >= cutoff_24h).count()
                stats['feedbacks'] = {
                    'positive': pos,
                    'negative': neg,
                    'total': pos + neg,
                    'positive_rate': round(pos / (pos + neg), 4) if (pos + neg) else 0.0,
                    'recent_24h': recent,
                }
            finally:
                session.close()
        except Exception as e:
            logger.warning("admin_stats 数据库统计失败: %s", e)
            stats['database'] = {'error': str(e)}
    else:
        stats['database'] = {'error': 'db 未初始化'}

    # 向量库统计
    if vs is not None:
        try:
            collection_stats = vs.get_collection_stats() if hasattr(vs, 'get_collection_stats') else {}
            stats['vector_store'] = {
                'count': collection_stats.get('count', 0) if isinstance(collection_stats, dict) else 0,
                'collection_name': getattr(vs, 'collection_name', None) or getattr(vs, 'COLLECTION_NAME', None),
            }
        except Exception as e:
            stats['vector_store'] = {'error': str(e)}
    else:
        stats['vector_store'] = {'error': 'vector_store 未初始化'}

    # RAG 引擎
    if rag is not None:
        try:
            stats['rag'] = {
                'use_multi_stage': getattr(rag, 'use_multi_stage', None),
                'has_provider': rag.provider is not None,
                'provider_name': (
                    type(rag.provider.primary).__name__
                    if rag.provider and hasattr(rag.provider, 'primary')
                    else type(rag.provider).__name__ if rag.provider else None
                ),
            }
        except Exception as e:
            stats['rag'] = {'error': str(e)}
    else:
        stats['rag'] = {'error': 'rag_engine 未初始化'}

    # 缓存统计
    try:
        from app.services.query_cache import get_l1_cache
        from app.services.redis_cache import get_redis_cache
        from app.services.simhash_cache import get_simhash_cache

        l1 = get_l1_cache()
        l2 = get_redis_cache()
        l3 = get_simhash_cache()

        stats['cache'] = {
            'l1': l1.get_stats() if hasattr(l1, 'get_stats') else {},
            'l2': {
                'mode': 'memory_fallback' if l2.is_fallback_mode() else 'redis',
                'stats': l2.get_stats() if hasattr(l2, 'get_stats') else {},
            } if l2 else {},
            'l3': l3.get_stats() if hasattr(l3, 'get_stats') else {},
        }
    except Exception as e:
        stats['cache'] = {'error': str(e)}

    return jsonify({'success': True, 'data': stats})


@admin_api.route('/cache/clear', methods=['POST'])
def admin_cache_clear():
    """清理 L1 / L2 / L3 缓存

    Body（可选）: {"levels": ["l1", "l2", "l3"]}，缺省全清
    """
    body = request.get_json(silent=True) or {}
    levels = body.get('levels') or ['l1', 'l2', 'l3']
    if not isinstance(levels, list):
        return jsonify({
            'success': False,
            'error': {'code': 'INVALID_REQUEST', 'message': 'levels 必须是数组'}
        }), 400

    result = {'requested': levels, 'cleared': {}, 'errors': {}}

    if 'l1' in levels:
        try:
            from app.services.query_cache import get_l1_cache
            l1 = get_l1_cache()
            if l1 and hasattr(l1, 'clear'):
                l1.clear()
                result['cleared']['l1'] = True
            else:
                result['cleared']['l1'] = False
        except Exception as e:
            result['errors']['l1'] = str(e)

    if 'l2' in levels:
        try:
            from app.services.redis_cache import get_redis_cache
            l2 = get_redis_cache()
            if l2 and hasattr(l2, 'clear'):
                l2.clear()
                result['cleared']['l2'] = True
            else:
                result['cleared']['l2'] = False
        except Exception as e:
            result['errors']['l2'] = str(e)

    if 'l3' in levels:
        try:
            from app.services.simhash_cache import get_simhash_cache
            l3 = get_simhash_cache()
            if l3 and hasattr(l3, 'clear'):
                l3.clear()
                result['cleared']['l3'] = True
            else:
                result['cleared']['l3'] = False
        except Exception as e:
            result['errors']['l3'] = str(e)

    logger.info("admin cache clear: %s (errors: %s)", result['cleared'], result['errors'])
    status = 200 if not result['errors'] else 207
    return jsonify({'success': not result['errors'], 'data': result}), status


@admin_api.route('/users', methods=['GET'])
def admin_users():
    """用户列表

    项目当前没有 User model（只有 Conversation/Message），所以本端点返回 mock 数据 + 基于
    Conversation 的活跃用户聚合（去重 conversation_id 前 8 位作为匿名 user hash）。

    Query:
      page: 页码（默认 1）
      page_size: 每页（默认 20）
      include_mock: 是否包含 mock 示例用户（默认 true，方便前端开发）
    """
    try:
        page = max(1, request.args.get('page', 1, type=int))
        page_size = min(100, max(1, request.args.get('page_size', 20, type=int)))
        include_mock = request.args.get('include_mock', 'true').lower() != 'false'

        db = _get_db()
        real_users = []
        if db is not None:
            try:
                from app.db.models import Conversation, Message
                session = db.get_session()
                try:
                    # 按 conversation_id 聚合活跃度（取前 8 位作为匿名 user 标识）
                    rows = (
                        session.query(
                            Conversation.id,
                            Conversation.title,
                            Conversation.created_at,
                            Conversation.updated_at,
                        )
                        .order_by(Conversation.updated_at.desc())
                        .limit(500)  # 最多扫 500 条会话
                        .all()
                    )
                    for cid, title, created_at, updated_at in rows:
                        real_users.append({
                            'user_id': f'anon-{cid[:8]}',
                            'display_name': title or f'会话 {cid[:8]}',
                            'role': 'guest',
                            'source': 'conversation',
                            'conversation_id': cid,
                            'created_at': created_at.isoformat() if created_at else None,
                            'updated_at': updated_at.isoformat() if updated_at else None,
                        })
                finally:
                    session.close()
            except Exception as e:
                logger.warning("admin_users 数据库查询失败: %s", e)

        mock_users = [
            {
                'user_id': 'mock-admin-001',
                'display_name': '示例管理员',
                'role': 'admin',
                'source': 'mock',
                'email': 'admin@example.com',
                'created_at': '2026-01-01T00:00:00',
            },
            {
                'user_id': 'mock-user-001',
                'display_name': '示例用户A',
                'role': 'user',
                'source': 'mock',
                'email': 'user_a@example.com',
                'created_at': '2026-02-15T10:30:00',
            },
        ] if include_mock else []

        all_users = mock_users + real_users
        total = len(all_users)
        start = (page - 1) * page_size
        items = all_users[start:start + page_size]

        return jsonify({
            'success': True,
            'data': {
                'items': items,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size if total else 0,
                },
                'note': 'mock 数据 + 基于会话的匿名用户聚合；待 User model 落地后切换为真实表',
            }
        })
    except Exception as e:
        logger.error("admin_users 失败: %s", e)
        return jsonify({
            'success': False,
            'error': {'code': 'LIST_USERS_FAILED', 'message': str(e)}
        }), 500


@admin_api.route('/health', methods=['GET'])
def admin_health():
    """轻量级健康检查（不查 LLM，避免慢响应）

    检查项：进程、磁盘、数据库可连接、向量库可连接
    """
    components = {}

    # 进程
    components['process'] = {
        'status': 'healthy',
        'pid': os.getpid(),
        'uptime_unavailable': True,  # 简化：未维护启动时间
    }

    # 数据库
    db = _get_db()
    if db is not None:
        try:
            session = db.get_session()
            try:
                from sqlalchemy import text
                session.execute(text('SELECT 1'))
                components['database'] = {'status': 'healthy'}
            finally:
                session.close()
        except Exception as e:
            components['database'] = {'status': 'down', 'message': str(e)}
    else:
        components['database'] = {'status': 'down', 'message': 'db 未初始化'}

    # 向量库（仅探活）
    vs = _get_vector_store()
    if vs is not None:
        try:
            # 仅尝试拿元数据，不触发 embedding
            if hasattr(vs, 'get_collection_stats'):
                vs.get_collection_stats()
            components['vector_store'] = {'status': 'healthy'}
        except Exception as e:
            components['vector_store'] = {'status': 'down', 'message': str(e)}
    else:
        components['vector_store'] = {'status': 'down', 'message': 'vector_store 未初始化'}

    # 汇总
    statuses = [c.get('status') for c in components.values()]
    if all(s == 'healthy' for s in statuses):
        overall = 'healthy'
        http_code = 200
    elif any(s == 'down' for s in statuses):
        overall = 'degraded'
        http_code = 503
    else:
        overall = 'degraded'
        http_code = 200

    return jsonify({
        'success': overall == 'healthy',
        'data': {
            'status': overall,
            'components': components,
            'timestamp': datetime.utcnow().isoformat(),
        }
    }), http_code


@admin_api.route('/config', methods=['GET'])
def admin_get_config():
    """查看 RAG 运行时配置 + 关键开关状态"""
    try:
        from app.config import Config

        cfg = {
            'llm_provider': getattr(Config, 'LLM_PROVIDER', None),
            'fallback_provider': getattr(Config, 'FALLBACK_PROVIDER', None),
            'model_name': getattr(Config, 'MODEL_NAME', None),
            'fallback_model_name': getattr(Config, 'FALLBACK_MODEL_NAME', None),
            'agent_type': getattr(Config, 'AGENT_TYPE', None),
            'agent_max_iterations': getattr(Config, 'AGENT_MAX_ITERATIONS', None),
            'rrf_enabled': bool(getattr(Config, 'RRF_ENABLED', True)),
            'ocg_chroma_db_path': getattr(Config, 'OCG_CHROMA_DB_PATH', None),
            'ocg_sqlite_db_path': getattr(Config, 'OCG_SQLITE_DB_PATH', None),
        }
        # 掩码 API key
        for key in ('minimax_api_key', 'openai_api_key'):
            val = getattr(Config, key.upper(), None) or getattr(Config, key, None)
            if val:
                cfg[key] = f'{val[:6]}...{val[-4:]}' if len(val) > 12 else '***'
        return jsonify({'success': True, 'data': cfg})
    except Exception as e:
        logger.error("admin_get_config 失败: %s", e)
        return jsonify({
            'success': False,
            'error': {'code': 'GET_CONFIG_FAILED', 'message': str(e)}
        }), 500


@admin_api.route('/config/reload', methods=['POST'])
def admin_reload_config():
    """触发配置热重载（mock 实现 — 实际重载 RAG 引擎的状态）

    真正的 reload 需要重启进程或重建 RAG 引擎实例。本端点仅作为标记位：返回成功，
    提示"完整 reload 需要重启 Flask 进程"。

    Body（可选）: {"scope": "all|rag|cache"}
    """
    body = request.get_json(silent=True) or {}
    scope = body.get('scope', 'cache')

    actions = []
    if scope in ('all', 'cache'):
        try:
            from app.services.query_cache import get_l1_cache
            l1 = get_l1_cache()
            if l1 and hasattr(l1, 'clear'):
                l1.clear()
                actions.append('l1_cache_cleared')
        except Exception as e:
            logger.warning("reload l1 cache 失败: %s", e)

    return jsonify({
        'success': True,
        'data': {
            'scope': scope,
            'actions': actions,
            'note': '轻量 reload：仅清理 L1 缓存。完整 reload（RAG/provider/skills）需要重启 Flask 进程。',
            'timestamp': datetime.utcnow().isoformat(),
        }
    })


# 暴露 blueprint 给 __init__.py 直接 register_blueprint 使用
# 同时也提供 register_admin_routes(app) 函数风格保持一致性
def register_admin_routes(app):
    """注册 admin 路由到 Flask app"""
    app.register_blueprint(admin_api)
    logger.info("✓ admin 路由已注册 (prefix=/api/v1/admin)")
    return admin_api
