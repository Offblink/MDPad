"""帮助与应用说明对话框。"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QGroupBox,
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
- **v1.5.5（当前版，v2-fluent 目录）**：光标动画回退，改回 Qt 原生光标
- **v1.5.4（v2-fluent 目录）**：输入法候选框定位调整（原生光标只在动画期间被接管）
- **v1.5.3（v2-fluent 目录）**：试错版（自建隐形系统光标，非根因）
- **v1.5.2（v2-fluent 目录）**：补了 Qt 的 ImCursorRectangle 查询（只修了一半）
- **v1.5.1（v2-fluent 目录）**：光标动画收敛成单一滑行、修复退格 / 删除时的抖动
- **v1.5.0（v2-fluent 目录）**：打开期间锁定文件、光标平滑移动、若干一致性修复
- **v1.4.0（v2-fluent 目录）**：新增查找与替换
- **v1.2.0（v2-fluent 目录）**：界面改用 Fluent 组件重写，多文件模块化结构
- **v1.1.0（旧版，v1-pyqt 目录）**：PyQt5 单文件版

### 本次更新（v1.5.5）
- **光标动画回退：编辑器改回 Qt 原生光标**。自绘光标（滑行 + 强调色）虽然看着顺滑，但它要长期接管 Qt 的光标绘制，接连引出输入法候选框定位问题（`ImCursorRectangle` 变成宽度 0、Windows 层 `hwndCaret = None`，候选框贴到窗口左上角/上一行）。既然定位正确比动画重要，这次直接整块回退：
  - 删掉 `mdpad/editor.py`，主窗口改回原生 `QTextEdit`；光标、闪烁、输入法交互全部回到 Qt 默认行为
  - 其余修复（打开期间锁定文件、F1 幂等、视图模式与滑块一致、保存确认框不叠加、API key 移出代码）都保留，不受影响

### v1.5.4 更新内容
- **修复中文输入法候选框定位（真正的修法：不再长期关掉原生光标）**：自绘光标只要 `setCursorWidth(0)`，就会连带把 Qt 那一整套原生信息弄坏——实测 `ImCursorRectangle` 变成**宽度 0** 的矩形，Windows 层 `hwndCaret = None`。输入法（以及"文本光标指示器"这类辅助功能）正是靠这些定位候选框：拿到空值就贴窗口左上角，光标在行首这类边界还会偏到上一行
  - 现在**平时保留 Qt 的原生光标**（静止、组词、打字全部走原生路径），只有滑行动画的那 ~100ms 临时关掉它、改由自绘光标画（避免同一位置出现两个光标），动画一结束立刻交还；实测宽度变化：静止 1 → 动画中 0 → 动画结束 1，组词期间始终 1
  - 输入法组词期间本来就不做动画，所以候选框定位全程是原生行为
- 回退试错：v1.5.2 补的 `ImCursorRectangle` 宽度、v1.5.3 自建的"隐形系统光标"都不是根因（实测**原生 QTextEdit 也没有 Win32 系统光标**），已删除，避免和 Qt 抢同一份状态

### v1.5.3 更新内容
- **修复中文输入法候选框定位（根治）**：`setCursorWidth(0)` 关掉原生光标后，**Windows 层面根本没有光标**——实测 `hwndCaret = None`、`rcCaret = (0,0,0,0)`。输入法（以及"文本光标指示器"等辅助功能）是问系统要这个位置来放候选框的，拿到空值就贴到窗口左上角，光标在行首这类边界还会偏到上一行；只补 Qt 的查询（v1.5.2 做的）不够，因为不是所有输入法都走那条路
  - 现在自己维护一个"**有尺寸、但位图全 0 = 不可见**"的系统光标：Windows 用位图 XOR 出光标，全 0 位图等于不改屏幕，所以不会多出光标，而 `rcCaret` 是准的
  - 每次重绘把它摆到真实光标位置，失焦时销毁；实测行首/行中：`rcCaret` 分别落在各自那一行（行首 `(4,33,6,59)`、行中 `(70,33,72,59)`）

### v1.5.2 更新内容
- **修复中文输入法候选框位置（上半）**：重写 `inputMethodQuery`，把 `ImCursorRectangle` 从"宽度 0"补成正常宽度（实测 `QRectF(x, y, 0, h)` → `QRectF(x, y, 2, h)`）

### v1.5.1 更新内容
- **光标动画回到"就一个滑行"**：删掉 v1.5.0 的尾迹与落点脉冲，只保留滑行 + 运动期间的 Fluent 强调色（打字、退格、方向键、点击、查找跳转全都一样）；落点在视口外时先把滚动条平滑滚过去
- **修复退格 / 删除时的抖动**（三处根因）
  - **起点算错**：v1.5.0 拿"上一次的光标位置"在新文本里重算起点，而退格是"先删字、再移动光标"，那个旧位置往往已经落到别处（删掉换行就变成另一行，删到文档末尾甚至算到布局之外——实测得到 y=-1227 的矩形，光标从 1900px 外飞进来）。现在起点固定取"改文档之前屏幕上真正画着的那个矩形"
  - **终点算早**：在光标信号里立刻 `cursorRect()` 拿到的是"字删了但还没重排"的旧坐标，会让光标到位后又回弹 5~8px。现在推迟一轮事件循环再算
  - **连打时滑行会"追"**：打字 / 退格连打（间隔 < 90ms）时文字在快速重排，直接落位；单发按键仍然滑行。实测连打退格 8 次：画面光标与真实位置偏差 ≤9px、无向右回退帧
- 顺带修正：命中滚动时才把滑行时长延长到 220ms（原来判断写反了，滚动时反而没延长）

### v1.5.0 更新内容
- **打开期间锁定当前文件**：正在编辑的文档在 MDPad 打开期间，资源管理器/其他程序无法移动、删除、重命名它（显示「另一个程序正在使用此文件」）；自己的保存不受影响，别人仍可只读打开；另存为会跟着换锁、新建文件或关闭窗口即释放
- **光标平滑移动**：光标在起终点之间滑行（L 形路径：先纵向到位再横向），带 80ms 渐隐尾迹与到位时的轻微脉冲；运动期间用 Fluent 强调色，停下后回到正文色；打字、方向键、鼠标点击、查找跳转都生效；落点在视口外时先把滚动条平滑滚过去；输入法组词过程中不做动画
- **修复 F1 重复打开帮助框**：帮助窗口打开期间主窗口快捷键被禁用，连按 F1 只会有一个帮助窗口
- **修复保存确认框叠加**（同一根因）：确认框打开期间 Ctrl+O / Ctrl+N / Ctrl+S 不再叠出多个确认框
- **修复「视图状态与右上角滑块不一致」**：视图模式（编辑 / 预览 / 分屏）改为显式记忆，启动时界面与滑块一起还原；分栏比例也一起记住（不再每次切回分屏都被强制 50/50）；修掉旧版本把 `[宽, 0]` 当成有效分栏尺寸写进设置、导致下次启动分屏只剩一栏的问题
- **安全：API key 移出代码**：AI 命名用的智谱 key 改从本机文件 `%APPDATA%\\MDPad\\ai_key.txt` 读取（一行一个，`#` 开头为注释），仓库里不再保存任何密钥；没配 key 时不发请求，只在右上角提示该路径

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
- **文件被"占用"是故意的**：编辑中的文档在资源管理器里移动 / 改名 / 删除会提示「另一个程序正在使用此文件」，这是防止误删误移；关掉 MDPad、新建文件或另存到别处即自动解除
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
