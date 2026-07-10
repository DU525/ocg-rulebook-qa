from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Any, Optional
import logging
import requests
import json
from app.services.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


def _get_trace_id() -> str:
    try:
        from app.core.trace import get_current_trace
        return get_current_trace()
    except Exception:
        return ''


class BaseLLMProvider(ABC):
    """LLM 供应商抽象基类"""

    def __init__(self, api_key: str, api_base: str, model_name: str, **kwargs):
        self.api_key = api_key
        self.api_base = api_base
        self.model_name = model_name
        self.kwargs = kwargs
        self._circuit_breaker = CircuitBreaker(
            name=f"{self.__class__.__name__}/{model_name}",
            failure_threshold=3,
            recovery_timeout=60,
        )

    @abstractmethod
    def generate(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        tools: Optional[List[dict]] = None,
    ) -> str:
        pass

    @abstractmethod
    def generate_stream(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        tools: Optional[List[dict]] = None,
    ) -> Generator[str, None, None]:
        pass

    @abstractmethod
    def health_check(self) -> bool:
        pass

    def get_model_info(self) -> dict:
        return {
            "model_name": self.model_name,
            "provider_name": self._provider_name(),
            "supports_streaming": True,
        }

    def _provider_name(self) -> str:
        return self.__class__.__name__.replace("Provider", "").lower()

    def get_circuit_breaker_stats(self) -> dict:
        return self._circuit_breaker.get_stats()


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI 兼容 API 供应商 - 适用于任何遵循 /v1/chat/completions 格式的 API"""

    def __init__(self, api_key: str, api_base: str, model_name: str, **kwargs):
        super().__init__(api_key, api_base, model_name, **kwargs)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
            )
        return self._client

    def generate(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        tools: Optional[List[dict]] = None,
    ) -> str:
        trace_id = _get_trace_id()
        try:
            if tools:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice="auto",
                )
                msg = response.choices[0].message
                if msg.tool_calls:
                    tool_calls_data = []
                    for tc in msg.tool_calls:
                        tool_calls_data.append({
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        })
                    result = json.dumps({"tool_calls": tool_calls_data})
                    logger.info(f"[LLM:{trace_id}] {self._provider_name()}/{self.model_name} -> tool_calls ({len(tool_calls_data)})")
                    return result
                logger.info(f"[LLM:{trace_id}] {self._provider_name()}/{self.model_name} -> {len(msg.content or '')} chars")
                return msg.content or ""
            else:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                logger.info(f"[LLM:{trace_id}] {self._provider_name()}/{self.model_name} -> {len(response.choices[0].message.content)} chars")
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[LLM:{trace_id}] [{self._provider_name()}] generate error: {e}")
            raise

    def generate_stream(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        tools: Optional[List[dict]] = None,
    ) -> Generator[str, None, None]:
        trace_id = _get_trace_id()
        logger.info(f"[LLM:{trace_id}] Stream start: {self._provider_name()}/{self.model_name}")
        try:
            stream_kwargs = dict(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            if tools:
                stream_kwargs["tools"] = tools
                stream_kwargs["tool_choice"] = "auto"

            stream = self.client.chat.completions.create(**stream_kwargs)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                elif chunk.choices and chunk.choices[0].delta.tool_calls:
                    for tc in chunk.choices[0].delta.tool_calls:
                        tc_data = {"index": tc.index}
                        if tc.id:
                            tc_data["id"] = tc.id
                        if tc.type:
                            tc_data["type"] = tc.type
                        if tc.function:
                            tc_data["function"] = {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        yield json.dumps({"tool_call_chunk": tc_data})
        except Exception as e:
            logger.error(f"[LLM:{trace_id}] [{self._provider_name()}] generate_stream error: {e}")
            raise

    def health_check(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f"[{self._provider_name()}] health check failed: {e}")
            return False


class MiniMaxProvider(OpenAICompatibleProvider):
    """MiniMax 供应商 - 使用 OpenAI 兼容 API，默认指向 MiniMax 端点"""

    def __init__(self, api_key: str, api_base: str = "https://api.minimax.chat/v1",
                 model_name: str = "MiniMax-M2.5", **kwargs):
        super().__init__(api_key, api_base, model_name, **kwargs)

    def get_model_info(self) -> dict:
        return {
            "model_name": self.model_name,
            "provider_name": "minimax",
            "supports_streaming": True,
        }


class RawHTTPProvider(BaseLLMProvider):
    """纯 HTTP 实现——不依赖任何 SDK，展示底层协议理解"""

    def __init__(self, api_key: str, api_base: str, model_name: str, **kwargs):
        super().__init__(api_key, api_base, model_name, **kwargs)
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            })
        return self._session

    def generate(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        tools: Optional[List[dict]] = None,
    ) -> str:
        trace_id = _get_trace_id()
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            msg = data["choices"][0]["message"]
            if "tool_calls" in msg:
                tool_calls_data = []
                for tc in msg["tool_calls"]:
                    tool_calls_data.append({
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    })
                result = json.dumps({"tool_calls": tool_calls_data})
                logger.info(f"[LLM:{trace_id}] raw_http/{self.model_name} -> tool_calls ({len(tool_calls_data)})")
                return result
            logger.info(f"[LLM:{trace_id}] raw_http/{self.model_name} -> {len(msg['content'])} chars")
            return msg["content"]
        except requests.exceptions.Timeout:
            logger.error(f"[LLM:{trace_id}] [raw_http] Request timeout for {self.model_name}")
            raise RuntimeError("模型请求超时")
        except requests.exceptions.HTTPError as e:
            logger.error(f"[LLM:{trace_id}] [raw_http] HTTP error: {e.response.status_code}")
            raise
        except (KeyError, IndexError) as e:
            logger.error(f"[LLM:{trace_id}] [raw_http] Unexpected response format: {e}")
            raise RuntimeError("模型返回格式异常")

    def generate_stream(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        tools: Optional[List[dict]] = None,
    ) -> Generator[str, None, None]:
        trace_id = _get_trace_id()
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            logger.info(f"[LLM:{trace_id}] raw_http stream start")
            response = self.session.post(url, json=payload, stream=True, timeout=60)
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                        tool_calls = delta.get("tool_calls")
                        if tool_calls:
                            for tc in tool_calls:
                                yield json.dumps({"tool_call_chunk": tc})
                    except json.JSONDecodeError:
                        logger.warning(f"[LLM:{trace_id}] [raw_http] Failed to parse SSE chunk")
        except requests.exceptions.Timeout:
            raise RuntimeError("流式请求超时")
        except Exception as e:
            logger.error(f"[LLM:{trace_id}] [raw_http] Stream error: {e}")
            raise

    def health_check(self) -> bool:
        try:
            url = f"{self.api_base}/models"
            response = self.session.get(url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def get_model_info(self) -> dict:
        return {
            "model_name": self.model_name,
            "provider_name": "raw_http",
            "supports_streaming": True,
            "implementation": "requests (no SDK)",
        }


class LLMProviderFactory:
    """LLM 供应商工厂"""

    _providers = {
        "openai": OpenAICompatibleProvider,
        "minimax": MiniMaxProvider,
        "custom": OpenAICompatibleProvider,
        "raw_http": RawHTTPProvider,
        "qwen": OpenAICompatibleProvider,
    }

    @classmethod
    def create(cls, provider_name: str, api_key: str, api_base: str = "",
               model_name: str = "", **kwargs) -> BaseLLMProvider:
        provider_name = provider_name.lower().strip()

        provider_class = cls._providers.get(provider_name)
        if provider_class is None:
            logger.warning(f"Unknown provider '{provider_name}', falling back to OpenAICompatibleProvider")
            provider_class = OpenAICompatibleProvider
            if not api_base:
                api_base = "https://api.openai.com/v1"
            if not model_name:
                model_name = "gpt-4"

        if provider_name == "minimax":
            if not api_base:
                api_base = "https://api.minimax.chat/v1"
            if not model_name:
                model_name = "MiniMax-M2.5"
            return provider_class(api_key=api_key, api_base=api_base, model_name=model_name, **kwargs)

        if provider_name == "openai":
            if not api_base:
                api_base = "https://api.openai.com/v1"
            if not model_name:
                model_name = "gpt-4"
            return provider_class(api_key=api_key, api_base=api_base, model_name=model_name, **kwargs)

        if provider_name == "raw_http":
            if not api_base:
                api_base = "https://api.minimax.chat/v1"
            if not model_name:
                model_name = "MiniMax-M2.5"
            return provider_class(api_key=api_key, api_base=api_base, model_name=model_name, **kwargs)

        return provider_class(api_key=api_key, api_base=api_base, model_name=model_name, **kwargs)

    @classmethod
    def get_available_providers(cls) -> list:
        return list(cls._providers.keys())

    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        cls._providers[name.lower()] = provider_class

    @classmethod
    def get_default_fallbacks(cls) -> list:
        return ["minimax", "openai"]


class LLMProviderWithFallback:
    """带降级策略的 LLM 供应商包装器"""

    def __init__(self, primary: BaseLLMProvider, fallbacks: List[BaseLLMProvider] = None):
        self.primary = primary
        self.fallbacks = fallbacks or []
        self._last_used_provider = None

    @property
    def last_used_provider(self):
        return self._last_used_provider

    def generate(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        tools: Optional[List[dict]] = None,
    ) -> str:
        providers_to_try = [self.primary] + self.fallbacks

        for provider in providers_to_try:
            if not provider._circuit_breaker.can_execute():
                logger.warning(f"Provider {provider._provider_name()} circuit breaker OPEN, skipping")
                continue
            try:
                result = provider.generate(messages, temperature=temperature, max_tokens=max_tokens, tools=tools)
                provider._circuit_breaker.record_success()
                if self._last_used_provider and self._last_used_provider != provider:
                    logger.info(f"Fallback: switched from {self._last_used_provider._provider_name()} to {provider._provider_name()} (generate)")
                self._last_used_provider = provider
                return result
            except Exception as e:
                provider._circuit_breaker.record_failure()
                logger.warning(f"Provider {provider._provider_name()} failed (generate): {e}")
                if provider == providers_to_try[-1]:
                    raise
                logger.info(f"Falling back from {provider._provider_name()} to next provider")

        raise RuntimeError("All providers failed for generate()")

    def generate_stream(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        tools: Optional[List[dict]] = None,
    ) -> Generator[str, None, None]:
        providers_to_try = [self.primary] + self.fallbacks

        for provider in providers_to_try:
            try:
                if self._last_used_provider and self._last_used_provider != provider:
                    logger.info(f"Fallback: switched from {self._last_used_provider._provider_name()} to {provider._provider_name()} (generate_stream)")
                self._last_used_provider = provider
                yield from provider.generate_stream(messages, temperature=temperature, max_tokens=max_tokens, tools=tools)
                return
            except Exception as e:
                logger.warning(f"Provider {provider._provider_name()} failed (generate_stream): {e}")
                if provider == providers_to_try[-1]:
                    raise
                logger.info(f"Falling back from {provider._provider_name()} to next provider")

        raise RuntimeError("All providers failed for generate_stream()")

    def health_check(self) -> bool:
        if self.primary.health_check():
            return True
        for fallback in self.fallbacks:
            if fallback.health_check():
                return True
        return False

    def get_model_info(self) -> dict:
        return self.primary.get_model_info()
