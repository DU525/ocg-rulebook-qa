"""
飞书通知服务 (P0: 消息通知集成)
通过 lark-cli 发送飞书消息通知
"""

import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 飞书通知优先级
FEISHU_PRIORITY = {
    'low': '低优先级',
    'medium': '中优先级',
    'high': '高优先级',
    'urgent': '紧急告警'
}


def check_feishu_cli_available() -> bool:
    """检查 lark-cli 是否可用"""
    try:
        result = subprocess.run(
            ['lark-cli', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"lark-cli 检查失败: {e}")
        return False


def send_message(chat_id: str, message: str, as_bot: bool = True) -> dict:
    """
    发送飞书消息

    Args:
        chat_id: 飞书群聊ID
        message: 消息内容（支持Markdown）
        as_bot: 是否以机器人身份发送（默认True）

    Returns:
        dict: {"success": bool, "message": str}
    """
    from flask import current_app

    # 检查是否启用飞书
    if hasattr(current_app, 'config'):
        if not current_app.config.get('FEISHU_ENABLED', False):
            return {"success": False, "message": "飞书通知未启用"}

    # 检查lark-cli
    if not check_feishu_cli_available():
        logger.error("lark-cli 未安装或不可用")
        return {"success": False, "message": "lark-cli 未安装"}

    try:
        # 构建命令
        cmd = ['lark-cli', 'im', '+messages-send']

        # 获取目标
        target_chat_id = chat_id or current_app.config.get('FEISHU_CHAT_ID', '')
        user_id = current_app.config.get('FEISHU_USER_ID', '')
        
        # 身份设置
        if as_bot:
            cmd.extend(['--as', 'bot'])
        else:
            cmd.extend(['--as', 'user'])
        
        # 发送目标 - 优先群聊chat_id，其次用户user_id
        if target_chat_id:
            cmd.extend(['--chat-id', target_chat_id, '--markdown', message])
        elif user_id:
            cmd.extend(['--user-id', user_id, '--text', message])
        else:
            logger.error("未配置飞书CHAT_ID或USER_ID")
            return {"success": False, "message": "未配置飞书目标"}

        logger.info(f"发送飞书消息: chat_id={target_chat_id or 'N/A'}, user_id={user_id or 'N/A'}, preview={message[:50]}...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            logger.info("飞书消息发送成功")
            return {"success": True, "message": "消息已发送"}
        else:
            logger.error(f"飞书消息发送失败: {result.stderr}")
            return {"success": False, "message": result.stderr.strip()}

    except subprocess.TimeoutExpired:
        logger.error("飞书消息发送超时")
        return {"success": False, "message": "消息发送超时"}
    except Exception as e:
        logger.error(f"飞书消息发送异常: {e}")
        return {"success": False, "message": str(e)}


def send_alert(title: str, content: str, priority: str = 'medium') -> dict:
    """
    发送告警通知

    Args:
        title: 告警标题
        content: 告警内容
        priority: 优先级 (low/medium/high/urgent)

    Returns:
        dict: {"success": bool, "message": str}
    """
    priority_label = FEISHU_PRIORITY.get(priority, '普通')

    # 构建Markdown格式的消息
    message = f"""## {priority_label}告警: {title}

{content}

> 💡 OCG规则书问答系统"""

    return send_message(
        chat_id='',
        message=message,
        as_bot=True
    )


def send_kb_update(doc_name: str, update_type: str, details: str = '') -> dict:
    """
    发送知识库更新通知

    Args:
        doc_name: 文档名称
        update_type: 更新类型 (新增/更新/删除)
        details: 详细说明

    Returns:
        dict: {"success": bool, "message": str}
    """
    message = f"""## 📚 知识库更新

**文档**: {doc_name}
**操作**: {update_type}
{details if details else ''}

> 💡 自动通知"""

    return send_message(
        chat_id='',
        message=message,
        as_bot=True
    )


def send_stats(summary: dict) -> dict:
    """
    发送系统统计信息

    Args:
        summary: 统计数据字典，包含 questions_count, avg_response_time 等

    Returns:
        dict: {"success": bool, "message": str}
    """
    questions = summary.get('questions_count', 0)
    avg_time = summary.get('avg_response_time', 0)

    message = f"""## 📊 系统统计日报

- **今日问答数**: {questions}
- **平均响应时间**: {avg_time:.2f}秒

> 💡 OCG规则书系统"""

    return send_message(
        chat_id='',
        message=message,
        as_bot=True
    )


if __name__ == '__main__':
    # 测试代码
    print("飞书通知服务测试")
    print(f"lark-cli 可用: {check_feishu_cli_available()}")