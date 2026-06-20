"""
日志工具
提供统一的日志记录，支持GUI集成
"""
import logging
import sys
from typing import Optional, Callable
from datetime import datetime
from pathlib import Path


class GUILogHandler(logging.Handler):
    """自定义日志处理器，将日志转发到GUI"""

    def __init__(self, callback: Optional[Callable[[str], None]] = None):
        super().__init__()
        self.callback = callback
        self.max_lines = 5000
        self._buffer: list[str] = []

    def emit(self, record):
        msg = self.format(record)
        self._buffer.append(msg)
        if len(self._buffer) > self.max_lines:
            self._buffer = self._buffer[-self.max_lines:]
        if self.callback:
            self.callback(msg)

    def get_buffer(self) -> str:
        return '\n'.join(self._buffer)

    def clear(self):
        self._buffer.clear()


class AppLogger:
    """应用日志管理器"""

    _instance: Optional['AppLogger'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.logger = logging.getLogger("AI-RE-Toolkit")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # 格式
        self.formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(message)s",
            datefmt="%H:%M:%S"
        )

        # 控制台输出
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setLevel(logging.INFO)
        self.console_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.console_handler)

        # GUI处理器（初始无回调）
        self.gui_handler = GUILogHandler()
        self.gui_handler.setLevel(logging.DEBUG)
        self.gui_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.gui_handler)

        # 文件日志
        self.file_handler: Optional[logging.FileHandler] = None

    def set_gui_callback(self, callback: Callable[[str], None]):
        """设置GUI日志回调"""
        self.gui_handler.callback = callback

    def enable_file_logging(self, log_dir: str = "./logs"):
        """启用文件日志"""
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = Path(log_dir) / f"aire_{timestamp}.log"

        self.file_handler = logging.FileHandler(log_file, encoding='utf-8')
        self.file_handler.setLevel(logging.DEBUG)
        self.file_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s"
        ))
        self.logger.addHandler(self.file_handler)
        self.info(f"日志文件: {log_file}")

    def debug(self, msg: str):
        self.logger.debug(msg)

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def critical(self, msg: str):
        self.logger.critical(msg)

    def get_gui_buffer(self) -> str:
        """获取GUI日志缓冲区内容"""
        return self.gui_handler.get_buffer()

    def clear_gui_buffer(self):
        """清空GUI日志缓冲区"""
        self.gui_handler.clear()


# 全局日志实例
log = AppLogger()
