"""
Ollama Provider - 本地离线模型
"""
import json
import requests
from typing import Dict, List, Generator

from .base import BaseProvider, AIMessage, AIResponse


class OllamaProvider(BaseProvider):
    """Ollama 本地模型接入"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "ollama"
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.api_url = f"{self.base_url}/api/chat"
        self.generate_url = f"{self.base_url}/api/generate"

    def validate_config(self) -> bool:
        """检查Ollama服务是否可用"""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def chat(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """非流式对话"""
        payload = {
            "model": self.model,
            "messages": self._build_messages_dict(messages),
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
            }
        }

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    self.api_url,
                    json=payload,
                    timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()

                return AIResponse(
                    content=data.get("message", {}).get("content", ""),
                    tokens_used=data.get("eval_count", 0),
                    model=self.model,
                    finish_reason="stop",
                    raw_response=data
                )
            except requests.exceptions.ConnectionError:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(
                        f"无法连接到Ollama服务 ({self.base_url}). "
                        "请确认Ollama已启动。"
                    )
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Ollama请求失败: {e}")

    def stream_chat(self, messages: List[AIMessage], **kwargs) -> Generator[str, None, None]:
        """流式对话"""
        payload = {
            "model": self.model,
            "messages": self._build_messages_dict(messages),
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
            }
        }

        try:
            resp = requests.post(
                self.api_url,
                json=payload,
                stream=True,
                timeout=self.timeout
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line.decode('utf-8'))
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue
        except requests.exceptions.ConnectionError:
            yield "[错误] 无法连接到Ollama服务，请确认服务已启动"
        except Exception as e:
            yield f"[错误] 请求异常: {e}"

    def list_models(self) -> List[str]:
        """列出本地可用模型"""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
