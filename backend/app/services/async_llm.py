"""
异步 LLM 调用模块 - Async LLM Provider

功能特性：
1. 使用 aiohttp 替换 requests，实现真正的异步 HTTP 请求
2. 流式异步读取（Server-Sent Events）
3. 异步重试机制（指数退避）
4. 异步连接池管理
5. 与现有 LLMProvider 接口兼容

使用示例：
```python
from app.services.async_llm import AsyncLLMProviderFactory

# 创建异步 LLM 提供者
llm = AsyncLLMProviderFactory.create(
    provider_name='openai',
    api_key='your-api-key',
    api_base='https://api.openai.com/v1',
    model_name='gpt-4'
)

# 异步生成文本
response = await llm.generate(
    messages=[{"role": "user", "content": "你好"}],
    temperature=0.7
)

# 异步流式生成
async for chunk in llm.generate_stream(
    messages=[{"role": "user", "content": "讲个故事"}],
    temperature=0.7
):
    print(chunk, end='', flush=True)
```
"""
import asyncio
import logging
import json
from typing import AsyncGenerator, List, Dict, Any, Optional
from abc import ABC, abstractmethod
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import aiohttp

logger = logging.getLogger(__name__)


def _get_trace_id() -> str:
    try:
        from app.core.trace import get_current_trace
        return get_current_trace()
    except Exception:
        return ''


class AsyncBaseLLMProvider(ABC):
    """异步 LLM 提供者抽象基类"""
    
    def __init__(self, api_key: str, api_base: str, model_name: str, **kwargs):
        self.api_key = api_key
        self.api_base = api_base.rstrip('/') if api_base else api_base
        self.model_name = model_name
        self.kwargs = kwargs
        
        # aiohttp 连接池配置
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(total=60.0)
        self._connector = aiohttp.TCPConnector(
            limit=10,  # 最大连接数
            limit_per_host=5,  # 每个主机的最大连接数
            ttl_dns_cache=300,  # DNS 缓存 TTL
        )
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp 会话（连接池复用）"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=self._timeout,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                }
            )
        return self._session
    
    async def close(self):
        """关闭会话，释放连接池资源"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1500,
        **kwargs
    ) -> str:
        """异步生成文本"""
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1500,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """异步流式生成文本"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """异步健康检查"""
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            'model_name': self.model_name,
            'provider_name': self._provider_name(),
            'supports_streaming': True,
        }
    
    def _provider_name(self) -> str:
        """获取提供者名称"""
        return self.__class__.__name__.replace('Async', '').replace('Provider', '').lower()


class AsyncOpenAICompatibleProvider(AsyncBaseLLMProvider):
    """
    异步 OpenAI 兼容 API 提供者
    
    适用于任何遵循 /v1/chat/completions 格式的 API：
    - OpenAI API
    - MiniMax
    - 其他兼容 API
    """
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            aiohttp.ClientError,
            asyncio.TimeoutError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1500,
        **kwargs
    ) -> str:
        session = await self._get_session()
        trace_id = _get_trace_id()

        url = f"{self.api_base}/chat/completions"
        payload = {
            'model': self.model_name,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            **kwargs
        }

        async with session.post(url, json=payload) as response:
            response.raise_for_status()
            data = await response.json()

            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                logger.info(f"[LLM:{trace_id}] {self._provider_name()}/{self.model_name} -> {len(content)} chars")
                return content
            else:
                raise ValueError(f"Unexpected response format: {data}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            aiohttp.ClientError,
            asyncio.TimeoutError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1500,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        session = await self._get_session()
        trace_id = _get_trace_id()
        logger.info(f"[LLM:{trace_id}] async_stream start: {self._provider_name()}/{self.model_name}")

        url = f"{self.api_base}/chat/completions"
        payload = {
            'model': self.model_name,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': True,
            **kwargs
        }

        async with session.post(url, json=payload) as response:
            response.raise_for_status()

            async for line in response.content:
                line = line.decode('utf-8').strip()

                if not line:
                    continue

                if line.startswith('data: '):
                    data = line[6:].strip()

                    if data == '[DONE]':
                        break

                    try:
                        chunk = json.loads(data)
                        if (
                            'choices' in chunk
                            and len(chunk['choices']) > 0
                            and 'delta' in chunk['choices'][0]
                            and 'content' in chunk['choices'][0]['delta']
                        ):
                            content = chunk['choices'][0]['delta']['content']
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
    
    async def health_check(self) -> bool:
        """异步健康检查"""
        try:
            session = await self._get_session()
            url = f"{self.api_base}/models"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False


class AsyncMiniMaxProvider(AsyncOpenAICompatibleProvider):
    """异步 MiniMax 提供者（默认指向 MiniMax 端点）"""
    
    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.minimax.chat/v1",
        model_name: str = "MiniMax-M2.5",
        **kwargs
    ):
        super().__init__(api_key, api_base, model_name, **kwargs)
    
    def get_model_info(self) -> Dict[str, Any]:
        return {
            'model_name': self.model_name,
            'provider_name': 'minimax',
            'supports_streaming': True,
        }


class AsyncLLMProviderFactory:
    """异步 LLM 提供者工厂类"""
    
    _providers = {
        'openai': AsyncOpenAICompatibleProvider,
        'minimax': AsyncMiniMaxProvider,
        'custom': AsyncOpenAICompatibleProvider,
    }
    
    @classmethod
    def create(
        cls,
        provider_name: str,
        api_key: str,
        api_base: str = "",
        model_name: str = "",
        **kwargs
    ) -> AsyncBaseLLMProvider:
        """
        创建异步 LLM 提供者实例
        
        Args:
            provider_name: 提供者名称 (openai, minimax, custom)
            api_key: API 密钥
            api_base: API 基础 URL
            model_name: 模型名称
            **kwargs: 其他参数
            
        Returns:
            异步 LLM 提供者实例
        """
        provider_name = provider_name.lower().strip()
        
        provider_class = cls._providers.get(provider_name)
        if provider_class is None:
            logger.warning(f"Unknown provider '{provider_name}', falling back to OpenAICompatibleProvider")
            provider_class = AsyncOpenAICompatibleProvider
            if not api_base:
                api_base = "https://api.openai.com/v1"
            if not model_name:
                model_name = "gpt-4"
        
        if provider_name == 'minimax':
            if not api_base:
                api_base = "https://api.minimax.chat/v1"
            if not model_name:
                model_name = "MiniMax-M2.5"
        
        if provider_name == 'openai':
            if not api_base:
                api_base = "https://api.openai.com/v1"
            if not model_name:
                model_name = "gpt-4"
        
        return provider_class(
            api_key=api_key,
            api_base=api_base,
            model_name=model_name,
            **kwargs
        )
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """获取可用的提供者列表"""
        return list(cls._providers.keys())
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """注册自定义提供者"""
        cls._providers[name.lower()] = provider_class


class AsyncLLMProviderWithFallback:
    """
    带降级策略的异步 LLM 提供者包装器
    
    支持多个 LLM 提供者，主提供者失败时自动尝试备用提供者
    """
    
    def __init__(
        self,
        primary: AsyncBaseLLMProvider,
        fallbacks: Optional[List[AsyncBaseLLMProvider]] = None,
    ):
        self.primary = primary
        self.fallbacks = fallbacks or []
        self._last_used_provider: Optional[AsyncBaseLLMProvider] = None
    
    @property
    def last_used_provider(self) -> Optional[AsyncBaseLLMProvider]:
        """获取最后使用的提供者"""
        return self._last_used_provider
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1500,
        **kwargs
    ) -> str:
        """
        异步生成文本（带降级策略）
        
        依次尝试主提供者和备用提供者，直到成功
        """
        providers_to_try = [self.primary] + self.fallbacks
        
        last_exception = None
        for provider in providers_to_try:
            try:
                result = await provider.generate(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                if self._last_used_provider != provider:
                    logger.info(f"Fallback: switched to {provider._provider_name()}")
                self._last_used_provider = provider
                return result
            except Exception as e:
                logger.warning(f"Provider {provider._provider_name()} failed: {e}")
                last_exception = e
                continue
        
        if last_exception:
            raise last_exception
        raise RuntimeError("All providers failed for generate()")
    
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1500,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        异步流式生成文本（带降级策略）
        """
        providers_to_try = [self.primary] + self.fallbacks
        
        last_exception = None
        for provider in providers_to_try:
            try:
                if self._last_used_provider != provider:
                    logger.info(f"Fallback: switched to {provider._provider_name()}")
                self._last_used_provider = provider
                
                async for chunk in provider.generate_stream(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                ):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Provider {provider._provider_name()} failed: {e}")
                last_exception = e
                continue
        
        if last_exception:
            raise last_exception
        raise RuntimeError("All providers failed for generate_stream()")
    
    async def health_check(self) -> bool:
        """检查健康状态"""
        if await self.primary.health_check():
            return True
        
        for fallback in self.fallbacks:
            if await fallback.health_check():
                return True
        
        return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取当前模型信息"""
        return self.primary.get_model_info()
    
    async def close_all(self):
        """关闭所有提供者的连接池"""
        await self.primary.close()
        for fallback in self.fallbacks:
            await fallback.close()


# 上下文管理器支持
class AsyncLLMContext:
    """
    异步 LLM 上下文管理器
    
    自动管理连接池生命周期，确保资源正确释放
    """
    
    def __init__(self, provider: AsyncBaseLLMProvider):
        self.provider = provider
    
    async def __aenter__(self):
        return self.provider
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.provider.close()
