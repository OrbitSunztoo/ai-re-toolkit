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
from PySide6.QtGui import QAction, QActionGroup

from .file_panel import FilePanel
from .log_panel import LogPanel
from .code_viewer import CodeViewer
from .ai_chat_panel import AIChatPanel
from .settings_dialog import SettingsDialog
from .chat_worker import ChatWorker
from src.utils.logger import log
from src.core.file_analyzer import analyze_file
from src.ai.scheduler import AIScheduler, ProviderFactory, AnalysisSession
from src.tools.executor import ToolExecutor
from src.tools.registry import ToolRegistry
from src.utils.i18n import translator, t


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
        self.setWindowTitle(t("app.title"))
        self.setMinimumSize(1400, 900)

        self.config = self._load_config()
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.scheduler = None
        self._init_scheduler()

        self.worker: AnalysisWorker = None

        # 注册语言变更回调
        translator.register_change_callback(self._on_language_changed)

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._apply_theme()

        log.set_gui_callback(self._on_log)
        log.info("AI-RE Toolkit " + t("status.started"))

    def _on_language_changed(self, lang_code: str):
        """语言切换回调"""
        self.setWindowTitle(t("app.title"))
        self._update_ui_texts()

    def _update_ui_texts(self):
        """更新所有UI文本"""
        # 更新菜单
        self._rebuild_menu()

        # 更新状态栏
        self.statusbar.showMessage(t("status.ready"))
        if self.scheduler:
            self.lbl_ai_status.setText(t("status.ai_connected").format(name=self.scheduler.provider.name))
        else:
            self.lbl_ai_status.setText(t("status.ai_not_connected"))

        # 更新子面板
        self.file_panel.update_texts()
        self.log_panel.update_texts()
        self.code_viewer.update_texts()
        self.ai_chat.update_texts()

    def _rebuild_menu(self):
        """重建菜单"""
        self.menuBar().clear()
        self._setup_menu()

    def _load_config(self) -> dict:
        try:
            with open("config/app_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                # 恢复保存的语言设置
                saved_lang = config.get("language")
                if saved_lang and saved_lang in translator.get_available_languages():
                    translator.set_language(saved_lang)
                return config
        except Exception:
            return {}

    def _save_config(self):
        try:
            with open("config/app_config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"{t('messages.config_save_failed')}: {e}")

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
            log.info(f"{t('messages.scheduler_init_success')}: {provider_name}")
        except Exception as e:
            log.error(f"{t('messages.scheduler_init_failed')}: {e}")
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

        file_menu = menubar.addMenu(t("menu.file"))
        open_action = QAction(t("menu.open_file"), self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.file_panel._on_select_file)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction(t("menu.exit"), self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools_menu = menubar.addMenu(t("menu.tools"))
        clear_cache = QAction(t("menu.clear_cache"), self)
        clear_cache.triggered.connect(self._clear_cache)
        tools_menu.addAction(clear_cache)

        settings_menu = menubar.addMenu(t("menu.settings"))
        ai_settings = QAction(t("menu.ai_config"), self)
        ai_settings.triggered.connect(self._show_settings)
        settings_menu.addAction(ai_settings)

        # 语言子菜单
        lang_menu = QMenu(t("menu.language"), self)
        settings_menu.addMenu(lang_menu)

        lang_group = QActionGroup(self)
        for lang_code, lang_name in [
            ("zh_CN", t("language.chinese")),
            ("en_US", t("language.english"))
        ]:
            lang_action = QAction(lang_name, self)
            lang_action.setCheckable(True)
            lang_action.setChecked(translator.current_language == lang_code)
            lang_action.triggered.connect(lambda checked, code=lang_code: self._switch_language(code))
            lang_group.addAction(lang_action)
            lang_menu.addAction(lang_action)

        help_menu = menubar.addMenu(t("menu.help"))
        about_action = QAction(t("menu.about"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _switch_language(self, lang_code: str):
        """切换语言"""
        if translator.set_language(lang_code):
            # 保存语言偏好
            self.config["language"] = lang_code
            self._save_config()

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage(t("status.ready"))
        self.lbl_ai_status = QLabel(t("status.ai_not_connected"))
        self.statusbar.addPermanentWidget(self.lbl_ai_status)
        if self.scheduler:
            self.lbl_ai_status.setText(t("status.ai_connected").format(name=self.scheduler.provider.name))

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
        log.info(f"{t('messages.file_loaded')}: {path}")
        log.info(f"{t('messages.file_type')}: {info.get('type_name')}")

        ctx = t("context")
        is_packed = info.get('is_packed')

        preview = f"""/*
 * {ctx['file']}: {os.path.basename(path)}
 * {ctx['type']}: {info.get('type_name', 'unknown')}
 * {ctx['size']}: {info.get('size', 0)} bytes
 * {ctx['architecture']}: {info.get('arch', 'N/A')}
 * {ctx['packed']}: {ctx['yes'] if is_packed else ctx['no']}
 * {ctx['magic']}: {info.get('magic', 'N/A')[:32]}...
 */
"""
        self.code_viewer.set_code(preview)

        context = f"""{t('messages.analysis_required')}:
- {ctx['path']}: {path}
- {ctx['type']}: {info.get('type_name', 'unknown')}
- {ctx['size']}: {info.get('size', 0)} bytes
- {ctx['architecture']}: {info.get('arch', 'N/A')}
- {ctx['packed']}: {ctx['yes'] if is_packed else ctx['no']}
- {ctx['suggested_tools']}: {', '.join(info.get('suggested_tools', []))}

{ctx['available_tools']}:
- {ctx['windows_tools']}: pefile_analyze, detect_it_easy, upx, ghidra_analyze, strings
- {ctx['android_tools']}: apk_analyze, jadx, apktool, read_file
- {ctx['ios_tools']}: ipa_analyze, strings

{ctx['supported_ops']}: {ctx['op_analyze']}, {ctx['op_decompile']}, {ctx['op_unpack']}, {ctx['op_modify']}, {ctx['op_repack']}
"""
        self.ai_chat.set_context(context)

    def _start_analysis(self):
        if not self.scheduler:
            QMessageBox.warning(self, t("messages.error"), t("messages.ai_not_init"))
            return

        file_path = self.file_panel.current_file
        file_info = self.file_panel.file_info

        if not file_path or not file_info:
            QMessageBox.warning(self, t("messages.error"), t("messages.please_select_file"))
            return

        self.file_panel.btn_analyze.setEnabled(False)
        self.log_panel.clear()
        log.info("=" * 50)
        log.info(t("messages.analysis_start"))
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
        log.info(t("messages.analysis_complete"))
        log.info(f"{t('messages.total_steps')}: {session.step_count}")
        log.info("=" * 50)

        if session.final_report:
            self.code_viewer.set_code(session.final_report)
            log.info(t("messages.report_generated"))

        if session.tool_outputs:
            summary = "\n\n/* " + t("messages.tool_execution_summary") + " */\n"
            for out in session.tool_outputs:
                tool = out.get("tool", "unknown")
                result = out.get("result", {})
                success = result.get("success", False)
                duration = result.get("duration", 0)
                summary += f"// {tool}: {t('messages.tool_success') if success else t('messages.tool_failed')} ({duration:.1f}s)\n"
            self.code_viewer.append(summary)

        QMessageBox.information(self, t("messages.completed"), t("messages.analysis_complete_msg"))

    def _on_analysis_error(self, error: str):
        self.file_panel.btn_analyze.setEnabled(True)
        log.error(f"{t('messages.error')}: {error}")
        QMessageBox.critical(self, t("messages.error"), f"{t('messages.error')}:\n{error}")

    def _on_ai_progress(self, message: str):
        pass

    def _on_progress_update(self, message: str):
        log.info(f"[AI] {message}")
        if self.worker and self.worker.isRunning():
            progress = min(self.file_panel.progress.value() + 5, 95)
            self.file_panel.set_progress(progress)

    def _on_log(self, message: str):
        level = "info"
        err = t("messages.error")
        warn = t("messages.warning")
        done = t("messages.completed")

        if "[错误]" in message or "[ERROR]" in message or err in message or "ERROR" in message:
            level = "error"
        elif "[警告]" in message or "[WARNING]" in message or warn in message or "WARNING" in message:
            level = "warning"
        elif "完成" in message or "complete" in message.lower() or done in message:
            level = "success"
        elif "[AI]" in message:
            level = "ai"

        self.log_panel.append(message, level)
        self.statusbar.showMessage(message[:100])

    def _clear_cache(self):
        self.tool_executor.clear_cache()
        log.info(t("messages.cache_cleared"))
        QMessageBox.information(self, t("messages.info"), t("messages.cache_cleared"))

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
            QMessageBox.information(self, t("messages.info"), t("messages.config_saved"))

    def _show_about(self):
        QMessageBox.about(
            self,
            t("about.title"),
            f"""<h2>AI-RE Toolkit v0.1.0</h2>
            <p>{t("about.subtitle")}</p>
            <p>{t("about.features")}</p>
            <p>{t("about.capabilities")}</p>
            <hr>
            <p><b>{t("about.disclaimer_title")}</b>{t("about.disclaimer")}</p>
            """
        )

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, t("messages.confirm_exit"),
                t("messages.analysis_in_progress"),
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
            self.ai_chat._add_message(t("messages.ai_processing"), is_user=False)
            return

        if not self.scheduler:
            self.ai_chat._add_message(t("messages.ai_not_configured"), is_user=False)
            return

        self.ai_chat.input_box.clear()
        self.ai_chat._add_message(message, is_user=True)
        self.ai_chat.messages.append({"role": "user", "content": message})
        self.ai_chat._set_loading(True)
        log.info("[Chat] User: " + message)

        full_context = self.ai_chat.current_context
        if len(self.ai_chat.messages) > 1:
            full_context += "\n\n" + t("ai_chat.history") + ":\n" + self.ai_chat.get_conversation_history()

        file_path = getattr(self.file_panel, 'current_file', '')

        if self.ai_chat.worker is not None:
            try:
                self.ai_chat.worker.stop()
                self.ai_chat.worker.wait(1000)
            except Exception:
                pass

        self.ai_chat.worker = ChatWorker(
            self.scheduler, self.tool_executor, message, full_context, file_path
        )
        self.ai_chat.worker.response_ready.connect(self._on_chat_response)
        self.ai_chat.worker.tool_executed.connect(self._on_chat_tool_executed)
        self.ai_chat.worker.log_signal.connect(self._on_log)
        self.ai_chat.worker.error.connect(self._on_chat_error)
        self.ai_chat.worker.start()

    def _on_chat_tool_executed(self, reasoning: str, result: str):
        msg_text = f"🔧 {reasoning}\n{result}"
        self.ai_chat._add_message(msg_text, is_user=False)
        self.ai_chat.messages.append({"role": "assistant", "content": msg_text})

        if len(result) > 50:
            self.code_viewer.set_code(result)

        log.info(f"[Chat] {t('messages.tool_execution')}: {reasoning[:60]}")

    def _on_chat_response(self, content: str):
        self.ai_chat._set_loading(False)

        self.ai_chat._add_message(content, is_user=False)
        self.ai_chat.messages.append({"role": "assistant", "content": content})

        if len(content) > 50:
            self.code_viewer.set_code(content)

        log.info("[Chat] " + t("messages.chat_completed"))
        self.ai_chat.worker = None

    def _on_chat_error(self, error: str):
        self.ai_chat._set_loading(False)
        self.ai_chat._add_message(f"{t('messages.error')}: {error}", is_user=False)
        log.error(f"[Chat] {t('messages.error')}: {error}")
        self.ai_chat.worker = None
