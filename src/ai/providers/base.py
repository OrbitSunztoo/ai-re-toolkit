"""
AI Provider 基类
定义所有AI服务提供商的统一接口
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Generator, Any
from dataclasses import dataclass


@dataclass
class AIResponse:
    """AI响应标准格式"""
    content: str
    tokens_used: int = 0
    model: str = ""
    finish_reason: str = ""
    raw_response: Any = None


@dataclass
class AIMessage:
    """对话消息"""
    role: str  # system, user, assistant
    content: str


class BaseProvider(ABC):
    """AI Provider 抽象基类"""

    def __init__(self, config: Dict):
        self.config = config
        self.name = "base"
        self.model = config.get("model", "")
        self.temperature = config.get("temperature", 0.3)
        self.timeout = config.get("timeout", 120)
        self.max_retries = config.get("max_retries", 3)

    @abstractmethod
    def chat(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """
        发送对话请求
        Args:
            messages: 消息列表
            **kwargs: 额外参数（temperature, max_tokens等）
        Returns:
            AIResponse
        """
        pass

    @abstractmethod
    def stream_chat(self, messages: List[AIMessage], **kwargs) -> Generator[str, None, None]:
        """
        流式对话请求
        Yields:
            文本片段
        """
        pass

    def validate_config(self) -> bool:
        """验证配置是否完整"""
        return True

    def count_tokens(self, text: str) -> int:
        """
        估算token数量
        简单实现：中文按字符数估算，英文按空格分词估算
        """
        if not text:
            return 0
        # 中文字符按1:1估算
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # 英文按空格分词 + 字符数/4
        english_tokens = len(text.split())
        # 粗略估算：总字符数 / 4 是比较通用的估算方式
        return max(len(text) // 4, chinese_chars + english_tokens)

    def truncate_history(self, messages: List[AIMessage],
                        max_tokens: int = 8000) -> List[AIMessage]:
        """截断过长的对话历史"""
        if len(messages) <= 2:
            return messages

        total = sum(self.count_tokens(m.content) for m in messages)
        # 保留system消息和最后几条
        while total > max_tokens and len(messages) > 2:
            removed = messages.pop(1)  # 保留system，移除最早的user/assistant
            total -= self.count_tokens(removed.content)

        return messages

    def _build_messages_dict(self, messages: List[AIMessage]) -> List[Dict]:
        """将AIMessage转换为API格式"""
        return [{"role": m.role, "content": m.content} for m in messages]
