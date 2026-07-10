"""多模态 LLM Provider——支持图像输入的 LLM 调用"""
import requests
import logging
from app.services.llm_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class MiniMaxVisionProvider(BaseLLMProvider):
    """MiniMax 视觉模型 Provider——支持图文混合输入"""

    def __init__(self, api_key: str, model_name: str = "MiniMax-VL", **kwargs):
        super().__init__(
            api_key=api_key,
            api_base="https://api.minimax.chat/v1",
            model_name=model_name,
            **kwargs
        )

    def generate_with_image(
        self,
        text: str,
        image_base64: str,
        temperature: float = 0.3,
        max_tokens: int = 1500
    ) -> str:
        """图文混合生成——核心面试加分项
        Args:
            text: 文字提示（如"请描述这张卡牌的效果"）
            image_base64: base64 编码的图片
            temperature: 温度参数
            max_tokens: 最大 token 数
        Returns:
            模型回答
        """
        url = f"{self.api_base}/chat/completions"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"[vision] Error: {e}")
            raise

    def generate(self, messages: list, temperature: float = 0.3, max_tokens: int = 1500) -> str:
        from app.services.llm_provider import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(
            api_key=self.api_key, api_base=self.api_base, model_name=self.model_name
        )
        return provider.generate(messages, temperature, max_tokens)

    def generate_stream(self, messages: list, temperature: float = 0.3, max_tokens: int = 1500):
        from app.services.llm_provider import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(
            api_key=self.api_key, api_base=self.api_base, model_name=self.model_name
        )
        yield from provider.generate_stream(messages, temperature, max_tokens)

    def health_check(self) -> bool:
        return True
