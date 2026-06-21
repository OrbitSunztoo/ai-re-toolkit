"""
AI Provider 统一实现
合并所有 OpenAI 兼容 API 的 Provider，减少代码重复
"""
import json
import requests
from typing import Dict, List, Generator

from .base import BaseProvider, AIMessage, AIResponse


class OpenAIProvider(BaseProvider):
    """OpenAI / DeepSeek / Qwen / Kimi / Grok 等 OpenAI 兼容 API"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.api_url = f"{self.base_url}/chat/completions"
        self.name = config.get("_provider_name", "openai")

    def validate_config(self) -> bool:
        return bool(self.api_key) and len(self.api_key) > 10

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def chat(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        if not self.validate_config():
            raise ValueError(f"{self.name} API Key 未配置")

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": self._build_messages_dict(messages),
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": False
        }

        last_err = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    self.api_url,
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout
                )
                if resp.status_code == 401:
                    raise RuntimeError("API Key 无效或已过期")
                resp.raise_for_status()
                data = resp.json()

                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                return AIResponse(
                    content=msg.get("content", ""),
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                    model=data.get("model", self.model),
                    finish_reason=choice.get("finish_reason", ""),
                    raw_response=data
                )
            except requests.exceptions.HTTPError as e:
                if resp.status_code == 429 and attempt < self.max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"API请求失败: {e}")
            except Exception as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    continue
                raise RuntimeError(f"请求失败: {e}")

    def stream_chat(self, messages: List[AIMessage], **kwargs) -> Generator[str, None, None]:
        if not self.validate_config():
            yield f"[错误] {self.name} API Key 未配置"
            return

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": self._build_messages_dict(messages),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True
        }

        try:
            resp = requests.post(
                self.api_url,
                headers=self._headers(),
                json=payload,
                stream=True,
                timeout=self.timeout
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = line[6:]
                if line == "[DONE]":
                    break
                try:
                    data = json.loads(line)
                    chunk = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if chunk:
                        yield chunk
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            yield f"[错误] {e}"


# Provider 预设配置（合并 other_providers.py 的所有 Provider）
PROVIDER_PRESETS = {
    "ollama":     {"base_url": "http://localhost:11434",     "class": "ollama"},
    "openai":     {"base_url": "https://api.openai.com/v1",  "class": "openai"},
    "anthropic":  {"base_url": "https://api.anthropic.com",  "class": "anthropic"},
    "deepseek":   {"base_url": "https://api.deepseek.com/v1","class": "openai"},
    "qwen":       {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "class": "openai"},
    "kimi":       {"base_url": "https://api.moonshot.cn/v1", "class": "openai"},
    "grok":       {"base_url": "https://api.x.ai/v1",        "class": "openai"},
    "custom":     {"base_url": "",                            "class": "openai"},
}


# Provider 默认模型列表
PROVIDER_MODELS = {
    "ollama":    ["llama3", "llama3.2", "qwen2.5", "qwen2.5-coder", "deepseek-coder", "mistral", "phi3", "gemma2"],
    "openai":    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1-preview", "o1-mini"],
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
    "deepseek":  ["deepseek-chat", "deepseek-coder"],
    "qwen":      ["qwen-plus", "qwen-turbo", "qwen-max", "qwen-coder-plus"],
    "kimi":      ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    "grok":      ["grok-2", "grok-2-mini", "grok-beta"],
}


def make_provider(name: str, config: Dict) -> BaseProvider:
    """Provider 工厂函数 - 统一创建入口"""
    if name in ("ollama",):
        from .ollama_provider import OllamaProvider
        return OllamaProvider(config)

    # OpenAI 兼容系列
    preset = PROVIDER_PRESETS.get(name, {})
    if not preset.get("base_url") and "base_url" not in config:
        raise ValueError(f"未知的Provider: {name}")

    config = {**config, "_provider_name": name}
    if "base_url" not in config and preset.get("base_url"):
        config["base_url"] = preset["base_url"]
    return OpenAIProvider(config)
