"""
主窗口
整合所有面板，提供完整的用户界面
"""
import os
import json
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu, QMessageBox,
    QDialog, QLabel
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction

from .file_panel import FilePanel
from .log_panel import LogPanel
from .code_viewer import CodeViewer
from .ai_chat_panel import AIChatPanel
from .settings_dialog import SettingsDialog
from .chat_worker import PersistentChatWorker
from src.utils.logger import log
from src.core.file_analyzer import analyze_file
from src.ai.scheduler import AIScheduler, ProviderFactory, AnalysisSession
from src.tools.executor import ToolExecutor
from src.tools.registry import ToolRegistry


class AnalysisWorker(QThread):
    """后台分析工作线程"""
    log_signal = Signal(str)
    progress_signal = Signal(str)
    finished_signal = Signal(AnalysisSession)
    error = Signal(str)

    def __init__(self, scheduler: AIScheduler, file_path: str, file_info: dict):
        super().__init__()
        self.scheduler = scheduler
        self.file_path = file_path
        self.file_info = file_info

    def run(self):
        try:
            self.scheduler.register_progress_callback(self._on_progress)
            session = self.scheduler.start_analysis(self.file_path, self.file_info)
            self.finished_signal.emit(session)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, message: str):
        self.log_signal.emit(message)
        self.progress_signal.emit(message)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI-RE Toolkit v0.1.0")
        self.setMinimumSize(1400, 900)

        self.config = self._load_config()
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.scheduler = None
        self._init_scheduler()

        self.worker: AnalysisWorker = None

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._apply_theme()

        log.set_gui_callback(self._on_log)
        log.info("AI-RE Toolkit 已启动")

    def _load_config(self) -> dict:
        try:
            with open("config/app_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        try:
            with open("config/app_config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"保存配置失败: {e}")

    def _init_scheduler(self):
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
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        self.file_panel = FilePanel()
        self.file_panel.file_loaded.connect(self._on_file_loaded)
        self.file_panel.start_analysis.connect(self._start_analysis)

        self.log_panel = LogPanel()
        self.code_viewer = CodeViewer()
        self.ai_chat = AIChatPanel()
        self.ai_chat.worker = None
        self.ai_chat._send_message = lambda: self._send_chat_message()

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
        menubar = self.menuBar()

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

        tools_menu = menubar.addMenu("工具")
        clear_cache = QAction("清除缓存", self)
        clear_cache.triggered.connect(self._clear_cache)
        tools_menu.addAction(clear_cache)

        settings_menu = menubar.addMenu("设置")
        ai_settings = QAction("AI配置", self)
        ai_settings.triggered.connect(self._show_settings)
        settings_menu.addAction(ai_settings)

        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪")
        self.lbl_ai_status = QLabel("AI: 未连接")
        self.statusbar.addPermanentWidget(self.lbl_ai_status)
        if self.scheduler:
            self.lbl_ai_status.setText(f"AI: {self.scheduler.provider.name}")

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background: #1a1a1a; }
            QWidget { background: #1a1a1a; color: #e0e0e0; }
            QMenuBar { background: #252525; color: #e0e0e0; border-bottom: 1px solid #333; }
            QMenuBar::item:selected { background: #3a3a3a; }
            QMenu { background: #2a2a2a; border: 1px solid #444; }
            QMenu::item:selected { background: #3a3a3a; }
            QStatusBar { background: #252525; color: #888; border-top: 1px solid #333; }
            QSplitter::handle { background: #333; }
        """)

    def _on_file_loaded(self, path: str, info: dict):
        log.info(f"加载文件: {path}")
        log.info(f"文件类型: {info.get('type_name')}")

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
        if not self.scheduler:
            QMessageBox.warning(self, "错误", "AI调度器未初始化")
            return

        file_path = self.file_panel.current_file
        file_info = self.file_panel.file_info

        if not file_path or not file_info:
            QMessageBox.warning(self, "错误", "请先选择文件")
            return

        self.file_panel.btn_analyze.setEnabled(False)
        self.log_panel.clear()
        log.info("=" * 50)
        log.info("开始AI自动化分析")
        log.info("=" * 50)

        self.worker = AnalysisWorker(self.scheduler, file_path, file_info)
        self.worker.log_signal.connect(self._on_log, Qt.ConnectionType.QueuedConnection)
        self.worker.progress_signal.connect(self._on_progress_update, Qt.ConnectionType.QueuedConnection)
        self.worker.finished_signal.connect(self._on_analysis_finished, Qt.ConnectionType.QueuedConnection)
        self.worker.error.connect(self._on_analysis_error, Qt.ConnectionType.QueuedConnection)
        self.worker.start()

    def _on_analysis_finished(self, session: AnalysisSession):
        self.file_panel.btn_analyze.setEnabled(True)
        self.file_panel.set_progress(100)

        log.info("=" * 50)
        log.info("分析完成")
        log.info(f"总步骤: {session.step_count}")
        log.info("=" * 50)

        if session.final_report:
            self.code_viewer.set_code(session.final_report)
            log.info("最终报告已生成")

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
        self.file_panel.btn_analyze.setEnabled(True)
        log.error(f"分析错误: {error}")
        QMessageBox.critical(self, "错误", f"分析过程中出错:\n{error}")

    def _on_ai_progress(self, message: str):
        pass

    def _on_progress_update(self, message: str):
        log.info(f"[AI] {message}")
        if self.worker and self.worker.isRunning():
            progress = min(self.file_panel.progress.value() + 5, 95)
            self.file_panel.set_progress(progress)

    def _on_log(self, message: str):
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
        self.tool_executor.clear_cache()
        log.info("工具缓存已清除")
        QMessageBox.information(self, "提示", "缓存已清除")

    def _show_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            cfg = dialog.get_config()
            self.config["ai"] = {
                "default_provider": "custom",
                "max_retries": 3,
                "timeout": 120,
                "providers": {"custom": cfg}
            }
            self._save_config()
            self._init_scheduler()
            QMessageBox.information(self, "提示", "设置已保存，AI配置已更新")

    def _show_about(self):
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
        message = self.ai_chat.input_box.text().strip()
        if not message:
            return

        if self.ai_chat.worker is not None and self.ai_chat.worker.isRunning():
            self.ai_chat._add_message("AI正在处理中，请等待完成后再发送新指令", is_user=False)
            return

        if not self.scheduler:
            self.ai_chat._add_message("AI未配置，请先在设置中配置AI", is_user=False)
            return

        self.ai_chat.input_box.clear()
        self.ai_chat._add_message(message, is_user=True)
        self.ai_chat.messages.append({"role": "user", "content": message})
        self.ai_chat._set_loading(True)
        log.info(f"[Chat] 用户: {message}")

        full_context = self.ai_chat.current_context
        if len(self.ai_chat.messages) > 1:
            full_context += "\n\n对话历史:\n" + self.ai_chat.get_conversation_history()

        file_path = getattr(self.file_panel, 'current_file', '')

        if self.ai_chat.worker is not None:
            try:
                self.ai_chat.worker.stop()
                self.ai_chat.worker.wait(1000)
            except Exception:
                pass

        self.ai_chat.worker = PersistentChatWorker(
            self.scheduler, self.tool_executor, message, full_context, file_path
        )
        self.ai_chat.worker.step_completed.connect(self._on_chat_step)
        self.ai_chat.worker.all_done.connect(self._on_chat_all_done)
        self.ai_chat.worker.log_signal.connect(self._on_log)
        self.ai_chat.worker.error.connect(self._on_chat_error)
        self.ai_chat.worker.start()

    def _on_chat_step(self, step: int, reasoning: str, result: str):
        msg_text = f"步骤 {step}: {reasoning}\n{result}"
        self.ai_chat._add_message(msg_text, is_user=False)
        self.ai_chat.messages.append({"role": "assistant", "content": msg_text})

        if "工具" in result and "\n" in result:
            lines = result.split("\n")
            if len(lines) > 1:
                output = "\n".join(lines[1:])
                if len(output) > 50:
                    self.code_viewer.set_code(output)

        log.info(f"[Chat] 步骤{step}: {reasoning[:60]}")

    def _on_chat_all_done(self, final_report: str, full_log: str):
        self.ai_chat._set_loading(False)

        report_msg = f"最终报告:\n{final_report}"
        self.ai_chat._add_message(report_msg, is_user=False)
        self.ai_chat.messages.append({"role": "assistant", "content": report_msg})
        self.code_viewer.set_code(final_report)

        log.info("[Chat] 任务完成")
        self.ai_chat.worker = None

    def _on_chat_error(self, error: str):
        self.ai_chat._set_loading(False)
        self.ai_chat._add_message(f"错误: {error}", is_user=False)
        log.error(f"[Chat] 错误: {error}")
        self.ai_chat.worker = None
