"""
Advanced Features API Routes - 暴露新功能接口

整合分层RAG、增强记忆、高级路由、工具系统等新功能到API。
"""

from flask import Blueprint, request, jsonify
from app.services.service_manager import get_unified_manager
import logging
import time
import uuid

logger = logging.getLogger(__name__)

advanced_api = Blueprint('advanced_api', __name__, url_prefix='/api/v1/advanced')


def init_advanced_services():
    """初始化高级服务"""
    try:
        manager = get_unified_manager()
        config = {
            'hierarchical_rag_dir': './data/hierarchical',
            'hierarchical_collection': 'unified_hierarchical',
            'max_short_term': 100,
            'max_long_term': 1000,
            'memory_ttl': 3600,
            'embedding_model': 'text2vec',
            'enable_feedback': True,
            'default_chunking': 'adaptive'
        }
        manager.initialize(config)
        logger.info("✓ 高级服务已初始化")
        return True
    except Exception as e:
        logger.error(f"高级服务初始化失败: {e}")
        return False


def register_advanced_routes():
    """注册高级功能路由"""
    init_advanced_services()

    @advanced_api.route('/health', methods=['GET'])
    def health_check():
        """高级服务健康检查"""
        manager = get_unified_manager()
        try:
            status = manager.get_system_status()
            return jsonify({
                'success': True,
                'data': status
            })
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'HEALTH_CHECK_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/query/unified', methods=['POST'])
    def unified_query():
        """
        统一查询接口 - 整合路由、记忆、RAG的完整流程

        请求体:
        {
            "query": "用户问题",
            "user_id": "可选的用户ID",
            "enable_memory": true,
            "enable_hierarchical": true
        }
        """
        start_time = time.time()
        data = request.get_json(silent=True) or {}

        if not data or not data.get('query'):
            return jsonify({
                'success': False,
                'error': {'code': 'EMPTY_QUERY', 'message': '查询不能为空'}
            }), 400

        query = data.get('query')
        user_id = data.get('user_id')
        enable_memory = data.get('enable_memory', True)
        enable_hierarchical = data.get('enable_hierarchical', True)

        try:
            manager = get_unified_manager()
            result = manager.query_with_routing(
                query=query,
                user_id=user_id,
                enable_memory=enable_memory,
                enable_hierarchical=enable_hierarchical
            )

            response_time = int((time.time() - start_time) * 1000)

            return jsonify({
                'success': True,
                'data': {
                    'query': result.get('query'),
                    'route': result.get('route'),
                    'memory_context': result.get('memory_context'),
                    'retrieved_docs': result.get('retrieved_docs'),
                    'answer': result.get('answer'),
                    'metadata': {
                        'response_time_ms': response_time,
                        'memory_enabled': enable_memory,
                        'hierarchical_enabled': enable_hierarchical
                    }
                }
            })

        except Exception as e:
            logger.error(f"统一查询失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'QUERY_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/memory/add', methods=['POST'])
    def add_memory():
        """
        添加记忆

        请求体:
        {
            "content": "记忆内容",
            "memory_type": "episodic|factual|semantic|working",
            "importance": 0.5,
            "tags": ["标签1", "标签2"],
            "user_id": "可选的用户ID"
        }
        """
        data = request.get_json(silent=True) or {}

        if not data or not data.get('content'):
            return jsonify({
                'success': False,
                'error': {'code': 'EMPTY_CONTENT', 'message': '记忆内容不能为空'}
            }), 400

        try:
            manager = get_unified_manager()
            memory_id = manager.add_memory(
                content=data.get('content'),
                memory_type=data.get('memory_type', 'episodic'),
                importance=data.get('importance', 0.5),
                tags=data.get('tags'),
                user_id=data.get('user_id')
            )

            return jsonify({
                'success': True,
                'data': {
                    'memory_id': memory_id,
                    'message': '记忆添加成功'
                }
            })

        except Exception as e:
            logger.error(f"添加记忆失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'ADD_MEMORY_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/memory/retrieve', methods=['GET'])
    def retrieve_memory():
        """
        检索记忆

        查询参数:
        - query: 检索查询
        - limit: 返回数量（默认5）
        """
        query = request.args.get('query', '')
        limit = request.args.get('limit', 5, type=int)

        if not query:
            return jsonify({
                'success': False,
                'error': {'code': 'EMPTY_QUERY', 'message': '查询不能为空'}
            }), 400

        try:
            manager = get_unified_manager()
            if not manager.memory_retriever:
                return jsonify({
                    'success': False,
                    'error': {'code': 'MEMORY_NOT_INITIALIZED', 'message': '记忆系统未初始化'}
                }), 503

            memories = manager.memory_retriever.retrieve(query, limit=limit)
            result = [
                {
                    'memory_id': m.memory.id,
                    'content': m.memory.content,
                    'score': m.score,
                    'type': m.memory.memory_type.value,
                    'importance': m.memory.importance
                }
                for m in memories
            ]

            return jsonify({
                'success': True,
                'data': {
                    'memories': result,
                    'count': len(result)
                }
            })

        except Exception as e:
            logger.error(f"检索记忆失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'RETRIEVE_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/memory/stats', methods=['GET'])
    def memory_stats():
        """获取记忆统计"""
        try:
            manager = get_unified_manager()
            if not manager.memory_system:
                return jsonify({
                    'success': False,
                    'error': {'code': 'MEMORY_NOT_INITIALIZED', 'message': '记忆系统未初始化'}
                }), 503

            stats = manager.memory_system.get_memory_stats()

            return jsonify({
                'success': True,
                'data': stats
            })

        except Exception as e:
            logger.error(f"获取记忆统计失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'STATS_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/routing/route', methods=['POST'])
    def route_query():
        """
        路由查询

        请求体:
        {
            "query": "用户问题"
        }
        """
        data = request.get_json(silent=True) or {}

        if not data or not data.get('query'):
            return jsonify({
                'success': False,
                'error': {'code': 'EMPTY_QUERY', 'message': '查询不能为空'}
            }), 400

        try:
            manager = get_unified_manager()
            if not manager.advanced_router:
                return jsonify({
                    'success': False,
                    'error': {'code': 'ROUTING_NOT_INITIALIZED', 'message': '路由系统未初始化'}
                }), 503

            route_result = manager.advanced_router.route(data.get('query'))

            return jsonify({
                'success': True,
                'data': {
                    'selected_route': route_result.selected_route,
                    'strategy': route_result.strategy_used.value,
                    'confidence': route_result.confidence,
                    'all_scores': route_result.all_scores if hasattr(route_result, 'all_scores') else {}
                }
            })

        except Exception as e:
            logger.error(f"路由查询失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'ROUTE_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/routing/routes', methods=['GET'])
    def list_routes():
        """列出所有可用路由"""
        try:
            manager = get_unified_manager()
            if not manager.semantic_router:
                return jsonify({
                    'success': False,
                    'error': {'code': 'ROUTING_NOT_INITIALIZED', 'message': '路由系统未初始化'}
                }), 503

            routes = manager.semantic_router.list_routes()

            return jsonify({
                'success': True,
                'data': {
                    'routes': routes,
                    'count': len(routes)
                }
            })

        except Exception as e:
            logger.error(f"列出路由失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'LIST_ROUTES_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/routing/routes', methods=['POST'])
    def add_route():
        """
        添加新路由

        请求体:
        {
            "name": "路由名称",
            "description": "路由描述",
            "examples": ["例子1", "例子2"],
            "keywords": ["关键词1", "关键词2"]
        }
        """
        data = request.get_json(silent=True) or {}

        if not data or not data.get('name'):
            return jsonify({
                'success': False,
                'error': {'code': 'INVALID_ROUTE', 'message': '路由名称不能为空'}
            }), 400

        try:
            manager = get_unified_manager()
            if not manager.semantic_router:
                return jsonify({
                    'success': False,
                    'error': {'code': 'ROUTING_NOT_INITIALIZED', 'message': '路由系统未初始化'}
                }), 503

            manager.semantic_router.add_route(
                name=data.get('name'),
                description=data.get('description', ''),
                examples=data.get('examples', []),
                keywords=data.get('keywords', [])
            )

            return jsonify({
                'success': True,
                'data': {
                    'message': '路由添加成功',
                    'route_name': data.get('name')
                }
            })

        except Exception as e:
            logger.error(f"添加路由失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'ADD_ROUTE_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/rag/search', methods=['GET'])
    def rag_search():
        """
        分层RAG搜索

        查询参数:
        - query: 搜索查询
        - top_k: 返回数量（默认5）
        - parent_top_k: 父块搜索数量（默认10）
        """
        query = request.args.get('query', '')
        top_k = request.args.get('top_k', 5, type=int)
        parent_top_k = request.args.get('parent_top_k', 10, type=int)

        if not query:
            return jsonify({
                'success': False,
                'error': {'code': 'EMPTY_QUERY', 'message': '查询不能为空'}
            }), 400

        try:
            manager = get_unified_manager()
            if not manager.hierarchical_rag:
                return jsonify({
                    'success': False,
                    'error': {'code': 'RAG_NOT_INITIALIZED', 'message': '分层RAG未初始化'}
                }), 503

            docs = manager.hierarchical_rag.search(
                query=query,
                top_k=top_k,
                parent_top_k=parent_top_k
            )

            result = [
                {
                    'chunk_id': d.chunk_id,
                    'content': d.content[:500] + '...' if len(d.content) > 500 else d.content,
                    'score': d.score,
                    'metadata': d.metadata,
                    'parent_id': d.parent_id if hasattr(d, 'parent_id') else None
                }
                for d in docs
            ]

            return jsonify({
                'success': True,
                'data': {
                    'results': result,
                    'count': len(result),
                    'query': query
                }
            })

        except Exception as e:
            logger.error(f"RAG搜索失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'SEARCH_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/rag/stats', methods=['GET'])
    def rag_stats():
        """获取RAG统计信息"""
        try:
            manager = get_unified_manager()
            if not manager.hierarchical_rag:
                return jsonify({
                    'success': False,
                    'error': {'code': 'RAG_NOT_INITIALIZED', 'message': '分层RAG未初始化'}
                }), 503

            stats = manager.hierarchical_rag.get_collection_stats()

            return jsonify({
                'success': True,
                'data': stats
            })

        except Exception as e:
            logger.error(f"获取RAG统计失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'STATS_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/tools/list', methods=['GET'])
    def list_tools():
        """列出所有可用工具"""
        try:
            manager = get_unified_manager()
            if not manager.tool_registry:
                return jsonify({
                    'success': False,
                    'error': {'code': 'TOOLS_NOT_INITIALIZED', 'message': '工具系统未初始化'}
                }), 503

            tools = manager.tool_registry.list_tools()

            return jsonify({
                'success': True,
                'data': {
                    'tools': tools,
                    'count': len(tools)
                }
            })

        except Exception as e:
            logger.error(f"列出工具失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'LIST_TOOLS_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/tools/execute', methods=['POST'])
    def execute_tool():
        """
        执行工具

        请求体:
        {
            "tool_name": "工具名称",
            "parameters": {"param1": "value1"}
        }
        """
        data = request.get_json(silent=True) or {}

        if not data or not data.get('tool_name'):
            return jsonify({
                'success': False,
                'error': {'code': 'INVALID_TOOL', 'message': '工具名称不能为空'}
            }), 400

        try:
            manager = get_unified_manager()
            if not manager.tool_registry:
                return jsonify({
                    'success': False,
                    'error': {'code': 'TOOLS_NOT_INITIALIZED', 'message': '工具系统未初始化'}
                }), 503

            tool_name = data.get('tool_name')
            parameters = data.get('parameters', {})

            tool = manager.tool_registry.get_tool(tool_name)
            if not tool:
                return jsonify({
                    'success': False,
                    'error': {'code': 'TOOL_NOT_FOUND', 'message': f'工具 {tool_name} 不存在'}
                }), 404

            result = tool.execute(**parameters)

            return jsonify({
                'success': True,
                'data': {
                    'tool_name': tool_name,
                    'result': result,
                    'parameters': parameters
                }
            })

        except Exception as e:
            logger.error(f"执行工具失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'EXECUTE_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/chunking/strategy', methods=['GET'])
    def get_chunking_strategy():
        """获取当前分块策略"""
        try:
            manager = get_unified_manager()
            if not manager.chunking_system:
                return jsonify({
                    'success': False,
                    'error': {'code': 'CHUNKING_NOT_INITIALIZED', 'message': '分块系统未初始化'}
                }), 503

            strategy = manager.chunking_system.get_current_strategy()
            available = manager.chunking_system.list_strategies()

            return jsonify({
                'success': True,
                'data': {
                    'current_strategy': strategy,
                    'available_strategies': available
                }
            })

        except Exception as e:
            logger.error(f"获取分块策略失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'GET_STRATEGY_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/chunking/chunk', methods=['POST'])
    def chunk_text():
        """
        分块文本

        请求体:
        {
            "text": "要分块的文本",
            "strategy": "adaptive|recursive|title|sentence",
            "max_chunk_size": 500
        }
        """
        data = request.get_json(silent=True) or {}

        if not data or not data.get('text'):
            return jsonify({
                'success': False,
                'error': {'code': 'EMPTY_TEXT', 'message': '文本不能为空'}
            }), 400

        try:
            manager = get_unified_manager()
            if not manager.chunking_system:
                return jsonify({
                    'success': False,
                    'error': {'code': 'CHUNKING_NOT_INITIALIZED', 'message': '分块系统未初始化'}
                }), 503

            text = data.get('text')
            strategy = data.get('strategy', 'adaptive')
            max_chunk_size = data.get('max_chunk_size', 500)

            chunks = manager.chunking_system.chunk_text(
                text=text,
                strategy=strategy,
                max_chunk_size=max_chunk_size
            )

            return jsonify({
                'success': True,
                'data': {
                    'chunks': chunks,
                    'count': len(chunks),
                    'strategy': strategy
                }
            })

        except Exception as e:
            logger.error(f"分块失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'CHUNK_FAILED', 'message': str(e)}
            }), 500

    @advanced_api.route('/status', methods=['GET'])
    def system_status():
        """获取完整系统状态"""
        try:
            manager = get_unified_manager()
            status = manager.get_system_status()

            return jsonify({
                'success': True,
                'data': status
            })

        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return jsonify({
                'success': False,
                'error': {'code': 'STATUS_FAILED', 'message': str(e)}
            }), 500

    logger.info("✓ 高级功能路由已注册")
    return advanced_api
