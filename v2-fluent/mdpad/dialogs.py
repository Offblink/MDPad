"""帮助与应用说明对话框。"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox,
    QScrollArea, QStackedWidget, QTextBrowser,
)
from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, PushButton, SegmentedWidget,
)

from . import __version__


def _dialog_size(parent, w_ratio, h_ratio, min_w, min_h):
    """按主窗口当前尺寸比例计算对话框尺寸（带保底最小尺寸）。

    主窗口被用户拉伸后，弹出的对话框随之变大。
    """
    if parent is not None:
        pw, ph = parent.width(), parent.height()
    else:
        pw, ph = 1200, 800
    return max(int(pw * w_ratio), min_w), max(int(ph * h_ratio), min_h)


def _font_scale(parent, base_w=1200, base_h=800):
    """按主窗口尺寸计算对话框字体缩放系数（温和映射）。

    主窗 1200×800 为基准（系数 1.0）；拉大到 1920×1080 → 约 1.14 倍。
    """
    if parent is None:
        return 1.0
    scale = min(parent.width() / base_w, parent.height() / base_h)
    factor = 1 + (scale - 1) * 0.4
    return max(factor, 0.9)


def _apply_font_scale(widget, factor):
    """把对话框内所有控件的字体按系数放大（兼容点字体与像素字体）。"""
    if abs(factor - 1.0) < 0.01:
        return
    for w in [widget] + widget.findChildren(QWidget):
        f = w.font()
        if f.pointSizeF() > 0:
            f.setPointSizeF(f.pointSizeF() * factor)
        elif f.pixelSize() > 0:
            f.setPixelSize(max(int(f.pixelSize() * factor), 1))
        else:
            continue
        w.setFont(f)

# 快捷键分组（已移除换行/空格快捷键）
SHORTCUT_GROUPS = [
    ("文件操作", [
        ("新建文件", "Ctrl + N"),
        ("打开文件", "Ctrl + O"),
        ("保存文件", "Ctrl + S"),
        ("另存为", "Ctrl + Shift + S"),
    ]),
    ("编辑操作", [
        ("撤销", "Ctrl + Z"),
        ("重做", "Ctrl + Y"),
        ("剪切", "Ctrl + X"),
        ("复制", "Ctrl + C"),
        ("粘贴", "Ctrl + V"),
        ("全选", "Ctrl + A"),
        ("查找与替换", "Ctrl + F"),
        ("查找下一个", "Ctrl + G"),
        ("查找上一个", "Ctrl + Shift + G"),
    ]),
    ("格式操作", [
        ("加粗", "Ctrl + B"),
        ("斜体", "Ctrl + I"),
        ("代码块", "Ctrl + K"),
        ("插入链接", "Ctrl + L"),
    ]),
    ("视图操作", [
        ("编辑模式", "F2"),
        ("预览模式", "F3"),
        ("分屏模式", "F4"),
        ("帮助", "F1"),
    ]),
]

RELEASE_NOTES = f"""## MDPad v{__version__} · 应用说明

### 版本历史
- **v1.4.0（当前版，v2-fluent 目录）**：新增查找与替换
- **v1.2.0（v2-fluent 目录）**：界面改用 Fluent 组件重写，多文件模块化结构
- **v1.1.0（旧版，v1-pyqt 目录）**：PyQt5 单文件版

### 本次更新（v1.4.0）
- **新增查找与替换**：Ctrl+F 打开「查找与替换」窗口（查找与替换共用一个窗口，非模态可边编辑边查找）
  - 查找：下一个（回车 / Ctrl+G）、上一个（Shift+回车 / Ctrl+Shift+G）、区分大小写单选框、匹配计数（输入即刷新）
  - 替换：替换当前（自动跳转下一个）、全部替换（免疫替换文本含查找词的死循环）
  - 查找到文档末尾/开头自动循环；关闭窗口不丢失查找词与选项

### v1.2.0 更新内容
- **界面全面改用 Fluent 组件重写**，自动跟随系统明暗主题，多文件模块化结构
- **移除换行与空格快捷键**（Alt+Enter、Ctrl+Space 等）及对应工具栏按钮
- **修复链接跳转**
  - 文件链接 → 用系统默认程序打开
  - 网址链接 → 在默认浏览器打开，不再在预览框内打开
  - 页内锚点（`#标题`）→ 正常跳转
  - `mailto:` 等外部协议 → 调用系统默认程序
- **修复图片嵌入**
  - 相对路径图片/链接以当前 Markdown 文件所在目录为基准解析
  - Windows 盘符路径（`C:\\...`、`C:/...`）与反斜杠相对路径自动修正
  - 支持加载远程图片（http/https）
- **AI 文件名生成改为异步**：请求在后台执行，期间不卡界面；完成后自动弹出保存/导出对话框
- **对话框自适应**：帮助、确认等对话框的尺寸与字体随主窗口大小缩放
- 帮助窗口改为「快捷键 + 应用说明」两个标签页

### 使用提示
- **相对路径的图片和链接依赖当前文件目录**：新建文档需先保存（Ctrl+S）后，预览中的相对路径图片才能正常显示；未保存的新文档没有基准目录，只能显示绝对路径或网址图片
- **AI 命名**：点击"另存为/导出"后右上角转圈，AI 完成自动弹出保存对话框（文件名已带建议）；无网络时自动回退默认文件名，不影响使用
- 打开文件支持拖放；编辑框与预览框内的拖放事件统一交给主窗口处理
- 三模式切换：编辑（F2）/ 预览（F3）/ 分屏（F4）

### 关于
- MDPad v{__version__} · 基于 PyQt5 + PyQt-Fluent-Widgets + Python-Markdown
"""


def _build_shortcuts_page():
    """快捷键标签页：按组分组的表格。"""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    for title, rows in SHORTCUT_GROUPS:
        group = QGroupBox(title)
        form = QFormLayout(group)
        for name, key in rows:
            key_label = QLabel(key)
            key_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            form.addRow(name, key_label)
        layout.addWidget(group)
    layout.addStretch(1)
    scroll.setWidget(container)
    return scroll


def _build_notes_page():
    """应用说明标签页：更新与修复记录。"""
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setMarkdown(RELEASE_NOTES)
    return browser


class HelpDialog(MessageBoxBase):
    """帮助窗口：快捷键 / 应用说明 两个标签页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("帮助")
        self.viewLayout.addWidget(self.titleLabel)

        # 标签切换（Fluent SegmentedWidget + 堆叠页）
        self.tab_seg = SegmentedWidget()
        self.stack = QStackedWidget()
        self.shortcuts_page = _build_shortcuts_page()
        self.notes_page = _build_notes_page()
        self.stack.addWidget(self.shortcuts_page)
        self.stack.addWidget(self.notes_page)
        self.tab_seg.addItem("shortcuts", "快捷键", onClick=lambda: self.stack.setCurrentIndex(0))
        self.tab_seg.addItem("notes", "应用说明", onClick=lambda: self.stack.setCurrentIndex(1))
        self.tab_seg.setCurrentItem("shortcuts")

        self.viewLayout.addWidget(self.tab_seg)
        self.viewLayout.addWidget(self.stack)
        self.stack.setCurrentIndex(0)

        self.cancelBtn = PushButton("关闭")
        self.buttonLayout.addWidget(self.cancelBtn)
        self.cancelBtn.clicked.connect(self.reject)

        # MessageBoxBase 自带 OK/Cancel 默认按钮，隐藏掉，只保留"关闭"
        self.buttonLayout.removeWidget(self.yesButton)
        self.buttonLayout.removeWidget(self.cancelButton)
        self.yesButton.hide()
        self.cancelButton.hide()

        # 放大默认尺寸，容纳表格与说明；尺寸跟随主窗口
        w, h = _dialog_size(parent, 0.6, 0.65, 620, 520)
        self.widget.setMinimumSize(w, h)
        # 字体随主窗口尺寸缩放
        _apply_font_scale(self, _font_scale(parent))
