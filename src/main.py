"""
AI-RE Toolkit 入口文件
一体化AI反编译工具箱
"""
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.gui.main_window import MainWindow
from src.utils.logger import log


def main():
    """主函数"""
    # 启用高DPI支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AI-RE Toolkit")
    app.setApplicationVersion("0.1.0")
    app.setStyle("Fusion")

    # 创建主窗口
    window = MainWindow()
    window.show()

    log.info("=" * 50)
    log.info("AI-RE Toolkit v0.1.0 已启动")
    log.info("=" * 50)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
