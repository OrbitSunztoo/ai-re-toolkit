"""
通义千问 (Qwen) Provider - OpenAI兼容API
"""
import requests
from typing import Dict, List, Generator

from .openai_provider import OpenAIProvider


class QwenProvider(OpenAIProvider):
    """通义千问模型接入（阿里云）"""

    def __init__(self, config: Dict):
        # 通义千问使用 OpenAI 兼容 API
        super().__init__(config)
        self.name = "qwen"
        self.base_url = config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def validate_config(self) -> bool:
        """检查通义千问服务是否可用"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=10
            )
            return resp.status_code in [200, 401]  # 401表示key无效但服务正常
        except Exception:
            return False


class KimiProvider(OpenAIProvider):
    """Kimi (Moonshot) 模型接入"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "kimi"
        self.base_url = config.get("base_url", "https://api.moonshot.cn/v1")

    def validate_config(self) -> bool:
        """检查Kimi服务是否可用"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=10
            )
            return resp.status_code in [200, 401]
        except Exception:
            return False


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek 模型接入"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "deepseek"
        self.base_url = config.get("base_url", "https://api.deepseek.com/v1")

    def validate_config(self) -> bool:
        """检查DeepSeek服务是否可用"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=10
            )
            return resp.status_code in [200, 401]
        except Exception:
            return False


class GrokProvider(OpenAIProvider):
    """Grok (xAI) 模型接入"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "grok"
        self.base_url = config.get("base_url", "https://api.x.ai/v1")

    def validate_config(self) -> bool:
        """检查Grok服务是否可用"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=10
            )
            return resp.status_code in [200, 401]
        except Exception:
            return False
