
"""
OCG Rulebook QA System - Locust Load Test Script
场景 4: 5000 并发用户（压力测试）
- 用户数: 5000
- 增长率: 10 用户/秒
- 持续时间: 10 分钟
- 用途: 极端压力测试（通常需要分布式部署）
"""

from locust import HttpUser, task, between, events, constant
from locust.runners import MasterRunner
import random
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

conversation_ids = []

class OCGQAStressTestUser(HttpUser):
    """
    压力测试场景用户行为
    """
    
    # 极短的等待时间，制造最大压力
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        self.current_conversation_id = None
    
    @task(70)
    def chat_question(self):
        """主要任务：问答查询 - 最高频率"""
        question = random.choice(TEST_QUESTIONS)
        payload = {"question": question}
        
        if self.current_conversation_id and random.random() &lt; 0.2:
            payload["conversation_id"] = self.current_conversation_id
        
        with self.client.post(
            "/api/v1/chat/question",
            json=payload,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="chat_question (stress)",
            timeout=30.0
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
    
    @task(15)
    def chat_question_stream(self):
        """流式问答查询"""
        question = random.choice(TEST_QUESTIONS)
        payload = {"question": question}
        
        if self.current_conversation_id and random.random() &lt; 0.2:
            payload["conversation_id"] = self.current_conversation_id
        
        with self.client.post(
            "/api/v1/chat/question/stream",
            json=payload,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            stream=True,
            name="chat_stream (stress)",
            timeout=30.0
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(8)
    def get_conversations(self):
        """获取对话列表"""
        self.client.get("/api/v1/conversations", name="get_conversations (stress)")
    
    @task(5)
    def get_documents(self):
        """获取文档列表"""
        self.client.get("/api/v1/documents", name="get_documents (stress)")
    
    @task(2)
    def get_metrics(self):
        """获取系统指标"""
        self.client.get("/api/v1/metrics", name="get_metrics (stress)")
    
    @task(0)  # 不执行健康检查
    def health_check(self):
        """健康检查 - 禁用"""
        pass


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        print(f"[Scene 4] 主控节点启动于 {datetime.now()}")
        print("[Scene 4] 注意: 5000 并发建议使用分布式模式！")
    else:
        print(f"[Scene 4] 工作节点启动于 {datetime.now()}")
    print("[Scene 4] 配置: 5000 并发用户，10 用户/秒增长，10 分钟测试")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"[Scene 4] 测试完成于 {datetime.now()}")


SCENE_CONFIG = {
    "users": 5000,
    "spawn_rate": 10,
    "run_time": "10m"
}

if __name__ == "__main__":
    print("OCG Rulebook QA System - Load Test Scene 4")
    print("=" * 60)
    print("场景 4: 压力测试 (5000 并发)")
    print("=" * 60)
    print("⚠️  警告: 5000 并发需要强大的服务器资源！")
    print("建议使用分布式模式:")
    print("  # 主控节点")
    print("  locust -f locustfile_scene4.py --master --host=http://localhost:8000")
    print("  # 工作节点 (在多个机器上运行)")
    print("  locust -f locustfile_scene4.py --worker --master-host=主节点IP --host=http://localhost:8000")
    print("\n单机模式 (不推荐):")
    print("  locust -f locustfile_scene4.py --host=http://localhost:8000")
    print("\nHeadless 模式:")
    print(f"  locust -f locustfile_scene4.py --host=http://localhost:8000 --headless -u {SCENE_CONFIG['users']} -r {SCENE_CONFIG['spawn_rate']} -t {SCENE_CONFIG['run_time']}")
    print("\n配置说明:")
    print(f"  - 用户数: {SCENE_CONFIG['users']}")
    print(f"  - 增长率: {SCENE_CONFIG['spawn_rate']} 用户/秒")
    print(f"  - 运行时间: {SCENE_CONFIG['run_time']}")
