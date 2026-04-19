"""AI 引擎 — 统一 LLM 调用接口，支持 GLM / MiniMax 切换"""

import base64
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class AIEngine:
    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("provider", "glm")
        self._client = None
        self._vision_client = None
        self._vision_key = None

        self._init_client()

    def _init_client(self):
        provider_cfg = self.config.get(self.provider, {})
        api_key = provider_cfg.get("api_key", "")
        base_url = provider_cfg.get("base_url", "")

        if not api_key or api_key == "YOUR_GLM_API_KEY":
            logger.warning(f"未配置 {self.provider} API Key，请在 config.yaml 中设置")

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = provider_cfg.get("model", "glm-5.1")
        logger.info(f"AI 引擎初始化: provider={self.provider}, model={self._model}")

        # 视觉模型
        vision_cfg = self.config.get("vision", {})
        if vision_cfg.get("enabled"):
            vision_key = vision_cfg.get("api_key") or api_key
            self._vision_client = OpenAI(
                api_key=vision_key,
                base_url="https://open.bigmodel.cn/api/paas/v4"
            )
            self._vision_model = vision_cfg.get("model", "glm-4v-flash")
            self._vision_key = vision_key
            logger.info(f"视觉模型: {self._vision_model}")

    @property
    def vision_enabled(self) -> bool:
        return self._vision_client is not None

    def chat(self, messages: list[dict], temperature: float = 0.8, max_tokens: int = 200) -> str:
        """调用大模型文本对话"""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content.strip()
            logger.debug(f"AI 响应: {content[:100]}...")
            return content
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return ""

    def vision_analyze(self, image_path: str, prompt: str) -> str:
        """调用视觉模型分析截图"""
        if not self._vision_client:
            return ""

        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        },
                    ],
                }
            ]

            response = self._vision_client.chat.completions.create(
                model=self._vision_model,
                messages=messages,
                temperature=0.5,
                max_tokens=300,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"视觉分析失败: {e}")
            return ""

    def switch_provider(self, provider: str):
        """切换 LLM 提供者"""
        if provider != self.provider:
            self.provider = provider
            self._init_client()
