"""提问建议路由"""
from flask import Blueprint, request, jsonify
from app.services.suggestion_engine import SuggestionEngine
import logging

logger = logging.getLogger(__name__)

suggestion_bp = Blueprint('suggestions', __name__, url_prefix='/api/v1')

_suggestion_engine = None


def init_suggestion_routes(db, Message, Feedback=None, game_type: str = 'ocg'):
    """初始化建议路由

    Args:
        db: 数据库实例
        Message: Message 模型
        Feedback: Feedback 模型（可选）
        game_type: 游戏类型
    """
    global _suggestion_engine
    _suggestion_engine = SuggestionEngine(db, Message, Feedback)
    _suggestion_engine.game_type = game_type

    suggestion_bp.route('/suggestions', methods=['GET'])(get_suggestions)
    suggestion_bp.route('/suggestions/categories', methods=['GET'])(get_category_suggestions)
    suggestion_bp.route('/suggestions/personalized', methods=['GET'])(get_personalized_suggestions)

    return suggestion_bp


def get_suggestions():
    """获取热门问题建议

    Query Parameters:
        category: 分类过滤（规则类/概念类/操作类）
        limit: 返回数量限制（默认10）
        days: 统计时间范围（默认30天）
        game_type: 游戏类型（ocg/dm）

    Returns:
        [{question, category, frequency, relevance_score}]
    """
    try:
        category = request.args.get('category', '')
        limit = request.args.get('limit', 10, type=int)
        days = request.args.get('days', 30, type=int)
        game_type = request.args.get('game_type', getattr(_suggestion_engine, 'game_type', 'ocg'))

        if limit > 50:
            limit = 50
        if days > 90:
            days = 90

        suggestions = _suggestion_engine.get_hot_questions(
            game_type=game_type,
            category=category if category else None,
            limit=limit,
            days=days
        )

        if not suggestions:
            suggestions = _suggestion_engine.get_default_suggestions(
                game_type=game_type,
                limit=limit
            )

        return jsonify({
            'success': True,
            'data': {
                'suggestions': suggestions,
                'total': len(suggestions),
                'category': category or 'all',
                'game_type': game_type
            }
        })

    except Exception as e:
        logger.error(f"Get suggestions error: {e}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': str(e)}
        }), 500


def get_category_suggestions():
    """获取各分类的热门问题建议

    Query Parameters:
        limit: 每个分类的返回数量（默认5）
        game_type: 游戏类型

    Returns:
        {category: [suggestions]}
    """
    try:
        limit = request.args.get('limit', 5, type=int)
        game_type = request.args.get('game_type', getattr(_suggestion_engine, 'game_type', 'ocg'))

        if limit > 20:
            limit = 20

        suggestions = _suggestion_engine.get_category_suggestions(
            game_type=game_type,
            limit_per_category=limit
        )

        return jsonify({
            'success': True,
            'data': {
                'categories': suggestions,
                'game_type': game_type
            }
        })

    except Exception as e:
        logger.error(f"Get category suggestions error: {e}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': str(e)}
        }), 500


def get_personalized_suggestions():
    """获取个性化建议

    Query Parameters:
        conversation_id: 用户对话ID
        limit: 返回数量（默认5）
        game_type: 游戏类型

    Returns:
        个性化建议列表
    """
    try:
        conversation_id = request.args.get('conversation_id', '')
        limit = request.args.get('limit', 5, type=int)
        game_type = request.args.get('game_type', getattr(_suggestion_engine, 'game_type', 'ocg'))

        if not conversation_id:
            return jsonify({
                'success': False,
                'error': {'code': 'MISSING_PARAM', 'message': 'conversation_id 不能为空'}
            }), 400

        if limit > 20:
            limit = 20

        suggestions = _suggestion_engine.get_personalized_suggestions(
            conversation_id=conversation_id,
            game_type=game_type,
            limit=limit
        )

        return jsonify({
            'success': True,
            'data': {
                'suggestions': suggestions,
                'total': len(suggestions),
                'conversation_id': conversation_id
            }
        })

    except Exception as e:
        logger.error(f"Get personalized suggestions error: {e}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': str(e)}
        }), 500
