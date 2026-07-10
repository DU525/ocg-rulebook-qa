"""
Feedback 管理端 API（admin 视角的反馈管理）

设计说明：
- base_routes.py:87-90 已经实现 4 个 user-facing feedback 端点（POST /feedback、GET /feedback/<id>、
  GET /feedback/stats、GET /feedback/negative-samples），挂在 /api/v1 前缀的 api blueprint 上。
- 本文件专注于 admin 视角的反馈管理：分页列表、详情查看、删除、聚合分析、批量操作、CSV 导出。
  所有端点使用独立 url_prefix='/api/v1/feedback-admin'，避免与 user-facing 端点冲突。
- 不引入新的鉴权（与项目其他 admin 接口一致），后续可挂 @admin_required 装饰器。

端点清单：
  GET    /api/v1/feedback-admin/list              分页列出反馈（支持 rating/reason/keyword 过滤）
  GET    /api/v1/feedback-admin/<feedback_id>     反馈详情
  DELETE /api/v1/feedback-admin/<feedback_id>     删除单条反馈（同时级联删除关联的 negative_sample）
  POST   /api/v1/feedback-admin/bulk-delete       批量删除
  GET    /api/v1/feedback-admin/analytics/summary 反馈聚合分析（按 rating/reason/天 维度）
  GET    /api/v1/feedback-admin/export            导出 CSV
"""
import csv
import io
import logging
from collections import Counter
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, Response

from app.db.models import Feedback, NegativeSample

logger = logging.getLogger(__name__)

feedback_admin_api = Blueprint(
    'feedback_admin_api',
    __name__,
    url_prefix='/api/v1/feedback-admin',
)


def _get_db():
    """惰性获取 db 实例（避免循环 import）"""
    try:
        from app.api import get_services
        # 优先使用 OCG 服务（base_routes 初始化过的那个）
        vector_store, rag_engine, db, *_ = get_services()
        return db
    except Exception as e:
        logger.warning("feedback_admin 无法获取 db: %s", e)
        return None


def _serialize_feedback(fb: Feedback) -> dict:
    return {
        'id': fb.id,
        'message_id': fb.message_id,
        'conversation_id': fb.conversation_id,
        'rating': fb.rating,
        'reason': fb.reason,
        'feedback_text': fb.feedback_text,
        'game_type': fb.game_type,
        'created_at': fb.created_at.isoformat() if fb.created_at else None,
    }


@feedback_admin_api.route('/list', methods=['GET'])
def list_feedbacks():
    """分页列出 feedback

    Query:
      page: 页码（默认 1）
      page_size: 每页数量（默认 20，最大 100）
      rating: positive/negative 过滤
      reason: 过滤具体原因（如 answer_inaccurate）
      keyword: 在 feedback_text 中模糊搜索
      days: 限定最近 N 天（默认全部）
    """
    try:
        db = _get_db()
        if db is None:
            return jsonify({
                'success': False,
                'error': {'code': 'DB_UNAVAILABLE', 'message': '数据库未初始化'}
            }), 503

        page = max(1, request.args.get('page', 1, type=int))
        page_size = min(100, max(1, request.args.get('page_size', 20, type=int)))
        rating = request.args.get('rating', '').strip()
        reason = request.args.get('reason', '').strip()
        keyword = request.args.get('keyword', '').strip()
        days = request.args.get('days', type=int)

        session = db.get_session()
        try:
            q = session.query(Feedback)
            if rating in ('positive', 'negative'):
                q = q.filter(Feedback.rating == rating)
            if reason:
                q = q.filter(Feedback.reason == reason)
            if keyword:
                like = f'%{keyword}%'
                q = q.filter(Feedback.feedback_text.like(like))
            if days and days > 0:
                cutoff = datetime.utcnow() - timedelta(days=days)
                q = q.filter(Feedback.created_at >= cutoff)

            total = q.count()
            items = (
                q.order_by(Feedback.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return jsonify({
                'success': True,
                'data': {
                    'items': [_serialize_feedback(fb) for fb in items],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size if total else 0,
                    }
                }
            })
        finally:
            session.close()
    except Exception as e:
        logger.error("list_feedbacks 失败: %s", e)
        return jsonify({
            'success': False,
            'error': {'code': 'LIST_FAILED', 'message': str(e)}
        }), 500


@feedback_admin_api.route('/<feedback_id>', methods=['GET'])
def get_feedback_detail(feedback_id: str):
    """反馈详情"""
    try:
        db = _get_db()
        if db is None:
            return jsonify({
                'success': False,
                'error': {'code': 'DB_UNAVAILABLE', 'message': '数据库未初始化'}
            }), 503

        session = db.get_session()
        try:
            fb = session.query(Feedback).filter_by(id=feedback_id).first()
            if not fb:
                return jsonify({
                    'success': False,
                    'error': {'code': 'NOT_FOUND', 'message': f'feedback {feedback_id} 不存在'}
                }), 404

            # 关联 negative sample（如果有）
            ns = session.query(NegativeSample).filter_by(feedback_id=feedback_id).first()
            data = _serialize_feedback(fb)
            data['negative_sample'] = {
                'id': ns.id,
                'question': ns.question,
                'answer': ns.answer,
                'reason': ns.reason,
                'created_at': ns.created_at.isoformat() if ns.created_at else None,
            } if ns else None
            return jsonify({'success': True, 'data': data})
        finally:
            session.close()
    except Exception as e:
        logger.error("get_feedback_detail 失败: %s", e)
        return jsonify({
            'success': False,
            'error': {'code': 'GET_FAILED', 'message': str(e)}
        }), 500


@feedback_admin_api.route('/<feedback_id>', methods=['DELETE'])
def delete_feedback(feedback_id: str):
    """删除单条 feedback（级联删除关联的 negative_sample）"""
    try:
        db = _get_db()
        if db is None:
            return jsonify({
                'success': False,
                'error': {'code': 'DB_UNAVAILABLE', 'message': '数据库未初始化'}
            }), 503

        session = db.get_session()
        try:
            fb = session.query(Feedback).filter_by(id=feedback_id).first()
            if not fb:
                return jsonify({
                    'success': False,
                    'error': {'code': 'NOT_FOUND', 'message': f'feedback {feedback_id} 不存在'}
                }), 404

            # 先级联删除 negative_sample
            ns_count = session.query(NegativeSample).filter_by(feedback_id=feedback_id).delete()
            session.delete(fb)
            session.commit()
            logger.info("删除 feedback %s（连带 %d 条 negative_sample）", feedback_id, ns_count)
            return jsonify({
                'success': True,
                'data': {
                    'feedback_id': feedback_id,
                    'negative_sample_deleted': ns_count,
                }
            })
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error("delete_feedback 失败: %s", e)
        return jsonify({
            'success': False,
            'error': {'code': 'DELETE_FAILED', 'message': str(e)}
        }), 500


@feedback_admin_api.route('/bulk-delete', methods=['POST'])
def bulk_delete_feedbacks():
    """批量删除 feedback

    Body: {"feedback_ids": ["id1", "id2", ...]}
    """
    try:
        body = request.get_json(silent=True) or {}
        ids = body.get('feedback_ids', [])
        if not isinstance(ids, list) or not ids:
            return jsonify({
                'success': False,
                'error': {'code': 'INVALID_REQUEST', 'message': 'feedback_ids 必须是非空数组'}
            }), 400

        db = _get_db()
        if db is None:
            return jsonify({
                'success': False,
                'error': {'code': 'DB_UNAVAILABLE', 'message': '数据库未初始化'}
            }), 503

        session = db.get_session()
        try:
            # 先删 negative_sample
            ns_count = session.query(NegativeSample).filter(NegativeSample.feedback_id.in_(ids)).delete(synchronize_session=False)
            fb_count = session.query(Feedback).filter(Feedback.id.in_(ids)).delete(synchronize_session=False)
            session.commit()
            logger.info("批量删除 %d 条 feedback（连带 %d 条 negative_sample）", fb_count, ns_count)
            return jsonify({
                'success': True,
                'data': {
                    'feedback_deleted': fb_count,
                    'negative_sample_deleted': ns_count,
                    'requested': len(ids),
                }
            })
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error("bulk_delete_feedbacks 失败: %s", e)
        return jsonify({
            'success': False,
            'error': {'code': 'BULK_DELETE_FAILED', 'message': str(e)}
        }), 500


@feedback_admin_api.route('/analytics/summary', methods=['GET'])
def feedback_analytics_summary():
    """反馈聚合分析

    Query:
      days: 限定最近 N 天（默认 30）

    Returns:
      total / positive_count / negative_count / positive_rate
      reason_distribution: 差评原因计数
      daily_trend: [{date, positive, negative}, ...]
    """
    try:
        db = _get_db()
        if db is None:
            return jsonify({
                'success': False,
                'error': {'code': 'DB_UNAVAILABLE', 'message': '数据库未初始化'}
            }), 503

        days = request.args.get('days', 30, type=int)
        days = min(365, max(1, days))

        session = db.get_session()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            q = session.query(Feedback).filter(Feedback.created_at >= cutoff)

            total = q.count()
            positive = q.filter(Feedback.rating == 'positive').count()
            negative = q.filter(Feedback.rating == 'negative').count()

            # 差评原因分布（仅统计有 reason 的）
            neg_with_reason = (
                session.query(Feedback.reason)
                .filter(Feedback.created_at >= cutoff, Feedback.rating == 'negative')
                .filter(Feedback.reason.isnot(None))
                .filter(Feedback.reason != '')
                .all()
            )
            reason_counter = Counter([r[0] for r in neg_with_reason])
            reason_distribution = [
                {'reason': k, 'count': v} for k, v in reason_counter.most_common()
            ]

            # 每日趋势（按天聚合 positive/negative）
            all_in_range = (
                session.query(Feedback.rating, Feedback.created_at)
                .filter(Feedback.created_at >= cutoff)
                .all()
            )
            daily = {}
            for rating, created_at in all_in_range:
                if not created_at:
                    continue
                key = created_at.strftime('%Y-%m-%d')
                if key not in daily:
                    daily[key] = {'date': key, 'positive': 0, 'negative': 0}
                if rating == 'positive':
                    daily[key]['positive'] += 1
                elif rating == 'negative':
                    daily[key]['negative'] += 1
            daily_trend = sorted(daily.values(), key=lambda x: x['date'])

            return jsonify({
                'success': True,
                'data': {
                    'days': days,
                    'total': total,
                    'positive_count': positive,
                    'negative_count': negative,
                    'positive_rate': round(positive / total, 4) if total else 0.0,
                    'reason_distribution': reason_distribution,
                    'daily_trend': daily_trend,
                }
            })
        finally:
            session.close()
    except Exception as e:
        logger.error("feedback_analytics_summary 失败: %s", e)
        return jsonify({
            'success': False,
            'error': {'code': 'ANALYTICS_FAILED', 'message': str(e)}
        }), 500


@feedback_admin_api.route('/export', methods=['GET'])
def export_feedbacks():
    """导出 feedback 为 CSV

    Query:
      rating: positive/negative 过滤
      days: 限定最近 N 天
      max_rows: 限制最多导出条数（默认 10000）
    """
    try:
        db = _get_db()
        if db is None:
            return jsonify({
                'success': False,
                'error': {'code': 'DB_UNAVAILABLE', 'message': '数据库未初始化'}
            }), 503

        rating = request.args.get('rating', '').strip()
        days = request.args.get('days', type=int)
        max_rows = min(50000, max(1, request.args.get('max_rows', 10000, type=int)))

        session = db.get_session()
        try:
            q = session.query(Feedback)
            if rating in ('positive', 'negative'):
                q = q.filter(Feedback.rating == rating)
            if days and days > 0:
                cutoff = datetime.utcnow() - timedelta(days=days)
                q = q.filter(Feedback.created_at >= cutoff)

            items = q.order_by(Feedback.created_at.desc()).limit(max_rows).all()

            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(['id', 'message_id', 'conversation_id', 'rating', 'reason', 'feedback_text', 'game_type', 'created_at'])
            for fb in items:
                writer.writerow([
                    fb.id,
                    fb.message_id,
                    fb.conversation_id or '',
                    fb.rating,
                    fb.reason or '',
                    (fb.feedback_text or '').replace('\n', ' ').replace('\r', ' '),
                    fb.game_type or '',
                    fb.created_at.isoformat() if fb.created_at else '',
                ])

            csv_text = buf.getvalue()
            filename = f'feedbacks_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
            return Response(
                csv_text,
                mimetype='text/csv; charset=utf-8',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'},
            )
        finally:
            session.close()
    except Exception as e:
        logger.error("export_feedbacks 失败: %s", e)
        return jsonify({
            'success': False,
            'error': {'code': 'EXPORT_FAILED', 'message': str(e)}
        }), 500


def register_feedback_routes(app):
    """注册 feedback-admin 路由蓝图到 Flask app

    被 backend/app/api/__init__.py:14-15 调用。
    """
    app.register_blueprint(feedback_admin_api)
    logger.info("✓ feedback_admin 路由已注册 (prefix=/api/v1/feedback-admin)")
    return feedback_admin_api
