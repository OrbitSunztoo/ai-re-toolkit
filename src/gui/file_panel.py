"""
文件操作面板
支持文件选择、拖拽、文件信息显示
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QGroupBox, QGridLayout, QTextEdit, QProgressBar
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from src.utils.i18n import t


class DropArea(QTextEdit):
    """支持文件拖拽的区域"""
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setReadOnly(True)
        self._update_placeholder()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QTextEdit {
                border: 2px dashed #666;
                border-radius: 8px;
                background: #2a2a2a;
                color: #aaa;
                font-size: 14px;
            }
            QTextEdit:hover {
                border-color: #4a9eff;
                background: #323232;
            }
        """)

    def _update_placeholder(self):
        self.setPlaceholderText(
            t("file_panel.no_file") + "\n" +
            t("file_panel.select_file") + "\n" +
            "EXE, DLL, ELF, APK, DEX, JS, ZIP, JAR"
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QTextEdit {
                    border: 2px dashed #4a9eff;
                    border-radius: 8px;
                    background: #323232;
                    color: #aaa;
                    font-size: 14px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QTextEdit {
                border: 2px dashed #666;
                border-radius: 8px;
                background: #2a2a2a;
                color: #aaa;
                font-size: 14px;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.isfile(file_path):
                self.file_dropped.emit(file_path)
        self.dragLeaveEvent(event)


class FilePanel(QWidget):
    """文件操作面板"""
    file_loaded = Signal(str, dict)  # path, info
    start_analysis = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self.file_info = None
        self._setup_ui()

    def update_texts(self):
        """更新所有文本（语言切换时调用）"""
        self.drop_area._update_placeholder()
        # 更新按钮文本
        self.btn_select.setText(t("file_panel.select_file"))
        self.btn_analyze.setText(t("file_panel.analyze"))
        # 更新信息组标题
        self.info_group.setTitle(t("file_panel.file_info"))
        # 刷新文件信息显示
        if self.current_file:
            self._analyze_file(self.current_file)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title = QLabel(t("file_panel.title"))
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        layout.addWidget(title)

        # 按钮区域
        btn_layout = QHBoxLayout()

        self.btn_select = QPushButton(t("file_panel.select_file"))
        self.btn_select.setStyleSheet(self._button_style("#4a9eff"))
        self.btn_select.clicked.connect(self._on_select_file)
        btn_layout.addWidget(self.btn_select)

        self.btn_analyze = QPushButton(t("file_panel.analyze"))
        self.btn_analyze.setStyleSheet(self._button_style("#4caf50"))
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self.start_analysis.emit)
        btn_layout.addWidget(self.btn_analyze)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 拖拽区域
        self.drop_area = DropArea()
        self.drop_area.file_dropped.connect(self._on_file_dropped)
        self.drop_area.setMaximumHeight(120)
        layout.addWidget(self.drop_area)

        # 文件信息区域
        self.info_group = QGroupBox(t("file_panel.file_info"))
        self.info_group.setStyleSheet("""
            QGroupBox {
                color: #ccc;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        info_layout = QGridLayout(self.info_group)

        self.lbl_name = QLabel(f"{t('file_panel.type')}: -")
        self.lbl_type = QLabel(f"{t('file_panel.type')}: -")
        self.lbl_size = QLabel(f"{t('file_panel.size')}: -")
        self.lbl_arch = QLabel(f"{t('file_panel.architecture')}: -")
        self.lbl_packed = QLabel(f"{t('file_panel.packed')}: -")
        self.lbl_magic = QLabel(f"{t('file_panel.magic')}: -")

        labels = [self.lbl_name, self.lbl_type, self.lbl_size,
                  self.lbl_arch, self.lbl_packed, self.lbl_magic]
        for i, lbl in enumerate(labels):
            lbl.setStyleSheet("color: #bbb; padding: 2px 0;")
            info_layout.addWidget(lbl, i // 2, i % 2)

        layout.addWidget(self.info_group)

        # 建议工具
        self.lbl_tools = QLabel(t("file_panel.analyze") + ": -")
        self.lbl_tools.setStyleSheet("color: #aaa; padding: 4px;")
        self.lbl_tools.setWordWrap(True)
        layout.addWidget(self.lbl_tools)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                color: #fff;
            }
            QProgressBar::chunk {
                background: #4a9eff;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress)

        layout.addStretch()

    def _button_style(self, color: str) -> str:
        hover_color = color + "dd" if len(color) == 7 else "#" + color[1] * 2 + color[2] * 2 + color[3] * 2 + "dd"
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {hover_color};
            }}
            QPushButton:disabled {{
                background: #555555;
                color: #888888;
            }}
        """

    def _on_select_file(self):
        dlg = t("dialog")
        path, _ = QFileDialog.getOpenFileName(
            self,
            dlg["select_file"],
            "",
            f"{dlg['all_files']} (*);;"
            f"{dlg['exe_files']} (*.exe *.dll *.elf);;"
            f"{dlg['android_files']} (*.apk *.dex);;"
            f"{dlg['java_files']} (*.jar *.class);;"
            f"{dlg['script_files']} (*.js *.py)"
        )
        if path:
            self._on_file_dropped(path)

    def _validate_file_path(self, path: str) -> bool:
        """
        验证文件路径的安全性
        - 检查是否为绝对路径
        - 检查是否为常规文件
        - 防止目录遍历攻击
        """
        try:
            # 转为绝对路径
            abs_path = os.path.abspath(path)

            # 检查是否为常规文件
            if not os.path.isfile(abs_path):
                return False

            # 检查文件大小（防止读取过大文件）
            size = os.path.getsize(abs_path)
            if size > 500 * 1024 * 1024:  # 500MB限制
                msg = t("file_panel.file_too_large").format(size=size // (1024*1024))
                self._show_error(msg)
                return False

            # 禁止的系统敏感路径
            forbidden = ['\\Windows\\System32', '\\Windows\\SysWOW64', '/etc/', '/bin/', '/sbin/']
            for forbid in forbidden:
                if forbid.lower() in abs_path.lower():
                    self._show_error(t("file_panel.forbidden_dir"))
                    return False

            return True
        except Exception:
            return False

    def _show_error(self, msg: str):
        """显示错误消息"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, t("messages.error"), msg)

    def _on_file_dropped(self, path: str):
        # 安全校验
        if not self._validate_file_path(path):
            return
        self.current_file = path
        self.drop_area.setPlainText(f"{t('file_panel.loaded')}: {os.path.basename(path)}")
        self._analyze_file(path)

    def _analyze_file(self, path: str):
        """分析文件并显示信息"""
        from src.core.file_analyzer import analyze_file

        try:
            info = analyze_file(path)
            self.file_info = info
            ctx = t("context")
            is_packed = info.get('is_packed')

            self.lbl_name.setText(f"{ctx['name']}: {os.path.basename(path)}")
            self.lbl_type.setText(f"{ctx['type']}: {info.get('type_name', 'unknown')}")
            self.lbl_size.setText(f"{ctx['size']}: {self._format_size(info.get('size', 0))}")
            self.lbl_arch.setText(f"{ctx['architecture']}: {info.get('arch', 'unknown') or 'N/A'}")
            self.lbl_packed.setText(f"{ctx['packed']}: {ctx['yes'] if is_packed else ctx['no']}")
            self.lbl_magic.setText(f"{ctx['magic']}: {info.get('magic', 'N/A')[:16]}...")

            tools = info.get('suggested_tools', [])
            self.lbl_tools.setText(f"{ctx['suggested_tools']}: {', '.join(tools) if tools else 'N/A'}")

            self.btn_analyze.setEnabled(True)
            self.file_loaded.emit(path, info)
        except Exception as e:
            self.lbl_type.setText(f"{t('messages.error')}: {e}")
            self.btn_analyze.setEnabled(False)

    def _format_size(self, size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def set_progress(self, value: int):
        self.progress.setValue(value)

    def reset(self):
        self.current_file = None
        self.file_info = None
        self.drop_area.setPlainText("")
        self.btn_analyze.setEnabled(False)
        self.progress.setValue(0)
