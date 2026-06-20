"""
OpenAI Compatible Provider
支持 OpenAI、Azure、以及兼容OpenAI API格式的第三方服务
"""
import json
import requests
from typing import Dict, List, Generator

from .base import BaseProvider, AIMessage, AIResponse


class OpenAIProvider(BaseProvider):
    """OpenAI API 接入"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "openai"
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.api_url = f"{self.base_url}/chat/completions"

    def validate_config(self) -> bool:
        """验证API Key是否配置"""
        return bool(self.api_key) and len(self.api_key) > 10

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def chat(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """非流式对话"""
        if not self.validate_config():
            raise ValueError("OpenAI API Key 未配置")

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": self._build_messages_dict(messages),
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": False
        }

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    self.api_url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=self.timeout
                )
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
                if resp.status_code == 401:
                    raise RuntimeError("API Key 无效或已过期")
                elif resp.status_code == 429:
                    if attempt < self.max_retries - 1:
                        import time
                        time.sleep(2 ** attempt)
                        continue
                raise RuntimeError(f"API请求失败: {e}")
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"请求失败: {e}")

    def stream_chat(self, messages: List[AIMessage], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        if not self.validate_config():
            yield "[错误] OpenAI API Key 未配置"
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
                headers=self._get_headers(),
                json=payload,
                stream=True,
                timeout=self.timeout
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode('utf-8')
                if line.startswith("data: "):
                    line = line[6:]
                if line == "[DONE]":
                    break
                try:
                    data = json.loads(line)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    chunk = delta.get("content", "")
                    if chunk:
                        yield chunk
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            yield f"[错误] 请求异常: {e}"


class AnthropicProvider(OpenAIProvider):
    """Anthropic Claude API（兼容OpenAI格式）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "anthropic"
        self.base_url = config.get("base_url", "https://api.anthropic.com/v1")
        self.api_url = f"{self.base_url}/messages"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

    def chat(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Claude API 调用"""
        if not self.validate_config():
            raise ValueError("Anthropic API Key 未配置")

        # 分离system消息
        system_msg = ""
        chat_msgs = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                chat_msgs.append({"role": m.role, "content": m.content})

        payload = {
            "model": kwargs.get("model", self.model),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", self.temperature),
            "messages": chat_msgs
        }
        if system_msg:
            payload["system"] = system_msg

        try:
            resp = requests.post(
                self.api_url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()

            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")

            return AIResponse(
                content=content,
                tokens_used=data.get("usage", {}).get("input_tokens", 0) +
                           data.get("usage", {}).get("output_tokens", 0),
                model=data.get("model", self.model),
                finish_reason=data.get("stop_reason", ""),
                raw_response=data
            )
        except Exception as e:
            raise RuntimeError(f"Anthropic请求失败: {e}")
