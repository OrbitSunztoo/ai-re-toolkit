"""
代码查看器
支持语法高亮、搜索、行号显示
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QComboBox, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor, QSyntaxHighlighter
from src.utils.i18n import t


class SimpleSyntaxHighlighter(QSyntaxHighlighter):
    """简单语法高亮器（用于C/Java/伪代码）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.keywords = [
            "auto", "break", "case", "char", "const", "continue",
            "default", "do", "double", "else", "enum", "extern",
            "float", "for", "goto", "if", "inline", "int", "long",
            "register", "restrict", "return", "short", "signed",
            "sizeof", "static", "struct", "switch", "typedef",
            "union", "unsigned", "void", "volatile", "while",
            "class", "public", "private", "protected", "virtual",
            "namespace", "using", "new", "delete", "try", "catch",
            "throw", "template", "typename", "nullptr", "true", "false",
            "function", "var", "let", "const", "return", "if", "else",
            "for", "while", "do", "switch", "case", "break", "continue"
        ]
        self.setup_formats()

    def setup_formats(self):
        self.keyword_fmt = QTextCharFormat()
        self.keyword_fmt.setForeground(QColor("#c586c0"))
        self.keyword_fmt.setFontWeight(QFont.Weight.Bold)

        self.string_fmt = QTextCharFormat()
        self.string_fmt.setForeground(QColor("#ce9178"))

        self.comment_fmt = QTextCharFormat()
        self.comment_fmt.setForeground(QColor("#6a9955"))

        self.number_fmt = QTextCharFormat()
        self.number_fmt.setForeground(QColor("#b5cea8"))

        self.function_fmt = QTextCharFormat()
        self.function_fmt.setForeground(QColor("#dcdcaa"))

    def highlightBlock(self, text: str):
        import re

        # 注释
        for match in re.finditer(r'//.*$', text):
            self.setFormat(match.start(), match.end() - match.start(), self.comment_fmt)
        for match in re.finditer(r'/\*.*?\*/', text):
            self.setFormat(match.start(), match.end() - match.start(), self.comment_fmt)

        # 字符串
        for match in re.finditer(r'"(?:[^"\\]|\\.)*"', text):
            self.setFormat(match.start(), match.end() - match.start(), self.string_fmt)
        for match in re.finditer(r"'(?:[^'\\]|\\.)*'", text):
            self.setFormat(match.start(), match.end() - match.start(), self.string_fmt)

        # 关键字
        for kw in self.keywords:
            pattern = r'\b' + re.escape(kw) + r'\b'
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), self.keyword_fmt)

        # 数字
        for match in re.finditer(r'\b(?:0x[0-9a-fA-F]+|\d+\.?\d*)\b', text):
            self.setFormat(match.start(), match.end() - match.start(), self.number_fmt)

        # 函数调用
        for match in re.finditer(r'\b([a-zA-Z_]\w*)\s*\(', text):
            self.setFormat(match.start(1), match.end(1) - match.start(1), self.function_fmt)


class CodeViewer(QWidget):
    """代码查看器组件"""
    search_triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.current_search = ""
        self.search_results = []
        self.current_result = -1

    def update_texts(self):
        """更新所有文本"""
        self.title.setText(t("code_viewer.preview"))
        self.btn_prev.setText(t("code_viewer.prev"))
        self.btn_next.setText(t("code_viewer.next"))
        self.search_input.setPlaceholderText(t("code_viewer.search_hint"))
        self.status.setText(t("code_viewer.ready"))

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 工具栏
        toolbar = QHBoxLayout()

        self.title = QLabel(t("code_viewer.preview"))
        self.title.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        toolbar.addWidget(self.title)

        toolbar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("code_viewer.search_hint"))
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 4px;
                color: #fff;
                padding: 4px 8px;
                min-width: 200px;
            }
        """)
        self.search_input.returnPressed.connect(self._search_next)
        toolbar.addWidget(self.search_input)

        self.btn_prev = QPushButton(t("code_viewer.prev"))
        self.btn_prev.setStyleSheet(self._btn_style("#555"))
        self.btn_prev.clicked.connect(self._search_prev)
        toolbar.addWidget(self.btn_prev)

        self.btn_next = QPushButton(t("code_viewer.next"))
        self.btn_next.setStyleSheet(self._btn_style("#4a9eff"))
        self.btn_next.clicked.connect(self._search_next)
        toolbar.addWidget(self.btn_next)

        self.lbl_results = QLabel("")
        self.lbl_results.setStyleSheet("color: #aaa;")
        toolbar.addWidget(self.lbl_results)

        layout.addLayout(toolbar)

        # 代码显示区
        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(True)
        self.code_edit.setFont(QFont("Consolas", 11))
        self.code_edit.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 8px;
                line-height: 1.4;
            }
        """)

        # 启用语法高亮
        self.highlighter = SimpleSyntaxHighlighter(self.code_edit.document())

        layout.addWidget(self.code_edit)

        # 状态栏
        self.status = QLabel(t("code_viewer.ready"))
        self.status.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.status)

    def _btn_style(self, color: str) -> str:
        hover_color = color + "dd" if len(color) == 7 else "#" + color[1] * 2 + color[2] * 2 + color[3] * 2 + "dd"
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background: {hover_color};
            }}
        """

    def set_code(self, text: str, language: str = "c"):
        """设置显示代码"""
        cv = t("code_viewer")
        self.code_edit.setPlainText(text)
        self.status.setText(f"{len(text)} {cv['chars']} | {text.count(chr(10))} {cv['lines']}")
        self.search_results.clear()
        self.current_result = -1

    def clear(self):
        self.code_edit.clear()
        self.status.setText(t("code_viewer.ready"))

    def append(self, text: str):
        """追加代码"""
        cursor = self.code_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.code_edit.setTextCursor(cursor)

    def _search_next(self):
        text = self.search_input.text()
        if text != self.current_search:
            self.current_search = text
            self._do_search(text)

        if self.search_results:
            self.current_result = (self.current_result + 1) % len(self.search_results)
            self._goto_result()

    def _search_prev(self):
        if self.search_results and self.current_search:
            self.current_result = (self.current_result - 1) % len(self.search_results)
            self._goto_result()

    def _do_search(self, text: str):
        """执行搜索"""
        cv = t("code_viewer")
        self.search_results.clear()
        if not text:
            self.lbl_results.setText("")
            return

        doc = self.code_edit.document()
        cursor = QTextCursor(doc)

        while True:
            cursor = doc.find(text, cursor)
            if cursor.isNull():
                break
            self.search_results.append(cursor)

        self.lbl_results.setText(f"{len(self.search_results)} {cv['matches']}")

    def _goto_result(self):
        """跳转到搜索结果"""
        if 0 <= self.current_result < len(self.search_results):
            cursor = self.search_results[self.current_result]
            self.code_edit.setTextCursor(cursor)
            self.lbl_results.setText(
                f"{self.current_result + 1} / {len(self.search_results)}"
            )

    def scroll_to_top(self):
        self.code_edit.moveCursor(QTextCursor.MoveOperation.Start)

    def scroll_to_bottom(self):
        self.code_edit.moveCursor(QTextCursor.MoveOperation.End)
