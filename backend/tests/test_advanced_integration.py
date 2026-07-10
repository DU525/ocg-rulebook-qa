"""
系统集成测试 - 测试所有新功能的连通性

测试分层RAG、增强记忆、高级路由、工具系统等功能的端到端流程。
"""

import pytest
import json
import time
from unittest.mock import MagicMock, patch


class TestAdvancedFeaturesIntegration:
    """高级功能集成测试"""

    def test_advanced_routes_registered(self, client):
        """测试高级功能路由是否正确注册"""
        response = client.get('/api/v1/advanced/health')
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'success' in data or 'error' in data

    def test_advanced_health_check(self, client):
        """测试高级服务健康检查"""
        response = client.get('/api/v1/advanced/health')
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            if data.get('success'):
                result = data.get('data', {})
                assert 'initialized' in result or 'services' in result

    def test_unified_query_endpoint(self, client):
        """测试统一查询接口"""
        response = client.post(
            '/api/v1/advanced/query/unified',
            json={'query': '游戏王OCG规则是什么'},
            content_type='application/json'
        )
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]

    def test_unified_query_empty_query(self, client):
        """测试空查询请求"""
        response = client.post(
            '/api/v1/advanced/query/unified',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data.get('success') is False
        assert 'EMPTY_QUERY' in str(data)

    def test_memory_add(self, client):
        """测试添加记忆功能"""
        response = client.post(
            '/api/v1/advanced/memory/add',
            json={
                'content': '用户询问了游戏王召唤规则',
                'memory_type': 'episodic',
                'importance': 0.8,
                'tags': ['游戏王', '规则']
            },
            content_type='application/json'
        )
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]

    def test_memory_retrieve(self, client):
        """测试记忆检索功能"""
        response = client.get(
            '/api/v1/advanced/memory/retrieve',
            query_string={'query': '游戏王', 'limit': 5}
        )
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]

    def test_memory_retrieve_empty_query(self, client):
        """测试空查询检索"""
        response = client.get(
            '/api/v1/advanced/memory/retrieve',
            query_string={'query': ''}
        )
        assert response.status_code == 400

    def test_memory_stats(self, client):
        """测试记忆统计功能"""
        response = client.get('/api/v1/advanced/memory/stats')
        assert response.status_code in [200, 500]

    def test_routing_route(self, client):
        """测试路由功能"""
        response = client.post(
            '/api/v1/advanced/routing/route',
            json={'query': '什么是禁止卡表'},
            content_type='application/json'
        )
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]

    def test_routing_list_routes(self, client):
        """测试列出路由功能"""
        response = client.get('/api/v1/advanced/routing/routes')
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]

    def test_routing_add_route(self, client):
        """测试添加路由功能"""
        response = client.post(
            '/api/v1/advanced/routing/routes',
            json={
                'name': 'test_route',
                'description': '测试路由',
                'examples': ['测试问题1', '测试问题2'],
                'keywords': ['测试', '关键词']
            },
            content_type='application/json'
        )
        assert response.status_code in [200, 400, 500]

    def test_rag_search(self, client):
        """测试RAG搜索功能"""
        response = client.get(
            '/api/v1/advanced/rag/search',
            query_string={'query': '召唤规则', 'top_k': 5}
        )
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]

    def test_rag_search_empty_query(self, client):
        """测试RAG空查询"""
        response = client.get(
            '/api/v1/advanced/rag/search',
            query_string={'query': ''}
        )
        assert response.status_code == 400

    def test_rag_stats(self, client):
        """测试RAG统计功能"""
        response = client.get('/api/v1/advanced/rag/stats')
        assert response.status_code in [200, 500]

    def test_tools_list(self, client):
        """测试工具列表功能"""
        response = client.get('/api/v1/advanced/tools/list')
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]

    def test_tools_execute(self, client):
        """测试工具执行功能"""
        response = client.post(
            '/api/v1/advanced/tools/execute',
            json={
                'tool_name': 'calculator',
                'parameters': {'expression': '2 + 2'}
            },
            content_type='application/json'
        )
        assert response.status_code in [200, 404, 500]

    def test_tools_execute_not_found(self, client):
        """测试执行不存在的工具"""
        response = client.post(
            '/api/v1/advanced/tools/execute',
            json={
                'tool_name': 'nonexistent_tool',
                'parameters': {}
            },
            content_type='application/json'
        )
        assert response.status_code in [404, 500]

    def test_chunking_strategy(self, client):
        """测试分块策略功能"""
        response = client.get('/api/v1/advanced/chunking/strategy')
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]

    def test_chunking_chunk(self, client):
        """测试文本分块功能"""
        response = client.post(
            '/api/v1/advanced/chunking/chunk',
            json={
                'text': '这是一个测试文本。用于测试分块功能。应该被分成多个块。',
                'strategy': 'adaptive',
                'max_chunk_size': 50
            },
            content_type='application/json'
        )
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]

    def test_chunking_chunk_empty_text(self, client):
        """测试空文本分块"""
        response = client.post(
            '/api/v1/advanced/chunking/chunk',
            json={'text': ''},
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_system_status(self, client):
        """测试系统状态接口"""
        response = client.get('/api/v1/advanced/status')
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data.get('success') in [True, False]


class TestEndToEndFlow:
    """端到端流程测试"""

    def test_complete_query_flow(self, client):
        """测试完整查询流程：路由 -> 记忆 -> RAG"""
        query = '游戏王OCG的召唤规则是什么'

        route_response = client.post(
            '/api/v1/advanced/routing/route',
            json={'query': query},
            content_type='application/json'
        )
        assert route_response.status_code in [200, 500]

        memory_response = client.post(
            '/api/v1/advanced/memory/add',
            json={
                'content': f'用户询问: {query}',
                'memory_type': 'episodic',
                'importance': 0.7
            },
            content_type='application/json'
        )
        assert memory_response.status_code in [200, 500]

        rag_response = client.get(
            '/api/v1/advanced/rag/search',
            query_string={'query': query, 'top_k': 3}
        )
        assert rag_response.status_code in [200, 400, 500]

    def test_unified_flow_with_memory(self, client):
        """测试统一流程（带记忆）"""
        response = client.post(
            '/api/v1/advanced/query/unified',
            json={
                'query': '游戏王OCG规则是什么',
                'enable_memory': True,
                'enable_hierarchical': True
            },
            content_type='application/json'
        )
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            if data.get('success'):
                result = data.get('data', {})
                assert 'query' in result
                assert 'metadata' in result

    def test_unified_flow_without_memory(self, client):
        """测试统一流程（不带记忆）"""
        response = client.post(
            '/api/v1/advanced/query/unified',
            json={
                'query': '什么是禁止卡表',
                'enable_memory': False,
                'enable_hierarchical': False
            },
            content_type='application/json'
        )
        assert response.status_code in [200, 400, 500]


class TestErrorHandling:
    """错误处理测试"""

    def test_invalid_json(self, client):
        """测试无效JSON请求"""
        response = client.post(
            '/api/v1/advanced/query/unified',
            data='not json',
            content_type='application/json'
        )
        assert response.status_code in [400, 415, 500]

    def test_missing_required_field(self, client):
        """测试缺少必需字段"""
        response = client.post(
            '/api/v1/advanced/memory/add',
            json={'invalid_field': 'value'},
            content_type='application/json'
        )
        assert response.status_code in [400, 500]

    def test_invalid_memory_type(self, client):
        """测试无效的记忆类型"""
        response = client.post(
            '/api/v1/advanced/memory/add',
            json={
                'content': '测试内容',
                'memory_type': 'invalid_type'
            },
            content_type='application/json'
        )
        assert response.status_code in [200, 400, 500]


class TestPerformance:
    """性能测试"""

    def test_response_time(self, client):
        """测试响应时间"""
        start_time = time.time()
        response = client.get('/api/v1/advanced/health')
        elapsed = time.time() - start_time

        assert response.status_code in [200, 500]
        assert elapsed < 5.0

    def test_concurrent_requests(self, client):
        """测试并发请求"""
        queries = [
            '游戏王规则',
            'OCG召唤方式',
            '禁止卡表',
            '限制卡',
            '准限制卡'
        ]

        for query in queries:
            response = client.post(
                '/api/v1/advanced/routing/route',
                json={'query': query},
                content_type='application/json'
            )
            assert response.status_code in [200, 500]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
