"""
A/B Experiment 管理端 API（admin 视角的实验管理）

设计说明：
- base_routes.py 没有 user-facing experiment 端点；本文件独立提供 6 个 admin 端点。
- 不引入新鉴权（与项目其他 admin 接口一致），后续可挂 @admin_required 装饰器。
- Blueprint name: experiment_api
- url_prefix: /api/v1/experiments

端点清单：
  GET    /api/v1/experiments                  分页列出实验（支持 status / keyword 过滤）
  GET    /api/v1/experiments/<exp_id>         实验详情
  POST   /api/v1/experiments                  创建实验
  PATCH  /api/v1/experiments/<exp_id>         更新 status / config / description
  DELETE /api/v1/experiments/<exp_id>         删除实验（不级联删 ExperimentLog，保留历史）
  GET    /api/v1/experiments/<exp_id>/stats   聚合统计（按 variant 维度聚合 ExperimentLog）
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

experiment_api = Blueprint(
    'experiment_api',
    __name__,
    url_prefix='/api/v1/experiments',
)

# 允许的 status 取值（与 ORM 模型的注释保持一致）
ALLOWED_STATUSES = {'draft', 'running', 'paused', 'completed', 'archived'}
ALLOWED_TYPES = {'a_b_test', 'multi_armed_bandit', 'feature_flag'}


# ============================================================
# 工具函数
# ============================================================

def _get_db():
    """惰性获取 db 实例（避免循环 import）"""
    try:
        from app.api import get_services
        # 优先使用 OCG 服务（base_routes 初始化过的那个）
        vector_store, rag_engine, db, *_ = get_services()
        return db
    except Exception as e:
        logger.warning("experiment_routes 无法获取 db: %s", e)
        return None


def _err(code: str, message: str, http_status: int = 500):
    """统一错误响应"""
    return jsonify({
        'success': False,
        'error': {'code': code, 'message': message},
    }), http_status


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _serialize_experiment(exp) -> Dict[str, Any]:
    """Experiment → JSON dict"""
    return {
        'id': exp.id,
        'name': exp.name,
        'description': exp.description,
        'status': exp.status,
        'experiment_type': exp.experiment_type,
        'config': exp.config or {},
        'created_at': exp.created_at.isoformat() if exp.created_at else None,
        'updated_at': exp.updated_at.isoformat() if exp.updated_at else None,
        'started_at': exp.started_at.isoformat() if exp.started_at else None,
        'ended_at': exp.ended_at.isoformat() if exp.ended_at else None,
    }


def _validate_status(value: Optional[str]) -> Tuple[bool, str]:
    if value is None:
        return True, ''
    if value not in ALLOWED_STATUSES:
        return False, f"status 取值非法，应为 {sorted(ALLOWED_STATUSES)} 之一"
    return True, ''


def _validate_type(value: Optional[str]) -> Tuple[bool, str]:
    if value is None:
        return True, ''
    if value not in ALLOWED_TYPES:
        return False, f"experiment_type 取值非法，应为 {sorted(ALLOWED_TYPES)} 之一"
    return True, ''


def _validate_config(value: Any) -> Tuple[bool, str]:
    """config 必须是 dict；variants 是 [{name, weight}] 列表（弱校验）"""
    if value is None:
        return True, ''
    if not isinstance(value, dict):
        return False, 'config 必须是 dict'

    variants = value.get('variants')
    if variants is not None:
        if not isinstance(variants, list) or not variants:
            return False, 'config.variants 必须是非空 list'
        for i, v in enumerate(variants):
            if not isinstance(v, dict):
                return False, f'config.variants[{i}] 必须是 dict'
            if 'name' not in v or not v['name']:
                return False, f'config.variants[{i}].name 必填'
            if 'weight' in v:
                try:
                    w = float(v['weight'])
                    if w < 0 or w > 1:
                        return False, f'config.variants[{i}].weight 必须在 [0,1]'
                except (TypeError, ValueError):
                    return False, f'config.variants[{i}].weight 必须是数字'
    return True, ''


# ============================================================
# 端点
# ============================================================

@experiment_api.route('/', methods=['GET'])
@experiment_api.route('', methods=['GET'])
def list_experiments():
    """分页列出 experiments

    Query:
      page: 页码（默认 1）
      page_size: 每页数量（默认 20，最大 100）
      status: 按 status 过滤（draft/running/paused/completed/archived）
      keyword: 在 name / description 中模糊搜索
    """
    try:
        db = _get_db()
        if db is None:
            return _err('DB_UNAVAILABLE', '数据库未初始化', 503)

        page = max(1, request.args.get('page', 1, type=int))
        page_size = min(100, max(1, request.args.get('page_size', 20, type=int)))
        status = request.args.get('status', '').strip()
        keyword = request.args.get('keyword', '').strip()

        # 延迟导入 ORM 模型（避免循环）
        from app.db.models import Experiment

        session = db.get_session()
        try:
            q = session.query(Experiment)
            if status:
                q = q.filter(Experiment.status == status)
            if keyword:
                like = f'%{keyword}%'
                q = q.filter(
                    (Experiment.name.like(like)) | (Experiment.description.like(like))
                )

            total = q.count()
            items = (
                q.order_by(Experiment.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return jsonify({
                'success': True,
                'data': {
                    'items': [_serialize_experiment(e) for e in items],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size if total else 0,
                    },
                    'filters': {
                        'status': status or None,
                        'keyword': keyword or None,
                    },
                }
            })
        finally:
            session.close()
    except Exception as e:
        logger.error("list_experiments 失败: %s", e)
        return _err('LIST_FAILED', str(e), 500)


@experiment_api.route('/<exp_id>', methods=['GET'])
def get_experiment_detail(exp_id: str):
    """实验详情"""
    try:
        db = _get_db()
        if db is None:
            return _err('DB_UNAVAILABLE', '数据库未初始化', 503)

        from app.db.models import Experiment

        session = db.get_session()
        try:
            exp = session.query(Experiment).filter_by(id=exp_id).first()
            if not exp:
                # 兼容按 name 查找
                exp = session.query(Experiment).filter_by(name=exp_id).first()
            if not exp:
                return _err('NOT_FOUND', f'experiment {exp_id} 不存在', 404)
            return jsonify({'success': True, 'data': _serialize_experiment(exp)})
        finally:
            session.close()
    except Exception as e:
        logger.error("get_experiment_detail 失败: %s", e)
        return _err('GET_FAILED', str(e), 500)


@experiment_api.route('/', methods=['POST'])
@experiment_api.route('', methods=['POST'])
def create_experiment():
    """创建实验

    Body: {
      "name": "rag_prompt_v2",            # 必填，唯一
      "description": "测试新 prompt 模板", # 选填
      "experiment_type": "a_b_test",      # 选填，默认 a_b_test
      "config": {                          # 选填
        "variants": [{"name": "control", "weight": 0.5}, {"name": "treatment", "weight": 0.5}],
        "target_metric": "positive_rate",
        "traffic_allocation": 1.0
      }
    }
    """
    try:
        body = request.get_json(silent=True) or {}
        name = (body.get('name') or '').strip()
        if not name:
            return _err('INVALID_REQUEST', 'name 必填', 400)
        if len(name) > 100:
            return _err('INVALID_REQUEST', 'name 长度不能超过 100', 400)

        ok, msg = _validate_type(body.get('experiment_type'))
        if not ok:
            return _err('INVALID_REQUEST', msg, 400)
        ok, msg = _validate_config(body.get('config'))
        if not ok:
            return _err('INVALID_REQUEST', msg, 400)

        db = _get_db()
        if db is None:
            return _err('DB_UNAVAILABLE', '数据库未初始化', 503)

        from app.db.models import Experiment

        session = db.get_session()
        try:
            existing = session.query(Experiment).filter_by(name=name).first()
            if existing:
                return _err('ALREADY_EXISTS', f'experiment name={name} 已存在', 409)

            exp = Experiment(
                id=str(uuid.uuid4()),
                name=name,
                description=body.get('description'),
                status=body.get('status', 'draft'),
                experiment_type=body.get('experiment_type', 'a_b_test'),
                config=body.get('config') or {},
            )
            # 创建时若 status='running'，自动填 started_at
            if exp.status == 'running':
                exp.started_at = datetime.utcnow()

            session.add(exp)
            session.commit()
            logger.info("创建 experiment id=%s name=%s", exp.id, exp.name)
            return jsonify({
                'success': True,
                'data': _serialize_experiment(exp),
            }), 201
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error("create_experiment 失败: %s", e)
        return _err('CREATE_FAILED', str(e), 500)


@experiment_api.route('/<exp_id>', methods=['PATCH'])
def update_experiment(exp_id: str):
    """更新实验

    Body（所有字段选填，至少传一个）:
      status: draft/running/paused/completed/archived
      description: 文本
      config: dict
      experiment_type: a_b_test/multi_armed_bandit/feature_flag
    """
    try:
        body = request.get_json(silent=True) or {}
        if not body:
            return _err('INVALID_REQUEST', 'body 不能为空', 400)

        ok, msg = _validate_status(body.get('status'))
        if not ok:
            return _err('INVALID_REQUEST', msg, 400)
        ok, msg = _validate_type(body.get('experiment_type'))
        if not ok:
            return _err('INVALID_REQUEST', msg, 400)
        ok, msg = _validate_config(body.get('config'))
        if not ok:
            return _err('INVALID_REQUEST', msg, 400)

        db = _get_db()
        if db is None:
            return _err('DB_UNAVAILABLE', '数据库未初始化', 503)

        from app.db.models import Experiment

        session = db.get_session()
        try:
            exp = session.query(Experiment).filter_by(id=exp_id).first()
            if not exp:
                exp = session.query(Experiment).filter_by(name=exp_id).first()
            if not exp:
                return _err('NOT_FOUND', f'experiment {exp_id} 不存在', 404)

            # 应用更新
            if 'description' in body:
                exp.description = body['description']
            if 'experiment_type' in body and body['experiment_type']:
                exp.experiment_type = body['experiment_type']
            if 'config' in body:
                exp.config = body['config'] or {}

            # status 转移 + 时间戳自动维护
            if 'status' in body and body['status'] and body['status'] != exp.status:
                new_status = body['status']
                old_status = exp.status
                exp.status = new_status
                if new_status == 'running' and not exp.started_at:
                    exp.started_at = datetime.utcnow()
                if new_status in ('completed', 'archived') and not exp.ended_at:
                    exp.ended_at = datetime.utcnow()
                logger.info("experiment %s status: %s → %s", exp.id, old_status, new_status)

            exp.updated_at = datetime.utcnow()
            session.commit()
            return jsonify({
                'success': True,
                'data': _serialize_experiment(exp),
            })
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error("update_experiment 失败: %s", e)
        return _err('UPDATE_FAILED', str(e), 500)


@experiment_api.route('/<exp_id>', methods=['DELETE'])
def delete_experiment(exp_id: str):
    """删除实验（不级联删除 ExperimentLog，保留历史事件流）"""
    try:
        db = _get_db()
        if db is None:
            return _err('DB_UNAVAILABLE', '数据库未初始化', 503)

        from app.db.models import Experiment, ExperimentLog

        session = db.get_session()
        try:
            exp = session.query(Experiment).filter_by(id=exp_id).first()
            if not exp:
                exp = session.query(Experiment).filter_by(name=exp_id).first()
            if not exp:
                return _err('NOT_FOUND', f'experiment {exp_id} 不存在', 404)

            # 统计关联的 log 数量（不删）
            log_count = session.query(ExperimentLog).filter_by(
                experiment_name=exp.name
            ).count()

            exp_id_ = exp.id
            exp_name_ = exp.name
            session.delete(exp)
            session.commit()
            logger.info(
                "删除 experiment id=%s name=%s（保留 %d 条 ExperimentLog 历史）",
                exp_id_, exp_name_, log_count,
            )
            return jsonify({
                'success': True,
                'data': {
                    'experiment_id': exp_id_,
                    'name': exp_name_,
                    'experiment_log_preserved': log_count,
                }
            })
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error("delete_experiment 失败: %s", e)
        return _err('DELETE_FAILED', str(e), 500)


@experiment_api.route('/<exp_id>/stats', methods=['GET'])
def get_experiment_stats(exp_id: str):
    """实验聚合统计

    聚合 ExperimentLog 数据，按 variant 分组：
      - impressions: 该 variant 的总曝光数
      - likes / dislikes / skips: 各类 rating 计数
      - like_rate: likes / impressions
      - avg_latency_ms: 平均延迟

    若 ExperimentLog 中没有该 experiment_name 的数据，会返回 zero-filled 模板（基于
    config.variants 列表），便于前端零状态展示。
    """
    try:
        db = _get_db()
        if db is None:
            return _err('DB_UNAVAILABLE', '数据库未初始化', 503)

        from app.db.models import Experiment, ExperimentLog
        from sqlalchemy import func

        session = db.get_session()
        try:
            exp = session.query(Experiment).filter_by(id=exp_id).first()
            if not exp:
                exp = session.query(Experiment).filter_by(name=exp_id).first()
            if not exp:
                return _err('NOT_FOUND', f'experiment {exp_id} 不存在', 404)

            # 真实聚合
            rows = (
                session.query(
                    ExperimentLog.variant,
                    ExperimentLog.rating,
                    func.count(ExperimentLog.id).label('cnt'),
                    func.avg(ExperimentLog.latency_ms).label('avg_latency'),
                )
                .filter(ExperimentLog.experiment_name == exp.name)
                .group_by(ExperimentLog.variant, ExperimentLog.rating)
                .all()
            )

            # 整理为 variant 维度的统计
            stats_by_variant: Dict[str, Dict[str, Any]] = {}
            total_impressions = 0
            for variant, rating, cnt, avg_latency in rows:
                if variant not in stats_by_variant:
                    stats_by_variant[variant] = {
                        'variant': variant,
                        'impressions': 0,
                        'likes': 0,
                        'dislikes': 0,
                        'skips': 0,
                        'avg_latency_ms': 0.0,
                        '_latency_weighted_sum': 0.0,
                    }
                bucket = stats_by_variant[variant]
                bucket['impressions'] += cnt
                total_impressions += cnt
                if rating == 'like':
                    bucket['likes'] += cnt
                elif rating == 'dislike':
                    bucket['dislikes'] += cnt
                elif rating == 'skip':
                    bucket['skips'] += cnt
                if avg_latency is not None:
                    bucket['_latency_weighted_sum'] += float(avg_latency) * cnt

            # 计算 like_rate 和 avg_latency
            for v in stats_by_variant.values():
                v['like_rate'] = round(v['likes'] / v['impressions'], 4) if v['impressions'] else 0.0
                v['avg_latency_ms'] = round(
                    v['_latency_weighted_sum'] / v['impressions'], 2
                ) if v['impressions'] else 0.0
                del v['_latency_weighted_sum']

            # 若 config.variants 里有但 logs 里没有，补 zero-filled
            cfg_variants = (exp.config or {}).get('variants') or []
            for cv in cfg_variants:
                cv_name = cv.get('name')
                if cv_name and cv_name not in stats_by_variant:
                    stats_by_variant[cv_name] = {
                        'variant': cv_name,
                        'impressions': 0,
                        'likes': 0,
                        'dislikes': 0,
                        'skips': 0,
                        'avg_latency_ms': 0.0,
                        'like_rate': 0.0,
                    }

            return jsonify({
                'success': True,
                'data': {
                    'experiment_id': exp.id,
                    'experiment_name': exp.name,
                    'status': exp.status,
                    'target_metric': (exp.config or {}).get('target_metric', 'positive_rate'),
                    'total_impressions': total_impressions,
                    'variants': list(stats_by_variant.values()),
                    'generated_at': _now_iso(),
                }
            })
        finally:
            session.close()
    except Exception as e:
        logger.error("get_experiment_stats 失败: %s", e)
        return _err('STATS_FAILED', str(e), 500)


def register_experiment_routes(app) -> None:
    """注册 experiment 路由蓝图到 Flask app

    被 backend/app/api/__init__.py:17-18 调用。
    """
    app.register_blueprint(experiment_api)
    logger.info("✓ experiment 路由已注册 (prefix=/api/v1/experiments)")
    return None
