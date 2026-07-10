"""Agent 框架——基于 ReAct 模式 + Function Calling"""
import re
import json
import logging
from typing import List, Dict, Any, Callable, Optional, Generator, Tuple
from app.services.llm_provider import BaseLLMProvider
from app.services.skill_registry import SkillRegistry
from app.services.tools_definitions import (
    ALL_PREDEFINED_TOOLS,
    TOOLS_SEARCH_RULES,
    TOOLS_CALCULATE,
    TOOLS_GET_CARD_INFO,
)

logger = logging.getLogger(__name__)


class SimpleAgent:
    """基于 ReAct 模式的简单 Agent
    ReAct = Reasoning + Acting
    流程：思考(Think) → 行动(Action) → 观察(Observation) → 循环 → 回答(Answer)
    """

    REACT_PROMPT = """你是一个智能助手，使用以下格式思考：

Thought: 分析当前情况，决定下一步行动
Action: 要执行的动作名称
Action Input: 动作的输入参数

可用的动作：
{available_skills}

如果已经有足够信息，用以下格式结束：
Thought: 我有足够的信息来回答问题
Answer: 最终回答

---
历史：
{history}

当前问题：{question}
"""

    def __init__(
        self,
        provider: BaseLLMProvider,
        skill_registry: SkillRegistry,
        max_iterations: int = 5,
    ):
        self.provider = provider
        self.skills = skill_registry
        self.max_iterations = max_iterations

    def run(self, user_input: str) -> Dict[str, Any]:
        """执行 Agent 流程
        Returns:
            {"answer": str, "thoughts": [...], "actions": [...]}
        """
        available_skills = self.skills.get_skill_descriptions()
        history: List[Dict[str, str]] = []

        for i in range(self.max_iterations):
            # 1. 生成思考 + 行动指令
            prompt = self.REACT_PROMPT.format(
                available_skills=available_skills,
                history="\n".join([f"{h['type']}: {h['content']}" for h in history]),
                question=user_input,
            )

            response = self.provider.generate([{"role": "user", "content": prompt}])

            # 2. 解析响应
            thought = self._extract_thought(response)
            action = self._extract_action(response)
            action_input = self._extract_action_input(response)

            if thought:
                history.append({"type": "Thought", "content": thought})

            if action and action_input:
                # 3. 执行技能
                try:
                    observation = self.skills.execute(action, query=action_input)
                    history.append({
                        "type": "Observation",
                        "content": f"动作 {action} 返回: {str(observation)[:200]}"
                    })
                except Exception as e:
                    history.append({
                        "type": "Observation",
                        "content": f"动作 {action} 失败: {str(e)}"
                    })
            else:
                # 4. 提取最终回答
                answer = self._extract_answer(response)
                if answer:
                    return {
                        "answer": answer,
                        "thoughts": [h for h in history if h["type"] == "Thought"],
                        "actions": [h for h in history if h["type"] == "Observation"],
                    }

        # 超时未回答，用 provider 直接回答
        final_answer = self.provider.generate([{"role": "user", "content": f"请回答：{user_input}"}])
        return {
            "answer": final_answer,
            "thoughts": [h for h in history if h["type"] == "Thought"],
            "actions": [],
        }

    def _extract_thought(self, text: str) -> Optional[str]:
        match = re.search(r'Thought:\s*(.*?)(?=\nAction:|\nAnswer:|$)', text, re.DOTALL)
        return match.group(1).strip() if match else None

    def _extract_action(self, text: str) -> Optional[str]:
        match = re.search(r'Action:\s*(\w+)', text)
        return match.group(1) if match else None

    def _extract_action_input(self, text: str) -> Optional[str]:
        match = re.search(r'Action Input:\s*(.*?)(?=\n|$)', text)
        return match.group(1).strip() if match else None

    def _extract_answer(self, text: str) -> Optional[str]:
        match = re.search(r'Answer:\s*(.*?)(?=\n|$)', text, re.DOTALL)
        return match.group(1).strip() if match else None


# ---------------------------------------------------------------------------
# Function Calling Agent
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_FC = """你是一个 OCG 规则问答助手。你可以使用以下工具帮助用户查询游戏王 OCG 规则。
当你收到用户的问题时，请根据需要调用合适的工具来获取信息，然后综合回答用户的问题。
如果不需要调用工具，直接给出回答即可。"""


def _build_tool_map(tools: List[Dict[str, Any]]) -> str:
    """从 tools 定义构建简要的工具映射说明，用于日志和降级场景。"""
    parts = []
    for t in tools:
        fn = t.get("function", {})
        name = fn.get("name", t.get("name", "?"))
        desc = fn.get("description", "")
        parts.append(f"- {name}: {desc}")
    return "\n".join(parts)


class FunctionCallingAgent:
    """基于 MiniMax-M2.5 / OpenAI Function Calling 的 Agent

    流程：
    1. 将用户消息 + system prompt 发给 LLM（带 tools 参数）
    2. LLM 可能返回 tool_calls 或纯文本回答
    3. 如果有 tool_calls，依次执行每个工具（支持并行调用）
    4. 将工具结果以 tool role 消息注入对话
    5. 再次调用 LLM，直到 LLM 不再请求工具调用

    兼容 SimpleAgent 接口：run() 返回格式与 SimpleAgent 一致
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        skill_registry: SkillRegistry,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_iterations: int = 5,
        system_prompt: Optional[str] = None,
    ):
        self.provider = provider
        self.skills = skill_registry
        self.tools = tools or ALL_PREDEFINED_TOOLS
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt or SYSTEM_PROMPT_FC

    # ----- public API --------------------------------------------------------

    def run(self, user_input: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """执行 Function Calling Agent 流程（非流式）

        Args:
            user_input: 用户问题
            history: 可选的历史消息列表，格式与 OpenAI Chat API 一致

        Returns:
            {"answer": str, "thoughts": [...], "actions": [...],
             "tool_calls_history": [...], "messages": [...], "used_function_calling": True}
        """
        messages = self._build_messages(user_input, history)
        tool_calls_history: List[Dict[str, Any]] = []

        for i in range(self.max_iterations):
            try:
                response = self.provider.generate(messages, tools=self.tools)
            except Exception as e:
                logger.error(f"[FC-Agent] provider.generate failed: {e}")
                # 优雅降级：直接调一次不带 tools 的生成
                fallback = self.provider.generate(
                    [{"role": "user", "content": user_input}]
                )
                return {
                    "answer": fallback if isinstance(fallback, str) else str(fallback),
                    "thoughts": [f"工具路径异常，已降级到直接回答: {e}"],
                    "actions": [],
                    "tool_calls_history": [],
                    "messages": messages,
                    "used_function_calling": True,
                }

            # 解析：返回 (is_tool_call, payload)
            is_tool_call, payload = self._parse_response(response)

            if not is_tool_call:
                # 没有 tool_calls，response 就是最终回答（payload 是文本）
                return {
                    "answer": payload if isinstance(payload, str) else str(payload),
                    "thoughts": [self._summarize_tool_calls(tool_calls_history)],
                    "actions": [tc.get('function', {}).get('name', '')
                                for tc in tool_calls_history],
                    "tool_calls_history": tool_calls_history,
                    "messages": messages,
                    "used_function_calling": True,
                }

            # payload 是 List[tool_call_dict]
            tool_calls = payload

            # 把 assistant 的 tool_calls 消息加入上下文（OpenAI 协议要求）
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls,
            })

            # 依次执行每个 tool_call
            for tool_call in tool_calls:
                func_name = tool_call.get('function', {}).get('name', '')
                args_str = tool_call.get('function', {}).get('arguments', '{}')
                try:
                    func_args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
                except (json.JSONDecodeError, TypeError):
                    func_args = {}

                tool_calls_history.append(tool_call)

                try:
                    result = self.skills.execute(func_name, **func_args)
                    result_text = str(result) if not isinstance(result, str) else result
                except Exception as e:
                    logger.warning(f"[FC-Agent] skill execute failed for '{func_name}': {e}")
                    result_text = f"工具执行失败: {str(e)}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get('id', ''),
                    "content": result_text,
                })

        # 达到最大迭代次数，最后一次 LLM 调用生成总结
        try:
            final = self.provider.generate(messages)
            final_answer = final if isinstance(final, str) else str(final)
        except Exception as e:
            logger.error(f"[FC-Agent] final generate failed: {e}")
            final_answer = "已达到最大迭代次数，无法继续。"

        return {
            "answer": final_answer,
            "thoughts": ["达到最大迭代次数"] + ([self._summarize_tool_calls(tool_calls_history)] if tool_calls_history else []),
            "actions": [tc.get('function', {}).get('name', '') for tc in tool_calls_history],
            "tool_calls_history": tool_calls_history,
            "messages": messages,
            "used_function_calling": True,
        }

    def run_stream(
        self,
        user_input: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Generator[str, None, None]:
        """执行 Function Calling Agent 流程（流式）

        在工具调用阶段不会产生流式输出，只在最终回答阶段产生流式 token。

        Yields:
            流式文本 chunk
        """
        messages = self._build_messages(user_input, history)

        for _i in range(self.max_iterations):
            has_tool_call = False
            collected: List[str] = []

            for chunk in self.provider.generate_stream(messages, tools=self.tools):
                # 检查是否是 tool_call chunk（JSON 格式）
                if isinstance(chunk, str) and chunk.startswith("{"):
                    try:
                        parsed = json.loads(chunk)
                        if "tool_call_chunk" in parsed:
                            has_tool_call = True
                            continue
                    except json.JSONDecodeError:
                        pass

                collected.append(chunk)
                yield chunk

            if has_tool_call:
                # 需要执行工具调用，重新构建消息并再次调用
                full_response = "".join(collected)
                is_tc, payload = self._parse_response(full_response)
                if not is_tc:
                    return
                tool_calls = payload

                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                })

                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    fn_info = tc.get("function", {})
                    name = fn_info.get("name", "")
                    args_str = fn_info.get("arguments", "{}")
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
                    except (json.JSONDecodeError, TypeError):
                        args = {}

                    try:
                        output = self._dispatch_tool(name, args)
                        content = str(output)
                    except Exception as e:
                        content = f"工具执行失败: {str(e)}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": content,
                    })
            else:
                return

    # ----- internal helpers --------------------------------------------------

    def _build_messages(
        self,
        user_input: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """构建 LLM 消息上下文：system + 历史（可选） + 当前问题"""
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        if history:
            for h in history:
                role = h.get('role', 'user')
                content = h.get('content', '')
                if role in ('user', 'assistant', 'system') and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_input})
        return messages

    def _parse_response(self, response: Any) -> Tuple[bool, Any]:
        """统一解析 LLM 返回：判断是 tool_calls 还是纯文本

        Returns:
            (is_tool_call, payload):
                - is_tool_call=True → payload 是 List[Dict] (tool_calls)
                - is_tool_call=False → payload 是 str (最终回答)
        """
        # 1. 字符串：尝试 JSON 解析
        if isinstance(response, str):
            stripped = response.strip()
            if stripped.startswith("{"):
                try:
                    data = json.loads(stripped)
                    if isinstance(data, dict) and data.get("tool_calls"):
                        return True, data["tool_calls"]
                except (json.JSONDecodeError, TypeError):
                    pass
            # 不是 JSON 或没有 tool_calls → 文本
            return False, response

        # 2. 字典：检查 tool_calls
        if isinstance(response, dict):
            if response.get("tool_calls"):
                return True, response["tool_calls"]
            return False, response.get("content", str(response))

        # 3. Pydantic model 之类的：有 .model_dump()
        if hasattr(response, 'model_dump'):
            try:
                d = response.model_dump()
                if d.get("tool_calls"):
                    return True, d["tool_calls"]
                return False, d.get("content", "")
            except Exception:
                pass

        # 4. 兜底
        return False, str(response)

    def _summarize_tool_calls(self, tool_calls_history: List[Dict]) -> str:
        if not tool_calls_history:
            return "直接回答（无工具调用）"
        names = [tc.get('function', {}).get('name', '') for tc in tool_calls_history]
        return f"调用了工具: {', '.join(names)}"

    def _dispatch_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """将工具名称分派到实际执行函数

        优先从 skill_registry 查找，如果找不到则使用预定义的内置工具。
        """
        # 1. 尝试从 skill registry 执行
        try:
            return self.skills.execute(name, **args)
        except Exception:
            # 2. 内置工具 fallback
            if name == "search_rules":
                return self._tool_search_rules(args.get("query", ""), args.get("top_k", 5))
            elif name == "calculate":
                return self._tool_calculate(args.get("expression", ""))
            elif name == "get_card_info":
                return self._tool_get_card_info(args.get("card_name", ""))
            else:
                raise ValueError(f"未知工具: {name}")

    def _tool_search_rules(self, query: str, top_k: int = 5) -> str:
        try:
            result = self.skills.execute("search_rules", query=query, top_k=top_k)
            return str(result)
        except Exception as e:
            return f"搜索失败: {str(e)}"

    def _tool_calculate(self, expression: str) -> str:
        try:
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in expression):
                return "错误: 表达式包含不允许的字符"
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as e:
            return f"计算错误: {str(e)}"

    def _tool_get_card_info(self, card_name: str) -> str:
        try:
            result = self.skills.execute("get_card_info", card_name=card_name)
            return str(result)
        except Exception as e:
            return f"获取卡片信息失败: {str(e)}"
