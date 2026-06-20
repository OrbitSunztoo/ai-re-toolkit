"""
日志显示面板
实时显示分析日志和AI输出
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QLineEdit
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat


class LogPanel(QWidget):
    """日志面板"""
    log_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("分析日志")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        header.addWidget(title)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索日志...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 4px;
                color: #fff;
                padding: 4px 8px;
            }
        """)
        self.search_box.textChanged.connect(self._highlight_search)
        header.addWidget(self.search_box)

        self.btn_clear = QPushButton("清空")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background: #555;
                color: #ccc;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: #666;
            }
        """)
        self.btn_clear.clicked.connect(self.clear)
        header.addWidget(self.btn_clear)
        layout.addLayout(header)

        # 日志显示区
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 4px;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.log_view)

        # 颜色定义
        self.colors = {
            "info": QColor("#d4d4d4"),
            "debug": QColor("#808080"),
            "warning": QColor("#ffcc00"),
            "error": QColor("#f44336"),
            "success": QColor("#4caf50"),
            "ai": QColor("#4a9eff"),
        }

    def append(self, text: str, level: str = "info"):
        """追加日志，支持颜色级别"""
        color = self.colors.get(level, self.colors["info"])

        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(color)

        cursor.insertText(text + "\n", fmt)

        # 自动滚动到底部
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

        # 限制最大行数
        self._trim_lines(5000)

    def _trim_lines(self, max_lines: int):
        """限制最大行数"""
        doc = self.log_view.document()
        if doc.blockCount() > max_lines:
            cursor = QTextCursor(doc.firstBlock())
            cursor.movePosition(QTextCursor.MoveOperation.Down,
                               QTextCursor.MoveMode.KeepAnchor,
                               doc.blockCount() - max_lines)
            cursor.removeSelectedText()

    def _highlight_search(self, text: str):
        """高亮搜索文本"""
        if not text:
            self.log_view.setExtraSelections([])
            return

        # 简单实现：重新设置样式（完整实现需要QTextDocument.find）
        pass

    def clear(self):
        self.log_view.clear()

    def get_text(self) -> str:
        return self.log_view.toPlainText()
