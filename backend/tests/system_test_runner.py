"""
完整系统测试脚本 - 测试前后端连通性

测试所有新功能的API端点和前后端集成。
"""

import sys
import os
import time
import json
import requests
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SystemTestRunner:
    """系统测试运行器"""

    def __init__(self, base_url: str = 'http://127.0.0.1:5000'):
        self.base_url = base_url
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def log_test(self, name: str, passed: bool, message: str = '', details: Any = None):
        """记录测试结果"""
        status = '✓ PASS' if passed else '✗ FAIL'
        self.results.append({
            'name': name,
            'status': status,
            'message': message,
            'details': details
        })
        if passed:
            self.passed += 1
            print(f"  {status}: {name}")
            if message:
                print(f"         {message}")
        else:
            self.failed += 1
            print(f"  {status}: {name}")
            if message:
                print(f"         {message}")
            if details:
                print(f"         Details: {details}")

    def test_backend_health(self) -> bool:
        """测试后端健康状态"""
        print("\n=== 测试后端健康状态 ===")
        try:
            response = requests.get(f'{self.base_url}/api/v1/health', timeout=5)
            self.log_test(
                "后端健康检查",
                response.status_code == 200,
                f"状态码: {response.status_code}"
            )
            return response.status_code == 200
        except Exception as e:
            self.log_test("后端健康检查", False, str(e))
            return False

    def test_advanced_routes_registration(self) -> bool:
        """测试高级路由是否注册"""
        print("\n=== 测试高级路由注册 ===")
        routes_to_test = [
            '/api/v1/advanced/health',
            '/api/v1/advanced/status',
            '/api/v1/advanced/query/unified',
            '/api/v1/advanced/memory/add',
            '/api/v1/advanced/memory/retrieve',
            '/api/v1/advanced/routing/route',
            '/api/v1/advanced/rag/search',
            '/api/v1/advanced/tools/list',
            '/api/v1/advanced/chunking/strategy'
        ]

        all_registered = True
        for route in routes_to_test:
            try:
                if route.endswith('/unified') or route.endswith('/add') or route.endswith('/route') or route.endswith('/chunk'):
                    response = requests.post(f'{self.base_url}{route}', json={'test': 'data'}, timeout=5)
                else:
                    response = requests.get(f'{self.base_url}{route}', timeout=5)

                status = response.status_code != 404
                self.log_test(
                    f"路由注册: {route}",
                    status,
                    f"状态码: {response.status_code}"
                )
                all_registered = all_registered and status
            except Exception as e:
                self.log_test(f"路由注册: {route}", False, str(e))
                all_registered = False

        return all_registered

    def test_advanced_health(self):
        """测试高级服务健康检查"""
        print("\n=== 测试高级服务健康检查 ===")
        try:
            response = requests.get(f'{self.base_url}/api/v1/advanced/health', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    result = data.get('data', {})
                    services = result.get('services', {})
                    print(f"  检测到的服务: {len(services)}")
                    for name, info in services.items():
                        print(f"    - {name}: {info.get('status')}")
            self.log_test(
                "高级服务健康检查",
                response.status_code == 200,
                f"状态码: {response.status_code}"
            )
        except Exception as e:
            self.log_test("高级服务健康检查", False, str(e))

    def test_system_status(self):
        """测试系统状态"""
        print("\n=== 测试系统状态 ===")
        try:
            response = requests.get(f'{self.base_url}/api/v1/advanced/status', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    result = data.get('data', {})
                    initialized = result.get('initialized', False)
                    self.log_test(
                        "系统初始化状态",
                        True,
                        f"已初始化: {initialized}"
                    )
            self.log_test(
                "系统状态接口",
                response.status_code == 200,
                f"状态码: {response.status_code}"
            )
        except Exception as e:
            self.log_test("系统状态接口", False, str(e))

    def test_unified_query(self):
        """测试统一查询接口"""
        print("\n=== 测试统一查询接口 ===")
        test_queries = [
            "游戏王OCG规则是什么",
            "怎么召唤怪兽",
            "禁止卡表是什么"
        ]

        for query in test_queries:
            try:
                response = requests.post(
                    f'{self.base_url}/api/v1/advanced/query/unified',
                    json={
                        'query': query,
                        'enable_memory': True,
                        'enable_hierarchical': True
                    },
                    timeout=30
                )
                success = response.status_code == 200
                details = None
                if success:
                    data = response.json()
                    if data.get('success'):
                        result = data.get('data', {})
                        details = f"路由: {result.get('route', {}).get('selected', 'N/A')}, "
                        details += f"置信度: {result.get('route', {}).get('confidence', 'N/A')}"

                self.log_test(
                    f"统一查询: {query[:20]}...",
                    success,
                    details or f"状态码: {response.status_code}"
                )
            except Exception as e:
                self.log_test(f"统一查询: {query[:20]}...", False, str(e))

    def test_memory_operations(self):
        """测试记忆操作"""
        print("\n=== 测试记忆操作 ===")

        try:
            response = requests.post(
                f'{self.base_url}/api/v1/advanced/memory/add',
                json={
                    'content': f'测试记忆 {time.time()}',
                    'memory_type': 'episodic',
                    'importance': 0.8,
                    'tags': ['测试']
                },
                timeout=10
            )
            self.log_test(
                "添加记忆",
                response.status_code == 200,
                f"状态码: {response.status_code}"
            )
        except Exception as e:
            self.log_test("添加记忆", False, str(e))

        try:
            response = requests.get(
                f'{self.base_url}/api/v1/advanced/memory/retrieve',
                params={'query': '测试', 'limit': 5},
                timeout=10
            )
            self.log_test(
                "检索记忆",
                response.status_code == 200,
                f"状态码: {response.status_code}"
            )
        except Exception as e:
            self.log_test("检索记忆", False, str(e))

        try:
            response = requests.get(
                f'{self.base_url}/api/v1/advanced/memory/stats',
                timeout=10
            )
            self.log_test(
                "记忆统计",
                response.status_code == 200,
                f"状态码: {response.status_code}"
            )
        except Exception as e:
            self.log_test("记忆统计", False, str(e))

    def test_routing_operations(self):
        """测试路由操作"""
        print("\n=== 测试路由操作 ===")

        try:
            response = requests.get(
                f'{self.base_url}/api/v1/advanced/routing/routes',
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    routes = data.get('data', {}).get('routes', [])
                    self.log_test(
                        "列出路由",
                        True,
                        f"找到 {len(routes)} 个路由"
                    )
                else:
                    self.log_test("列出路由", False, "API返回失败")
            else:
                self.log_test("列出路由", False, f"状态码: {response.status_code}")
        except Exception as e:
            self.log_test("列出路由", False, str(e))

        try:
            response = requests.post(
                f'{self.base_url}/api/v1/advanced/routing/route',
                json={'query': '什么是禁止卡表'},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    result = data.get('data', {})
                    route = result.get('selected_route', 'N/A')
                    confidence = result.get('confidence', 0)
                    self.log_test(
                        "路由查询",
                        True,
                        f"选择路由: {route}, 置信度: {confidence}"
                    )
                else:
                    self.log_test("路由查询", False, "API返回失败")
            else:
                self.log_test("路由查询", False, f"状态码: {response.status_code}")
        except Exception as e:
            self.log_test("路由查询", False, str(e))

    def test_rag_operations(self):
        """测试RAG操作"""
        print("\n=== 测试RAG操作 ===")

        try:
            response = requests.get(
                f'{self.base_url}/api/v1/advanced/rag/stats',
                timeout=10
            )
            self.log_test(
                "RAG统计",
                response.status_code == 200,
                f"状态码: {response.status_code}"
            )
        except Exception as e:
            self.log_test("RAG统计", False, str(e))

        try:
            response = requests.get(
                f'{self.base_url}/api/v1/advanced/rag/search',
                params={'query': '召唤规则', 'top_k': 5},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    results = data.get('data', {}).get('results', [])
                    self.log_test(
                        "RAG搜索",
                        True,
                        f"找到 {len(results)} 个结果"
                    )
                else:
                    self.log_test("RAG搜索", False, "API返回失败")
            else:
                self.log_test("RAG搜索", False, f"状态码: {response.status_code}")
        except Exception as e:
            self.log_test("RAG搜索", False, str(e))

    def test_tool_operations(self):
        """测试工具操作"""
        print("\n=== 测试工具操作 ===")

        try:
            response = requests.get(
                f'{self.base_url}/api/v1/advanced/tools/list',
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    tools = data.get('data', {}).get('tools', [])
                    self.log_test(
                        "列出工具",
                        True,
                        f"找到 {len(tools)} 个工具"
                    )
                else:
                    self.log_test("列出工具", False, "API返回失败")
            else:
                self.log_test("列出工具", False, f"状态码: {response.status_code}")
        except Exception as e:
            self.log_test("列出工具", False, str(e))

    def test_chunking_operations(self):
        """测试分块操作"""
        print("\n=== 测试分块操作 ===")

        try:
            response = requests.get(
                f'{self.base_url}/api/v1/advanced/chunking/strategy',
                timeout=10
            )
            self.log_test(
                "获取分块策略",
                response.status_code == 200,
                f"状态码: {response.status_code}"
            )
        except Exception as e:
            self.log_test("获取分块策略", False, str(e))

        try:
            response = requests.post(
                f'{self.base_url}/api/v1/advanced/chunking/chunk',
                json={
                    'text': '这是一个测试文本。用于测试分块功能。应该被分成多个块。',
                    'strategy': 'adaptive',
                    'max_chunk_size': 20
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    chunks = data.get('data', {}).get('chunks', [])
                    self.log_test(
                        "文本分块",
                        True,
                        f"分成 {len(chunks)} 个块"
                    )
                else:
                    self.log_test("文本分块", False, "API返回失败")
            else:
                self.log_test("文本分块", False, f"状态码: {response.status_code}")
        except Exception as e:
            self.log_test("文本分块", False, str(e))

    def test_error_handling(self):
        """测试错误处理"""
        print("\n=== 测试错误处理 ===")

        try:
            response = requests.post(
                f'{self.base_url}/api/v1/advanced/query/unified',
                json={},
                timeout=10
            )
            self.log_test(
                "空查询错误处理",
                response.status_code == 400,
                f"状态码: {response.status_code} (预期: 400)"
            )
        except Exception as e:
            self.log_test("空查询错误处理", False, str(e))

        try:
            response = requests.get(
                f'{self.base_url}/api/v1/advanced/memory/retrieve',
                params={'query': ''},
                timeout=10
            )
            self.log_test(
                "空查询参数错误处理",
                response.status_code == 400,
                f"状态码: {response.status_code} (预期: 400)"
            )
        except Exception as e:
            self.log_test("空查询参数错误处理", False, str(e))

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("完整系统测试 - 前后端连通性测试")
        print("=" * 60)
        print(f"测试目标: {self.base_url}")
        print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        self.test_backend_health()
        self.test_advanced_routes_registration()
        self.test_advanced_health()
        self.test_system_status()
        self.test_unified_query()
        self.test_memory_operations()
        self.test_routing_operations()
        self.test_rag_operations()
        self.test_tool_operations()
        self.test_chunking_operations()
        self.test_error_handling()

        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        print(f"✓ 通过: {self.passed}")
        print(f"✗ 失败: {self.failed}")
        print(f"总计: {self.passed + self.failed + self.skipped}")
        print(f"通过率: {self.passed / (self.passed + self.failed) * 100:.1f}%" if self.passed + self.failed > 0 else "N/A")
        print("=" * 60)

        return self.failed == 0

    def save_results(self, filepath: str):
        """保存测试结果"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {
                    'passed': self.passed,
                    'failed': self.failed,
                    'skipped': self.skipped,
                    'total': self.passed + self.failed + self.skipped,
                    'pass_rate': f"{self.passed / (self.passed + self.failed) * 100:.1f}%" if self.passed + self.failed > 0 else "N/A"
                },
                'tests': self.results
            }, f, ensure_ascii=False, indent=2)
        print(f"\n测试结果已保存到: {filepath}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='完整系统测试')
    parser.add_argument('--url', default='http://127.0.0.1:5000', help='后端URL')
    parser.add_argument('--output', default='test_results.json', help='输出文件')
    args = parser.parse_args()

    runner = SystemTestRunner(base_url=args.url)
    success = runner.run_all_tests()
    runner.save_results(args.output)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
