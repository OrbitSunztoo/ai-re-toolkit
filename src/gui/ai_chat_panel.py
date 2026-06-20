"""
AI 对话面板
提供实时 AI 指令交互界面
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QThread, QSize
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat


class ChatMessageWidget(QWidget):
    """聊天消息组件"""

    def __init__(self, text: str, is_user: bool = True, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self._setup_ui(text)

    def _setup_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # 标签
        label = QLabel("你" if self.is_user else "AI")
        label.setStyleSheet(f"""
            color: {'#4a9eff' if self.is_user else '#4caf50'};
            font-weight: bold;
            font-size: 12px;
        """)

        # 消息内容
        content = QTextEdit()
        content.setReadOnly(True)
        content.setPlainText(text)
        content.setStyleSheet("""
            QTextEdit {
                background: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 8px;
                color: #e0e0e0;
            }
        """)

        if self.is_user:
            layout.addWidget(label)
            layout.addWidget(content)
        else:
            layout.addWidget(label)
            layout.addWidget(content)

        self.setLayout(layout)


class AIChatPanel(QWidget):
    """AI 对话面板"""
    command_sent = Signal(str)  # 发送命令信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_context = ""
        self.messages = []  # 存储对话历史
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 标题栏
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)

        title = QLabel("AI 指令控制台")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #4a9eff;")

        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_clear = QPushButton("清空")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background: #444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: #555;
            }
        """)
        self.btn_clear.clicked.connect(self._clear_chat)
        header_layout.addWidget(self.btn_clear)

        layout.addWidget(header)

        # 对话区域
        self.chat_area = QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setStyleSheet("""
            QScrollArea {
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(12)

        self.chat_area.setWidget(self.chat_container)
        layout.addWidget(self.chat_area)

        # 快捷指令提示
        hint = QLabel("💡 示例: '分析这个文件' | '帮我修改APK的包名' | '脱壳这个EXE'")
        hint.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
        layout.addWidget(hint)

        # 输入区域
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 4, 0, 0)
        input_layout.setSpacing(8)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入指令，让AI执行操作...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 10px 12px;
                color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #4a9eff;
            }
            QLineEdit:disabled {
                background: #222;
                color: #666;
            }
        """)
        self.input_box.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_box)

        self.btn_send = QPushButton("发送")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background: #4a9eff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #5aafff;
            }
            QPushButton:disabled {
                background: #333;
                color: #666;
            }
        """)
        self.btn_send.clicked.connect(self._send_message)
        input_layout.addWidget(self.btn_send)

        layout.addWidget(input_widget)

    def set_context(self, context: str):
        """设置上下文（当前分析的文件信息）"""
        self.current_context = context

    def _send_message(self):
        """发送消息"""
        message = self.input_box.text().strip()
        if not message:
            return

        # 检查是否已有工作线程在运行
        if self.worker is not None and self.worker.isRunning():
            return

        # 清空输入框
        self.input_box.clear()

        # 添加用户消息
        self._add_message(message, is_user=True)

        # 显示等待状态
        self._set_loading(True)

        # 添加AI等待消息
        self._add_message("AI正在分析中，请稍候...", is_user=False)

    def _on_response(self, response: str, user_message: str):
        """处理 AI 响应"""
        self._set_loading(False)

        # 保存到历史
        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({"role": "assistant", "content": response})

        # 添加 AI 消息
        self._add_message(response, is_user=False)

        self.worker = None

    def _on_error(self, error: str):
        """处理错误"""
        self._set_loading(False)
        self._add_message(f"❌ 错误: {error}", is_user=False)
        self.worker = None

    def _add_message(self, text: str, is_user: bool):
        """添加消息到聊天区域"""
        msg = ChatMessageWidget(text, is_user)
        self.chat_layout.addWidget(msg)

        # 滚动到底部
        self.chat_area.verticalScrollBar().setValue(
            self.chat_area.verticalScrollBar().maximum()
        )

    def _set_loading(self, loading: bool):
        """设置加载状态"""
        self.input_box.setDisabled(loading)
        self.btn_send.setDisabled(loading)
        if loading:
            self.btn_send.setText("思考中...")
        else:
            self.btn_send.setText("发送")

    def _clear_chat(self):
        """清空对话"""
        # 移除所有消息组件
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.messages.clear()
        self._add_message("对话已清空。你可以继续输入新指令。", is_user=False)

    def get_conversation_history(self) -> str:
        """获取对话历史"""
        return "\n".join([f"{m['role']}: {m['content']}" for m in self.messages])
