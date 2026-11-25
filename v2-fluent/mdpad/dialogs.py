"""帮助与应用说明对话框。"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QGroupBox,
    QScrollArea, QStackedWidget, QTextBrowser,
)
from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, PushButton, SegmentedWidget,
)


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
        ("重新加载（按磁盘内容刷新）", "Ctrl + R"),
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
        ("替换当前", "Ctrl + T"),
        ("全部替换", "Ctrl + Shift + T"),
    ]),
    ("格式操作", [
        ("加粗", "Ctrl + B"),
        ("斜体", "Ctrl + I"),
        ("代码块", "Ctrl + K"),
        ("插入链接", "Ctrl + L"),
        ("插入图片", "Ctrl + Shift + L"),
        ("字体颜色", "工具栏调色板按钮"),
    ]),
    ("视图操作", [
        ("编辑模式", "F2"),
        ("预览模式", "F3"),
        ("分屏模式", "F4"),
        ("显示/隐藏行号", "Alt + L"),
        ("帮助", "F1"),
    ]),
]

USAGE_TEXT = """## MDPad · 应用说明

### 这是什么
MDPad 是一个 Fluent 风格的 Markdown 编辑器：左边写 Markdown，右边实时预览；也可以只看编辑区或只看预览。

### 主要功能
- **实时预览**：编辑内容即时渲染；分屏 / 编辑 / 预览三种模式（F4 / F2 / F3）
- **公式与流程图**：`$...$`、`$$...$$` 排版成数学公式，` ```mermaid ` 围栏画成流程图；导出的 HTML 同样生效
- **查找与替换**：Ctrl+F 打开面板；Ctrl+G / Ctrl+Shift+G 跳转；Ctrl+T 替换当前、Ctrl+Shift+T 全部替换（不打开面板也能用）
- **字体颜色**：选中文字后点工具栏调色板按钮，选红 / 绿 / 蓝 / 黑，或「自定义颜色…」打开选色面板；「移除颜色」恢复纯文本
- **格式与插入**：加粗、斜体、标题、链接、代码块、图片
- **行号与跟随**：Alt+L 开关行号；分屏时预览跟随光标
- **自动恢复**：编辑停顿即写草稿，异常退出后可恢复；打开期间锁定当前文件
- **导出**：导出为单个 HTML 文件（公式与流程图资产内联，离线可看）

### 使用提示
- 颜色是内联 HTML（`<span style="color:#E81123">文字</span>`），预览与导出的 HTML 都会识别；「移除颜色」剥掉标记即恢复纯文本
- 相对路径的图片和链接以当前 Markdown 文件所在目录为基准；新建文档需先保存（Ctrl+S）
- 编辑中的文件被「占用」是故意的：防止外部误移动 / 删除 / 重命名；关闭窗口或另存到别处即解除
- 打开文件支持拖放与命令行参数；编辑框与预览框内的拖放统一交给主窗口处理

### 关于
MDPad · 基于 PyQt5 + PyQt-Fluent-Widgets + Python-Markdown
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
    """应用说明标签页：只介绍应用本身与用法，不追踪版本。"""
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setMarkdown(USAGE_TEXT)
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
