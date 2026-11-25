"""应用入口辅助：创建 QApplication、命令行参数处理。"""
import os
import sys

from PyQt5.QtCore import QLocale, QTimer
from PyQt5.QtWidgets import QApplication

from . import __app_name__, __org_name__, __org_domain__, recovery, singleton


def _install_fluent_translator(app):
    """装 qfluentwidgets 自带的中文翻译。

    内置控件（选色面板 ColorDialog、输入框右键菜单等）的文案走 tr()，不装翻译
    就是英文；应用本体是中文，这里统一成 zh_CN。
    """
    from qfluentwidgets import FluentTranslator

    translator = FluentTranslator(QLocale("zh_CN"), app)
    app.installTranslator(translator)
    app._fluent_translator = translator  # 持有引用，防止被回收


def create_app(argv=None):
    """创建 QApplication。

    注意：mdpad.main_window 的导入链会先加载 QtWebEngineWidgets，
    必须在创建 QApplication 之前完成（QtWebEngine 硬性要求）——
    所以 MainWindow 是在 run() 里、建 QApplication 之前才导入的。
    """
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName(__org_name__)
    app.setOrganizationDomain(__org_domain__)
    _install_fluent_translator(app)
    return app


def run(argv=None):
    """启动主窗口；支持命令行参数打开文件（如右键"打开方式"）。

    同一个文件已经在别的窗口里开着时，这次启动只把那个窗口抬到前台，不再开新窗。
    """
    argv = argv if argv is not None else sys.argv
    file_path = argv[1] if len(argv) > 1 and os.path.isfile(argv[1]) else None
    key = recovery.file_key(file_path)
    if singleton.notify_existing(key):
        return 0

    # QtWebEngineWidgets 必须早于 QApplication（导入 main_window 即完成这件事）
    from .main_window import MainWindow

    app = create_app(argv)
    server = singleton.InstanceServer(key)
    window = MainWindow()
    server.activated.connect(window.raise_window)
    app.aboutToQuit.connect(server.close)
    window.show()
    if file_path:
        window.open_path(file_path)
    else:
        # 未命名草稿的询问要等窗口显示出来（遮罩模态框在窗口可见前弹出会把自己也藏起来）
        QTimer.singleShot(0, window.offer_untitled_recovery)
    return app.exec_()
