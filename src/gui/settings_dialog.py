"""
AI配置对话框
简洁的卡片式AI设置界面
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QLabel, QPushButton, QGroupBox
)
from PySide6.QtCore import Qt


class SettingsDialog(QDialog):
    """AI配置对话框"""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("AI 配置")
        self.setMinimumWidth(500)
        self._setup_style()
        self._setup_ui()
        self._load_config()

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a1a; }
            QLabel { color: #ccc; font-size: 14px; }
            QLineEdit {
                background: #2a2a2a; border: 1px solid #444;
                border-radius: 8px; padding: 10px;
                color: white; font-size: 14px;
            }
            QLineEdit:focus { border-color: #4a9eff; }
            QPushButton {
                border: none; border-radius: 8px;
                padding: 10px 20px; font-size: 14px; font-weight: bold;
            }
            QGroupBox {
                background: #222; border: 1px solid #333;
                border-radius: 12px; padding: 20px;
            }
            QGroupBox::title {
                color: #4a9eff; font-size: 14px;
                font-weight: bold; padding-left: 8px;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("AI 配置")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4a9eff;")
        layout.addWidget(title)

        desc = QLabel("配置 API、Key 和模型参数")
        desc.setStyleSheet("color: #888; font-size: 13px;")
        layout.addWidget(desc)

        # 表单
        group = QGroupBox("请求配置")
        form = QFormLayout(group)
        form.setSpacing(12)

        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("例如: https://api.deepseek.com/v1")
        form.addRow(QLabel("AI API:"), self.api_url_input)

        key_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-xxxxxxxxxx...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_layout.addWidget(self.api_key_input)

        self.key_toggle_btn = QPushButton("显示")
        self.key_toggle_btn.setStyleSheet("background: #333; color: #888; padding: 8px 16px; font-size: 12px;")
        self.key_toggle_btn.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.key_toggle_btn)
        form.addRow(QLabel("AI Key:"), key_layout)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("例如: deepseek-chat")
        form.addRow(QLabel("模型名称:"), self.model_input)

        layout.addWidget(group)

        # 测试连接
        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setStyleSheet("background: #4a9eff; color: white;")
        self.test_btn.clicked.connect(self._test_connection)
        test_layout.addWidget(self.test_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888;")
        test_layout.addWidget(self.status_label)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_reset = QPushButton("重置默认")
        self.btn_reset.setStyleSheet("background: #555; color: white;")
        self.btn_reset.clicked.connect(self._reset_default)
        btn_layout.addWidget(self.btn_reset)

        self.btn_save = QPushButton("保存配置")
        self.btn_save.setStyleSheet("background: #4caf50; color: white;")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _load_config(self):
        ai_cfg = self.config.get("ai", {})
        provider_cfg = ai_cfg.get("providers", {}).get(ai_cfg.get("default_provider", "custom"), {})
        self.api_url_input.setText(provider_cfg.get("base_url", "https://api.deepseek.com/v1"))
        self.api_key_input.setText(provider_cfg.get("api_key", ""))
        self.model_input.setText(provider_cfg.get("model", "deepseek-chat"))

    def _toggle_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.key_toggle_btn.setText("隐藏")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.key_toggle_btn.setText("显示")

    def _reset_default(self):
        self.api_url_input.setText("https://api.deepseek.com/v1")
        self.api_key_input.setText("")
        self.model_input.setText("deepseek-chat")
        self.status_label.setText("")

    def _test_connection(self):
        import requests

        url = self.api_url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        model = self.model_input.text().strip()

        if not url or not api_key:
            self.status_label.setText("请填写 API 和 Key")
            self.status_label.setStyleSheet("color: #f44336;")
            return

        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            resp = requests.post(
                f"{url}/chat/completions",
                headers=headers,
                json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
                timeout=10
            )

            if resp.status_code == 200:
                self.status_label.setText("连接成功")
                self.status_label.setStyleSheet("color: #4caf50;")
            else:
                self.status_label.setText(f"错误: {resp.status_code}")
                self.status_label.setStyleSheet("color: #f44336;")
        except requests.exceptions.Timeout:
            self.status_label.setText("连接超时")
            self.status_label.setStyleSheet("color: #f44336;")
        except Exception as e:
            self.status_label.setText(f"错误: {str(e)[:30]}")
            self.status_label.setStyleSheet("color: #f44336;")

    def get_config(self) -> dict:
        return {
            "base_url": self.api_url_input.text().strip(),
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_input.text().strip()
        }
