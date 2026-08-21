"""应用入口辅助：创建 QApplication、命令行参数处理。"""
import os
import sys

from PyQt5.QtWidgets import QApplication

from . import __app_name__, __org_name__, __org_domain__
from .main_window import MainWindow


def create_app(argv=None):
    """创建 QApplication。

    注意：mdpad.main_window 的导入链会先加载 QtWebEngineWidgets，
    必须在创建 QApplication 之前完成（QtWebEngine 硬性要求）。
    """
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName(__org_name__)
    app.setOrganizationDomain(__org_domain__)
    return app


def run(argv=None):
    """启动主窗口；支持命令行参数打开文件（如右键"打开方式"）。"""
    argv = argv if argv is not None else sys.argv
    app = create_app(argv)
    window = MainWindow()
    window.show()
    if len(argv) > 1 and os.path.isfile(argv[1]):
        window.open_path(argv[1])
    return app.exec_()
