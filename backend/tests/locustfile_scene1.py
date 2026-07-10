
"""
OCG Rulebook QA System - Locust Load Test Script
场景 1: 100 并发用户（正常负载）
- 用户数: 100
- 增长率: 10 用户/秒
- 持续时间: 5 分钟
- 用途: 日常性能基准测试
"""

from locust import HttpUser, task, between, events, constant_pacing
from locust.runners import MasterRunner
import random
import json
from datetime import datetime
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    "魔法陷阱的发动时机？"
]

conversation_ids = []

class OCGQANormalUser(HttpUser):
    """
    正常负载场景用户行为
    """
    
    # 等待时间：1-2秒，模拟真实用户思考时间
    wait_time = between(1, 2)
    
    def on_start(self):
        self.current_conversation_id = None
    
    @task(40)
    def chat_question(self):
        """主要任务：问答查询"""
        question = random.choice(TEST_QUESTIONS)
        payload = {"question": question}
        
        if self.current_conversation_id and random.random() &lt; 0.5:
            payload["conversation_id"] = self.current_conversation_id
        
        with self.client.post(
            "/api/v1/chat/question",
            json=payload,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="chat_question (normal)"
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    conv_id = result.get("data", {}).get("conversation_id")
                    if conv_id:
                        self.current_conversation_id = conv_id
                        conversation_ids.append(conv_id)
                    response.success()
                else:
                    response.failure(f"API error: {result.get('error')}")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(20)
    def chat_question_stream(self):
        """流式问答查询"""
        question = random.choice(TEST_QUESTIONS)
        payload = {"question": question}
        
        if self.current_conversation_id and random.random() &lt; 0.5:
            payload["conversation_id"] = self.current_conversation_id
        
        with self.client.post(
            "/api/v1/chat/question/stream",
            json=payload,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            stream=True,
            name="chat_stream (normal)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(15)
    def get_conversations(self):
        """获取对话列表"""
        self.client.get("/api/v1/conversations", name="get_conversations (normal)")
    
    @task(10)
    def get_documents(self):
        """获取文档列表"""
        self.client.get("/api/v1/documents", name="get_documents (normal)")
    
    @task(10)
    def get_metrics(self):
        """获取系统指标"""
        self.client.get("/api/v1/metrics", name="get_metrics (normal)")
    
    @task(5)
    def health_check(self):
        """健康检查"""
        self.client.get("/api/v1/health", name="health_check (normal)")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        print(f"[Scene 1] 主控节点启动于 {datetime.now()}")
    else:
        print(f"[Scene 1] 工作节点启动于 {datetime.now()}")
    print("[Scene 1] 配置: 100 并发用户，10 用户/秒增长，5 分钟测试")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"[Scene 1] 测试完成于 {datetime.now()}")


# 场景配置（用于 Headless 模式）
SCENE_CONFIG = {
    "users": 100,
    "spawn_rate": 10,
    "run_time": "5m"
}

if __name__ == "__main__":
    print("OCG Rulebook QA System - Load Test Scene 1")
    print("=" * 60)
    print("场景 1: 正常负载 (100 并发)")
    print("=" * 60)
    print("Web UI 模式:")
    print("  locust -f locustfile_scene1.py --host=http://localhost:8000")
    print("\nHeadless 模式:")
    print(f"  locust -f locustfile_scene1.py --host=http://localhost:8000 --headless -u {SCENE_CONFIG['users']} -r {SCENE_CONFIG['spawn_rate']} -t {SCENE_CONFIG['run_time']}")
    print("\n配置说明:")
    print(f"  - 用户数: {SCENE_CONFIG['users']}")
    print(f"  - 增长率: {SCENE_CONFIG['spawn_rate']} 用户/秒")
    print(f"  - 运行时间: {SCENE_CONFIG['run_time']}")
