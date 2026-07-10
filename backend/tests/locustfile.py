
"""
OCG Rulebook QA System - Locust Load Test Script
支持多个并发场景的全链路压测
"""

from locust import HttpUser, task, between, events
import json
import random
import uuid
import time
from datetime import datetime


# 测试用的问题样本
TEST_QUESTIONS = [
    "什么是连锁？",
    "通常召唤的规则是什么？",
    "融合召唤需要什么条件？",
    "效果怪兽和通常怪兽的区别？",
    "墓地效果发动的时机？",
    "同步召唤的步骤？",
    "超量召唤的规则？",
    "连接箭头的含义？",
    "战斗伤害如何计算？",
    "魔法陷阱的发动时机？",
    "灵摆召唤的过程是怎样的？",
    "仪式召唤需要哪些要素？",
    "衍生物的规则是什么？",
    "场上怪兽效果无效的情况？",
    "特殊召唤的各种方式？"
]

# 会话ID池，用于测试有历史对话的情况
conversation_ids = []

# 测试数据收集器
test_results = {
    "start_time": None,
    "end_time": None,
    "total_requests": 0,
    "failed_requests": 0,
    "response_times": []
}


class OCGQAUser(HttpUser):
    """
    模拟真实用户行为
    """
    
    # 等待时间：用户操作间的随机延迟（1-3秒）
    wait_time = between(1, 3)
    
    def on_start(self):
        """
        用户启动时的初始化操作
        """
        self.current_conversation_id = None
        self.conversation_history = []
    
    @task(30)
    def chat_question(self):
        """
        主要任务：问答查询（权重最高）
        """
        question = random.choice(TEST_QUESTIONS)
        
        payload = {
            "question": question
        }
        
        # 50%的概率使用已有对话ID，测试有历史的情况
        if self.current_conversation_id and random.random() &lt; 0.5:
            payload["conversation_id"] = self.current_conversation_id
        
        with self.client.post(
            "/api/v1/chat/question",
            json=payload,
            headers={"Content-Type": "application/json"},
            catch_response=True
        ) as response:
            test_results["total_requests"] += 1
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    self.current_conversation_id = result.get("data", {}).get("conversation_id")
                    if self.current_conversation_id:
                        conversation_ids.append(self.current_conversation_id)
                    response.success()
                else:
                    test_results["failed_requests"] += 1
                    response.failure(f"API returned error: {result.get('error')}")
            else:
                test_results["failed_requests"] += 1
                response.failure(f"HTTP {response.status_code}")
    
    @task(15)
    def chat_question_stream(self):
        """
        流式问答查询
        """
        question = random.choice(TEST_QUESTIONS)
        
        payload = {
            "question": question
        }
        
        if self.current_conversation_id and random.random() &lt; 0.5:
            payload["conversation_id"] = self.current_conversation_id
        
        with self.client.post(
            "/api/v1/chat/question/stream",
            json=payload,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            stream=True
        ) as response:
            test_results["total_requests"] += 1
            if response.status_code == 200:
                # 简单确认流式响应可正常接收
                content = ""
                try:
                    for line in response.iter_lines():
                        if line:
                            content += line.decode('utf-8')
                            if "[DONE]" in content:
                                break
                    response.success()
                except Exception as e:
                    test_results["failed_requests"] += 1
                    response.failure(f"Stream read error: {str(e)}")
            else:
                test_results["failed_requests"] += 1
                response.failure(f"HTTP {response.status_code}")
    
    @task(10)
    def get_conversations(self):
        """
        获取对话列表
        """
        with self.client.get(
            "/api/v1/conversations",
            catch_response=True
        ) as response:
            test_results["total_requests"] += 1
            if response.status_code == 200:
                response.success()
            else:
                test_results["failed_requests"] += 1
                response.failure(f"HTTP {response.status_code}")
    
    @task(8)
    def get_conversation_detail(self):
        """
        获取特定对话详情
        """
        if conversation_ids:
            conv_id = random.choice(conversation_ids)
            with self.client.get(
                f"/api/v1/conversations/{conv_id}",
                catch_response=True
            ) as response:
                test_results["total_requests"] += 1
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 404:
                    # 对话不存在是可接受的
                    response.success()
                else:
                    test_results["failed_requests"] += 1
                    response.failure(f"HTTP {response.status_code}")
    
    @task(7)
    def get_documents(self):
        """
        获取文档列表
        """
        with self.client.get(
            "/api/v1/documents",
            catch_response=True
        ) as response:
            test_results["total_requests"] += 1
            if response.status_code == 200:
                response.success()
            else:
                test_results["failed_requests"] += 1
                response.failure(f"HTTP {response.status_code}")
    
    @task(5)
    def get_metrics(self):
        """
        获取系统指标
        """
        with self.client.get(
            "/api/v1/metrics",
            catch_response=True
        ) as response:
            test_results["total_requests"] += 1
            if response.status_code == 200:
                response.success()
            else:
                test_results["failed_requests"] += 1
                response.failure(f"HTTP {response.status_code}")
    
    @task(3)
    def health_check(self):
        """
        健康检查
        """
        with self.client.get(
            "/api/v1/health",
            catch_response=True
        ) as response:
            test_results["total_requests"] += 1
            if response.status_code == 200:
                response.success()
            else:
                test_results["failed_requests"] += 1
                response.failure(f"HTTP {response.status_code}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    测试开始前的钩子
    """
    test_results["start_time"] = datetime.now()
    print(f"[INFO] 测试开始于: {test_results['start_time']}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    测试结束后的钩子
    """
    test_results["end_time"] = datetime.now()
    duration = (test_results["end_time"] - test_results["start_time"]).total_seconds()
    
    print("\n" + "="*60)
    print("测试完成 - 基本统计")
    print("="*60)
    print(f"测试持续时间: {duration:.2f} 秒")
    print(f"总请求数: {test_results['total_requests']}")
    print(f"失败请求数: {test_results['failed_requests']}")
    if test_results["total_requests"] &gt; 0:
        success_rate = ((test_results["total_requests"] - test_results["failed_requests"]) 
                       / test_results["total_requests"] * 100)
        print(f"成功率: {success_rate:.2f}%")
    print("="*60 + "\n")


if __name__ == "__main__":
    print("OCG Rulebook QA System - Locust Load Test")
    print("请使用以下命令运行:")
    print("  locust -f locustfile.py --host=http://localhost:8000")
    print("\n或者使用指定场景的脚本:")
    print("  locust -f locustfile_scene1.py --host=http://localhost:8000")

