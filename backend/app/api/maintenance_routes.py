"""
自动维护API接口
提供手动触发更新、状态查询、数据源管理等接口
"""
from flask import Blueprint, request, jsonify
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 创建路由
maintenance_bp = Blueprint('maintenance', __name__, url_prefix='/api/v1/maintenance')


def get_maintenance_system():
    """延迟导入获取系统实例"""
    from app.services.auto_maintenance import get_maintenance_system
    return get_maintenance_system()


# ============ API接口 ============

@maintenance_bp.route('/sync', methods=['POST'])
def trigger_sync():
    """
    手动触发同步
    请求: {"sync_type": "full/incremental/emergency", "priority": 5}
    """
    try:
        data = request.get_json(silent=True) or {}
        sync_type = data.get('sync_type', 'incremental')
        priority = data.get('priority', 5)
        
        system = get_maintenance_system()
        
        if sync_type == "full":
            task = system.trigger_full_sync()
            message = "全量同步任务已触发"
        elif sync_type == "incremental":
            task = system.trigger_incremental_sync()
            message = "增量同步任务已触发"
        elif sync_type == "emergency":
            task = system.trigger_emergency_update()
            message = "紧急更新任务已触发"
        else:
            return jsonify({
                "success": False,
                "error": "无效的同步类型 (full/incremental/emergency)"
            }), 400
        
        return jsonify({
            "success": True,
            "task_id": task.task_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Sync trigger failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/status', methods=['GET'])
def get_status():
    """获取维护系统状态"""
    try:
        system = get_maintenance_system()
        status = system.get_status()
        
        return jsonify({
            "success": True,
            "is_running": status.is_running,
            "scheduler_status": status.scheduler_status,
            "data_source_health": status.data_source_health,
            "last_sync": status.last_sync,
            "active_tasks": status.active_tasks,
            "cards_in_kb": status.cards_in_kb,
            "timestamp": status.timestamp.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Get status failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """获取详细统计信息"""
    try:
        system = get_maintenance_system()
        stats = system.get_all_statistics()
        
        return jsonify({
            "success": True,
            "statistics": stats
        })
        
    except Exception as e:
        logger.error(f"Get statistics failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/data-sources', methods=['GET'])
def list_data_sources():
    """获取所有数据源列表"""
    try:
        system = get_maintenance_system()
        manager = system.get_data_source_manager()
        sources = manager.get_all_sources()
        
        return jsonify({
            "success": True,
            "total": len(sources),
            "sources": [
                {
                    "id": s.id,
                    "name": s.name,
                    "url": s.url,
                    "enabled": s.enabled,
                    "priority": s.priority,
                    "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
                    "health_score": s.health_score,
                    "last_check_time": s.last_check_time.isoformat() if s.last_check_time else None,
                    "last_success_time": s.last_success_time.isoformat() if s.last_success_time else None
                }
                for s in sources
            ]
        })
        
    except Exception as e:
        logger.error(f"List data sources failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/data-sources', methods=['POST'])
def add_data_source():
    """添加数据源"""
    try:
        data = request.get_json(silent=True) or {}

        if not data or 'name' not in data or 'url' not in data:
            return jsonify({
                "success": False,
                "error": "缺少必要字段 (name, url)"
            }), 400
        
        system = get_maintenance_system()
        manager = system.get_data_source_manager()
        
        source_config = {
            'id': data.get('id', f"custom_{int(datetime.now().timestamp())}"),
            'name': data['name'],
            'url': data['url'],
            'api_key': data.get('api_key'),
            'type': data.get('type', 'third_party'),
            'enabled': data.get('enabled', True),
            'priority': data.get('priority', 10),
            'timeout': data.get('timeout', 30),
            'update_interval': data.get('update_interval', 3600),
            'headers': data.get('headers', {}),
            'metadata': data.get('metadata', {})
        }
        
        source = manager.add_source(source_config)
        
        return jsonify({
            "success": True,
            "message": f"数据源 {source.name} 已添加",
            "source_id": source.id
        })
        
    except Exception as e:
        logger.error(f"Add data source failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/data-sources/<source_id>', methods=['DELETE'])
def remove_data_source(source_id):
    """移除数据源"""
    try:
        system = get_maintenance_system()
        manager = system.get_data_source_manager()
        
        if manager.remove_source(source_id):
            return jsonify({
                "success": True,
                "message": f"数据源 {source_id} 已移除"
            })
        else:
            return jsonify({
                "success": False,
                "error": "数据源不存在"
            }), 404
            
    except Exception as e:
        logger.error(f"Remove data source failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/data-sources/<source_id>/health-check', methods=['POST'])
def check_data_source_health(source_id):
    """检查数据源健康状态"""
    try:
        system = get_maintenance_system()
        manager = system.get_data_source_manager()
        
        result = manager.check_source_health(source_id)
        
        return jsonify({
            "success": True,
            "source_id": result.source_id,
            "is_healthy": result.is_healthy,
            "response_time": result.response_time,
            "status_code": result.status_code,
            "error": result.error_message,
            "timestamp": result.timestamp.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/scheduler/start', methods=['POST'])
def start_scheduler():
    """启动调度器"""
    try:
        system = get_maintenance_system()
        
        if system._is_running:
            return jsonify({
                "success": True,
                "message": "调度器已在运行"
            })
        
        system.start()
        return jsonify({
            "success": True,
            "message": "调度器已启动"
        })
        
    except Exception as e:
        logger.error(f"Start scheduler failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """停止调度器"""
    try:
        system = get_maintenance_system()
        system.stop()
        
        return jsonify({
            "success": True,
            "message": "调度器已停止"
        })
        
    except Exception as e:
        logger.error(f"Stop scheduler failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/scheduler/jobs', methods=['GET'])
def list_scheduler_jobs():
    """获取调度任务列表"""
    try:
        system = get_maintenance_system()
        scheduler = system.get_scheduler()
        
        jobs = scheduler.scheduler.get_jobs() if hasattr(scheduler, 'scheduler') and scheduler.scheduler else []
        
        return jsonify({
            "success": True,
            "total": len(jobs),
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in jobs
            ]
        })
        
    except Exception as e:
        logger.error(f"List jobs failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/scheduler/history', methods=['GET'])
def get_task_history():
    """获取任务历史"""
    try:
        limit = int(request.args.get('limit', 20))
        
        system = get_maintenance_system()
        scheduler = system.get_scheduler()
        
        history = scheduler.get_task_history(limit=limit)
        
        return jsonify({
            "success": True,
            "total": len(history),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type),
                    "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "duration": task.duration,
                    "error": task.error
                }
                for task in history
            ]
        })
        
    except Exception as e:
        logger.error(f"Get history failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/knowledge-base/cards', methods=['GET'])
def list_kb_cards():
    """获取知识库中的卡片列表"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        system = get_maintenance_system()
        kb_sync = system.get_kb_sync()
        
        cards = kb_sync.get_all_cards()
        
        # 分页
        paginated = cards[offset:offset+limit]
        
        return jsonify({
            "success": True,
            "total": len(cards),
            "limit": limit,
            "offset": offset,
            "cards": paginated
        })
        
    except Exception as e:
        logger.error(f"List cards failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@maintenance_bp.route('/knowledge-base/versions', methods=['GET'])
def get_version_history():
    """获取知识库版本历史"""
    try:
        limit = int(request.args.get('limit', 10))
        
        system = get_maintenance_system()
        kb_sync = system.get_kb_sync()
        
        history = kb_sync.get_version_history(limit=limit)
        
        return jsonify({
            "success": True,
            "total": len(history),
            "versions": [
                {
                    "version_id": v.version_id,
                    "timestamp": v.timestamp.isoformat(),
                    "cards_added": v.cards_added,
                    "cards_updated": v.cards_updated,
                    "status": v.status,
                    "error": v.error
                }
                for v in history
            ]
        })
        
    except Exception as e:
        logger.error(f"Get versions failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def register_maintenance_routes(app):
    """注册维护路由到应用"""
    app.register_blueprint(maintenance_bp)
