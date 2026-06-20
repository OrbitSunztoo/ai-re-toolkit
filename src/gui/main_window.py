"""
主窗口
整合所有面板，提供完整的用户界面
"""
import os
import json
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu, QMessageBox,
    QFileDialog, QProgressDialog, QDialog, QComboBox,
    QDialogButtonBox, QFormLayout, QLineEdit, QLabel, QGroupBox,
    QPushButton
)
from PySide6.QtCore import Qt, QThread, Signal, QSettings
from PySide6.QtGui import QFont, QAction

from .file_panel import FilePanel
from .log_panel import LogPanel
from .code_viewer import CodeViewer
from .ai_chat_panel import AIChatPanel
from src.utils.logger import log
from src.core.file_analyzer import analyze_file
from src.ai.scheduler import AIScheduler, ProviderFactory, AnalysisSession
from src.tools.executor import ToolExecutor
from src.tools.registry import ToolRegistry


class AnalysisWorker(QThread):
    """后台分析工作线程"""
    log_signal = Signal(str)  # 日志信号
    progress_signal = Signal(str)  # 进度信号
    finished_signal = Signal(AnalysisSession)
    error = Signal(str)

    def __init__(self, scheduler: AIScheduler, file_path: str, file_info: dict):
        super().__init__()
        self.scheduler = scheduler
        self.file_path = file_path
        self.file_info = file_info

    def run(self):
        try:
            # 注册信号回调替代直接回调
            self.scheduler.register_progress_callback(self._on_progress)
            session = self.scheduler.start_analysis(self.file_path, self.file_info)
            self.finished_signal.emit(session)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, message: str):
        """进度回调 - 通过信号发送到主线程"""
        self.log_signal.emit(message)
        self.progress_signal.emit(message)


class SettingsDialog(QDialog):
    """AI配置对话框 - 简洁卡片式"""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("AI 配置")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog { background: #1a1a1a; }
            QLabel { color: #ccc; font-size: 14px; }
            QLineEdit { 
                background: #2a2a2a; 
                border: 1px solid #444; 
                border-radius: 8px; 
                padding: 10px; 
                color: white; 
                font-size: 14px;
            }
            QLineEdit:focus { border-color: #4a9eff; }
            QPushButton { 
                border: none; 
                border-radius: 8px; 
                padding: 10px 20px; 
                font-size: 14px; 
                font-weight: bold;
            }
            QGroupBox { 
                background: #222; 
                border: 1px solid #333; 
                border-radius: 12px; 
                padding: 20px;
            }
            QGroupBox::title { 
                color: #4a9eff; 
                font-size: 14px; 
                font-weight: bold; 
                padding-left: 8px;
            }
        """)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title = QLabel("🤖 AI 配置")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4a9eff;")
        main_layout.addWidget(title)

        desc = QLabel("配置 API、Key 和模型参数")
        desc.setStyleSheet("color: #888; font-size: 13px;")
        main_layout.addWidget(desc)

        request_group = QGroupBox("⚙️ 请求配置")
        request_layout = QFormLayout(request_group)
        request_layout.setSpacing(12)

        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("例如: https://api.deepseek.com/v1")
        request_layout.addRow(QLabel("AI API:"), self.api_url_input)

        key_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-xxxxxxxxxx...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_layout.addWidget(self.api_key_input)

        self.key_toggle_btn = QPushButton("显示")
        self.key_toggle_btn.setStyleSheet("background: #333; color: #888; padding: 8px 16px; font-size: 12px;")
        self.key_toggle_btn.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.key_toggle_btn)
        request_layout.addRow(QLabel("AI Key:"), key_layout)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("例如: deepseek-chat")
        request_layout.addRow(QLabel("模型名称:"), self.model_input)

        main_layout.addWidget(request_group)

        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("🔗 测试连接")
        self.test_btn.setStyleSheet("background: #4a9eff; color: white;")
        self.test_btn.clicked.connect(self._test_connection)
        test_layout.addWidget(self.test_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888;")
        test_layout.addWidget(self.status_label)
        test_layout.addStretch()
        main_layout.addLayout(test_layout)

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

        main_layout.addLayout(btn_layout)

    def _load_config(self):
        """加载当前配置"""
        ai_cfg = self.config.get("ai", {})
        provider_cfg = ai_cfg.get("providers", {}).get(ai_cfg.get("default_provider", "custom"), {})

        self.api_url_input.setText(provider_cfg.get("base_url", "https://api.deepseek.com/v1"))
        self.api_key_input.setText(provider_cfg.get("api_key", ""))
        self.model_input.setText(provider_cfg.get("model", "deepseek-chat"))

    def _toggle_key_visibility(self):
        """切换 API Key 显示/隐藏"""
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.key_toggle_btn.setText("隐藏")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.key_toggle_btn.setText("显示")

    def _reset_default(self):
        """重置为默认值"""
        self.api_url_input.setText("https://api.deepseek.com/v1")
        self.api_key_input.setText("")
        self.model_input.setText("deepseek-chat")
        self.status_label.setText("")

    def _test_connection(self):
        """测试连接"""
        import requests

        url = self.api_url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        model = self.model_input.text().strip()

        if not url or not api_key:
            self.status_label.setText("❌ 请填写 API 和 Key")
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
                self.status_label.setText("✅ 连接成功")
                self.status_label.setStyleSheet("color: #4caf50;")
            else:
                self.status_label.setText(f"❌ 错误: {resp.status_code}")
                self.status_label.setStyleSheet("color: #f44336;")

        except requests.exceptions.Timeout:
            self.status_label.setText("❌ 连接超时")
            self.status_label.setStyleSheet("color: #f44336;")
        except Exception as e:
            self.status_label.setText(f"❌ {str(e)[:30]}")
            self.status_label.setStyleSheet("color: #f44336;")

    def get_config(self) -> dict:
        """获取配置"""
        cfg = {
            "base_url": self.api_url_input.text().strip(),
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_input.text().strip()
        }
        return cfg


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI-RE Toolkit v0.1.0")
        self.setMinimumSize(1400, 900)

        # 加载配置
        self.config = self._load_config()

        # 核心组件
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.scheduler: AIScheduler = None
        self._init_scheduler()

        # 工作线程
        self.worker: AnalysisWorker = None

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._apply_theme()

        log.set_gui_callback(self._on_log)
        log.info("AI-RE Toolkit 已启动")

    def _load_config(self) -> dict:
        """加载应用配置"""
        try:
            with open("config/app_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        """保存配置"""
        try:
            with open("config/app_config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"保存配置失败: {e}")

    def _init_scheduler(self):
        """初始化AI调度器"""
        try:
            ai_cfg = self.config.get("ai", {})
            provider_name = ai_cfg.get("default_provider", "ollama")
            provider_cfg = ai_cfg.get("providers", {}).get(provider_name, {})

            provider = ProviderFactory.create(provider_name, provider_cfg)
            self.scheduler = AIScheduler(provider)
            self.scheduler.register_tool_executor(
                lambda name, params: self.tool_executor.execute(name, params)
            )
            self.scheduler.register_progress_callback(self._on_ai_progress)
            log.info(f"AI调度器已初始化: {provider_name}")
        except Exception as e:
            log.error(f"AI调度器初始化失败: {e}")
            self.scheduler = None

    def _setup_ui(self):
        """设置主界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 左侧：文件面板
        self.file_panel = FilePanel()
        self.file_panel.file_loaded.connect(self._on_file_loaded)
        self.file_panel.start_analysis.connect(self._start_analysis)

        # 中间：日志面板
        self.log_panel = LogPanel()

        # 右侧：代码查看器 + AI对话
        self.code_viewer = CodeViewer()
        self.ai_chat = AIChatPanel()

        # AI对话面板的worker需要使用主窗口的scheduler
        self.ai_chat.worker = None
        self.ai_chat._send_message = lambda: self._send_chat_message()

        # 使用Splitter分割
        left_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_splitter.addWidget(self.file_panel)
        left_splitter.setSizes([300])

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self.ai_chat)
        right_splitter.addWidget(self.log_panel)
        right_splitter.addWidget(self.code_viewer)
        right_splitter.setSizes([300, 250, 350])

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([300, 1000])

        main_layout.addWidget(main_splitter)

    def _setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        open_action = QAction("打开文件", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.file_panel._on_select_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")

        clear_cache = QAction("清除缓存", self)
        clear_cache.triggered.connect(self._clear_cache)
        tools_menu.addAction(clear_cache)

        # 设置菜单
        settings_menu = menubar.addMenu("设置")

        ai_settings = QAction("AI配置", self)
        ai_settings.triggered.connect(self._show_settings)
        settings_menu.addAction(ai_settings)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_statusbar(self):
        """设置状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪")

        # AI状态
        self.lbl_ai_status = QLabel("AI: 未连接")
        self.statusbar.addPermanentWidget(self.lbl_ai_status)

        # 更新AI状态
        if self.scheduler:
            self.lbl_ai_status.setText(f"AI: {self.scheduler.provider.name}")

    def _apply_theme(self):
        """应用暗色主题"""
        self.setStyleSheet("""
            QMainWindow {
                background: #1a1a1a;
            }
            QWidget {
                background: #1a1a1a;
                color: #e0e0e0;
            }
            QMenuBar {
                background: #252525;
                color: #e0e0e0;
                border-bottom: 1px solid #333;
            }
            QMenuBar::item:selected {
                background: #3a3a3a;
            }
            QMenu {
                background: #2a2a2a;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background: #3a3a3a;
            }
            QStatusBar {
                background: #252525;
                color: #888;
                border-top: 1px solid #333;
            }
            QSplitter::handle {
                background: #333;
            }
        """)

    def _on_file_loaded(self, path: str, info: dict):
        """文件加载回调"""
        log.info(f"加载文件: {path}")
        log.info(f"文件类型: {info.get('type_name')}")

        # 显示基本信息到代码区
        preview = f"""/*
 * 文件: {os.path.basename(path)}
 * 类型: {info.get('type_name', 'unknown')}
 * 大小: {info.get('size', 0)} bytes
 * 架构: {info.get('arch', 'N/A')}
 * 加壳: {'是' if info.get('is_packed') else '否'}
 * 魔数: {info.get('magic', 'N/A')[:32]}...
 */

"""
        self.code_viewer.set_code(preview)

        # 更新AI对话上下文
        context = f"""当前分析文件:
- 路径: {path}
- 类型: {info.get('type_name', 'unknown')}
- 大小: {info.get('size', 0)} bytes
- 架构: {info.get('arch', 'N/A')}
- 加壳: {'是' if info.get('is_packed') else '否'}
- 建议工具: {', '.join(info.get('suggested_tools', []))}

可用工具:
- Windows: pefile_analyze, detect_it_easy, upx, ghidra_analyze, strings
- Android: apk_analyze, jadx, apktool, read_file
- iOS: ipa_analyze, strings

支持操作: 分析、反编译、脱壳、修改文件、重打包APK
"""
        self.ai_chat.set_context(context)

    def _start_analysis(self):
        """开始AI分析"""
        if not self.scheduler:
            QMessageBox.warning(self, "错误", "AI调度器未初始化")
            return

        file_path = self.file_panel.current_file
        file_info = self.file_panel.file_info

        if not file_path or not file_info:
            QMessageBox.warning(self, "错误", "请先选择文件")
            return

        # 禁用按钮
        self.file_panel.btn_analyze.setEnabled(False)
        self.log_panel.clear()
        log.info("=" * 50)
        log.info("开始AI自动化分析")
        log.info("=" * 50)

        # 启动后台线程
        self.worker = AnalysisWorker(self.scheduler, file_path, file_info)
        # 使用 QueuedConnection 确保在主线程执行
        self.worker.log_signal.connect(self._on_log, Qt.ConnectionType.QueuedConnection)
        self.worker.progress_signal.connect(self._on_progress_update, Qt.ConnectionType.QueuedConnection)
        self.worker.finished_signal.connect(self._on_analysis_finished, Qt.ConnectionType.QueuedConnection)
        self.worker.error.connect(self._on_analysis_error, Qt.ConnectionType.QueuedConnection)
        self.worker.start()

    def _on_analysis_finished(self, session: AnalysisSession):
        """分析完成回调"""
        self.file_panel.btn_analyze.setEnabled(True)
        self.file_panel.set_progress(100)

        log.info("=" * 50)
        log.info("分析完成")
        log.info(f"总步骤: {session.step_count}")
        log.info("=" * 50)

        # 显示最终报告
        if session.final_report:
            self.code_viewer.set_code(session.final_report)
            log.info("最终报告已生成")

        # 显示工具输出摘要
        if session.tool_outputs:
            summary = "\n\n/* 工具执行摘要 */\n"
            for out in session.tool_outputs:
                tool = out.get("tool", "unknown")
                result = out.get("result", {})
                success = result.get("success", False)
                duration = result.get("duration", 0)
                summary += f"// {tool}: {'成功' if success else '失败'} ({duration:.1f}s)\n"
            self.code_viewer.append(summary)

        QMessageBox.information(self, "完成", "AI分析已完成！")

    def _on_analysis_error(self, error: str):
        """分析错误回调"""
        self.file_panel.btn_analyze.setEnabled(True)
        log.error(f"分析错误: {error}")
        QMessageBox.critical(self, "错误", f"分析过程中出错:\n{error}")

    def _on_ai_progress(self, message: str):
        """AI进度回调 - 已弃用，使用 _on_progress_update"""
        pass

    def _on_progress_update(self, message: str):
        """进度更新回调"""
        log.info(f"[AI] {message}")
        # 更新进度条
        if self.worker and self.worker.isRunning():
            progress = min(self.file_panel.progress.value() + 5, 95)
            self.file_panel.set_progress(progress)

    def _on_log(self, message: str):
        """日志回调"""
        level = "info"
        if "[错误]" in message or "ERROR" in message:
            level = "error"
        elif "[警告]" in message or "WARNING" in message:
            level = "warning"
        elif "完成" in message:
            level = "success"
        elif "[AI]" in message:
            level = "ai"

        self.log_panel.append(message, level)
        self.statusbar.showMessage(message[:100])

    def _clear_cache(self):
        """清除工具缓存"""
        self.tool_executor.clear_cache()
        log.info("工具缓存已清除")
        QMessageBox.information(self, "提示", "缓存已清除")

    def _show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            cfg = dialog.get_config()
            self.config["ai"] = {
                "default_provider": "custom",
                "max_retries": 3,
                "timeout": 120,
                "providers": {
                    "custom": cfg
                }
            }
            self._save_config()
            self._init_scheduler()
            QMessageBox.information(self, "提示", "设置已保存，AI配置已更新")

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 AI-RE Toolkit",
            """<h2>AI-RE Toolkit v0.1.0</h2>
            <p>一体化AI反编译工具箱</p>
            <p>内置全套逆向工具链 + AI调度层 + GUI界面</p>
            <p>AI自动调用拆解、反编译、分析、解混淆全套工具</p>
            <hr>
            <p><b>声明：</b>本软件仅用于自有程序分析和授权安全审计，
            严禁用于非法破解闭源商用软件。</p>
            """
        )

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认",
                "分析正在进行中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()

    def _send_chat_message(self):
        """发送AI对话消息 - 使用持续执行Worker"""
        message = self.ai_chat.input_box.text().strip()
        if not message:
            return

        # 检查是否已有工作线程在运行
        if self.ai_chat.worker is not None and self.ai_chat.worker.isRunning():
            self.ai_chat._add_message("⚠️ AI正在处理中，请等待完成后再发送新指令", is_user=False)
            return

        # 检查AI调度器是否初始化
        if not self.scheduler:
            self.ai_chat._add_message("❌ AI未配置，请先在设置中配置AI", is_user=False)
            return

        # 清空输入框
        self.ai_chat.input_box.clear()

        # 添加用户消息
        self.ai_chat._add_message(message, is_user=True)
        self.ai_chat.messages.append({"role": "user", "content": message})

        # 显示等待状态
        self.ai_chat._set_loading(True)

        log.info(f"[Chat] 用户: {message}")

        # 构建完整上下文（包含文件信息和对话历史）
        full_context = self.ai_chat.current_context
        if len(self.ai_chat.messages) > 1:
            full_context += "\n\n对话历史:\n" + self.ai_chat.get_conversation_history()

        file_path = getattr(self.file_panel, 'current_file', '')

        # 停止可能存在的旧线程
        if self.ai_chat.worker is not None:
            try:
                self.ai_chat.worker.stop()
                self.ai_chat.worker.wait(1000)
            except:
                pass

        # 启动持续执行工作线程
        self.ai_chat.worker = PersistentChatWorker(
            self.scheduler, self.tool_executor, message, full_context, file_path
        )
        self.ai_chat.worker.step_completed.connect(self._on_chat_step)
        self.ai_chat.worker.all_done.connect(self._on_chat_all_done)
        self.ai_chat.worker.log_signal.connect(self._on_log)
        self.ai_chat.worker.error.connect(self._on_chat_error)
        self.ai_chat.worker.start()

    def _on_chat_step(self, step: int, reasoning: str, result: str):
        """处理每步执行结果"""
        msg_text = f"步骤 {step}: {reasoning}\n{result}"
        self.ai_chat._add_message(msg_text, is_user=False)
        self.ai_chat.messages.append({"role": "assistant", "content": msg_text})

        # 更新代码查看器显示最新工具输出
        if "工具" in result and "\n" in result:
            lines = result.split("\n")
            if len(lines) > 1:
                output = "\n".join(lines[1:])
                if len(output) > 50:
                    self.code_viewer.set_code(output)

        log.info(f"[Chat] 步骤{step}: {reasoning[:60]}")

    def _on_chat_all_done(self, final_report: str, full_log: str):
        """任务全部完成"""
        self.ai_chat._set_loading(False)

        # 添加最终报告
        report_msg = f"✅ 最终报告:\n{final_report}"
        self.ai_chat._add_message(report_msg, is_user=False)
        self.ai_chat.messages.append({"role": "assistant", "content": report_msg})

        # 显示到代码查看器
        self.code_viewer.set_code(final_report)

        log.info("[Chat] 任务完成")
        self.ai_chat.worker = None

    def _on_chat_error(self, error: str):
        """处理聊天错误"""
        self.ai_chat._set_loading(False)
        self.ai_chat._add_message(f"❌ 错误: {error}", is_user=False)
        log.error(f"[Chat] 错误: {error}")
        self.ai_chat.worker = None


class PersistentChatWorker(QThread):
    """持续聊天工作线程 - 支持Agent多步循环执行"""
    step_completed = Signal(int, str, str)  # 步骤号, 推理, 结果摘要
    all_done = Signal(str, str)  # 最终报告, 完整日志
    log_signal = Signal(str)
    error = Signal(str)

    def __init__(self, scheduler, tool_executor, message: str, context: str = "",
                 file_path: str = "", max_steps: int = 15):
        super().__init__()
        self.scheduler = scheduler
        self.tool_executor = tool_executor
        self.message = message
        self.context = context
        self.file_path = file_path
        self.max_steps = max_steps
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            if not self.scheduler:
                self.error.emit("AI调度器未初始化，请先配置AI")
                return

            from src.ai.providers.base import AIMessage

            messages = [AIMessage("system", self.scheduler.system_prompt)]

            initial_prompt = self.context
            if self.file_path:
                initial_prompt += f"\n\n当前文件: {self.file_path}"
            initial_prompt += (
                f"\n\n用户指令: {self.message}\n\n"
                "请分析并执行操作。每步只返回一个JSON指令。"
                "如果需要继续执行更多步骤，在reasoning中说明计划，系统会自动反馈结果让你继续。"
                "达到最终结论时设置 is_complete 为 true。"
            )
            messages.append(AIMessage("user", initial_prompt))

            full_log = []
            final_report = ""

            for step in range(1, self.max_steps + 1):
                if self._stop:
                    full_log.append("用户中断")
                    break

                self.log_signal.emit(f"=== AI 步骤 {step} ===")

                response = self.scheduler.provider.chat(messages)
                content = response.content

                try:
                    instruction = self.scheduler._parse_ai_response(content)
                except ValueError as e:
                    full_log.append(f"步骤{step}: 解析AI响应失败 - {e}")
                    self.step_completed.emit(step, "解析错误", f"AI返回无效JSON: {str(e)[:100]}")
                    final_report = f"分析中断: AI返回无效JSON"
                    break

                action = instruction.get("action", "")
                reasoning = instruction.get("reasoning", "")
                is_complete = instruction.get("is_complete", False)

                self.log_signal.emit(f"动作: {action} | 推理: {reasoning[:80]}")

                if is_complete or action == "report":
                    final_report = instruction.get("message", "分析完成")
                    full_log.append(f"步骤{step}: 完成")
                    self.step_completed.emit(step, reasoning, f"完成: {final_report[:500]}")
                    break

                if action == "ask_user":
                    final_report = instruction.get("message", "需要用户输入")
                    full_log.append(f"步骤{step}: 需要用户输入")
                    self.step_completed.emit(step, reasoning, f"需要用户输入: {final_report}")
                    break

                if action == "execute_tool":
                    tool_name = instruction.get("tool", "")
                    params = instruction.get("params", {})

                    self.log_signal.emit(f"执行工具: {tool_name}")
                    result = self.tool_executor.execute(tool_name, params)

                    success = result.get("success", False)
                    stdout = result.get("stdout", "")[:2000]
                    stderr = result.get("stderr", "")[:500]

                    status_icon = "成功" if success else "失败"
                    result_summary = f"工具 {tool_name} {status_icon}\n{stdout[:400]}"
                    if stderr:
                        result_summary += f"\n错误: {stderr[:200]}"

                    full_log.append(f"步骤{step}: {tool_name} - {status_icon}")
                    self.step_completed.emit(step, reasoning, result_summary)

                    feedback = (
                        f"上一步工具执行结果:\n"
                        f"工具: {tool_name}\n"
                        f"状态: {'成功' if success else '失败'}\n"
                        f"输出:\n{stdout}\n\n"
                        f"请根据以上结果继续下一步操作，返回新的JSON指令。"
                        f"如果分析已完成，设置 is_complete 为 true 并输出最终报告。"
                    )
                    messages.append(AIMessage("assistant", content))
                    messages.append(AIMessage("user", feedback))
                    messages = self.scheduler.provider.truncate_history(messages)

                elif action in ("write", "delete", "create"):
                    session = type('Session', (), {
                        'file_path': self.file_path,
                        'tool_outputs': [],
                        'step_count': step
                    })()
                    result = self.scheduler._execute_instruction(instruction, session)
                    status = result.get("status", "unknown")
                    output = result.get("output", "")

                    full_log.append(f"步骤{step}: 文件操作 {action} - {status}")
                    self.step_completed.emit(step, reasoning, f"文件操作({action}): {output[:400]}")

                    feedback = (
                        f"文件操作完成: {output}\n\n"
                        f"请继续下一步，或设置 is_complete 为 true 结束。"
                    )
                    messages.append(AIMessage("assistant", content))
                    messages.append(AIMessage("user", feedback))
                    messages = self.scheduler.provider.truncate_history(messages)

                elif action == "analyze":
                    full_log.append(f"步骤{step}: 分析")
                    self.step_completed.emit(step, reasoning, "分析中...")

                    feedback = "请继续执行具体工具来完成分析。"
                    messages.append(AIMessage("assistant", content))
                    messages.append(AIMessage("user", feedback))
                    messages = self.scheduler.provider.truncate_history(messages)

                else:
                    full_log.append(f"步骤{step}: 未知动作 {action}")
                    self.step_completed.emit(step, reasoning, f"未知动作: {action}")
                    final_report = f"遇到未知动作: {action}"
                    break
            else:
                full_log.append("达到最大步数限制")
                self.step_completed.emit(self.max_steps, "", "达到最大步数限制")
                final_report = "分析达到最大步数限制，可能未完成"

            self.all_done.emit(final_report, "\n".join(full_log))

        except Exception as e:
            self.error.emit(str(e))
