"""查找与替换窗口：非模态浮动工具窗口，查找与替换共用。

- 查找：下一个 / 上一个（循环）、大小写敏感单选框、匹配计数
- 替换：替换当前、全部替换（反向位置替换，免疫替换文本自引用）
- 直接操作 QTextEdit 文档（QTextDocument.find），不依赖正则
- 视觉与帮助/保存确认对话框一致：复用 MessageBoxBase 的卡片样式
  （FluentStyleSheet.DIALOG + #centerWidget + 投影），仅去掉模态遮罩
"""
from PyQt5.QtCore import Qt, QEvent, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QDialog, QFrame, QWidget, QVBoxLayout, QHBoxLayout,
    QShortcut, QGraphicsDropShadowEffect,
)
from qfluentwidgets import (
    LineEdit, PushButton, ToolButton, RadioButton, BodyLabel, SubtitleLabel,
    FluentStyleSheet,
)

from .dialogs import _font_scale, _dialog_size

__all__ = ["FindReplaceDialog"]


def _find_flags(case_sensitive, backward=False):
    """构造 QTextDocument.FindFlags 值。"""
    from PyQt5.QtGui import QTextDocument
    flags = QTextDocument.FindCaseSensitively if case_sensitive else QTextDocument.FindFlags()
    if backward:
        flags |= QTextDocument.FindBackward
    return flags


def count_matches(document, query, case_sensitive):
    """统计全文档中查找词的不重叠匹配数。"""
    if not query:
        return 0
    flags = _find_flags(case_sensitive)
    count = 0
    cursor = document.find(query, 0, flags)
    while not cursor.isNull():
        count += 1
        cursor = document.find(query, cursor.selectionEnd(), flags)
    return count


class _FindLineEdit(LineEdit):
    """查找框：回车=下一个，Shift+回车=上一个。"""

    next_requested = pyqtSignal()
    prev_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                self.prev_requested.emit()
            else:
                self.next_requested.emit()
            return
        super().keyPressEvent(event)


class FindReplaceDialog(QDialog):
    """查找与替换窗口（无边框卡片，Qt.Tool 不占任务栏，随主窗口关闭）。

    持有主窗口引用以调用 notify（InfoBar 提示）与访问编辑器。
    卡片样式与帮助/保存确认对话框一致（同 QSS、同投影、同标题字体）。
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        self._main = main_window
        self._editor = main_window.text_edit

        self.setWindowTitle("查找与替换")
        self.setWindowFlag(Qt.Tool, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 跟随主窗口：移动/缩放时始终居中（同 MessageBoxBase 的几何同步思路）
        self._main.installEventFilter(self)

        self._build_ui()
        # 字体随主窗口尺寸缩放：先快照基准字体，之后按目标系数整体重算（防 int 截断漂移）
        self._capture_base_fonts()
        self._apply_font_target(_font_scale(main_window))

        # 状态联动
        self.find_box.textChanged.connect(self._refresh_count)
        self.case_sensitive_radio.toggled.connect(self._refresh_count)
        self._editor.document().contentsChanged.connect(self._refresh_count)

        # 快捷键（窗口内）
        QShortcut(QKeySequence("Ctrl+G"), self, self.find_next)
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, self.find_previous)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.hide)

        self._refresh_count()

    # ---------- UI ----------

    def _build_ui(self):
        # 外框：无边框透明窗口 + 四周余量容纳投影（与 MessageBoxBase 的卡片一致）
        outer = QVBoxLayout(self)
        outer.setContentsMargins(50, 50, 50, 50)

        self.card = QFrame(self, objectName="centerWidget")
        FluentStyleSheet.DIALOG.apply(self.card)
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        # 宽度随主窗口缩放，与帮助对话框同比例（0.6）同保底（620）
        w, _ = _dialog_size(self._main, 0.6, 0.2, 620, 160)
        self.card.setMinimumWidth(w)

        self.titleLabel = SubtitleLabel("查找与替换")
        layout.addWidget(self.titleLabel)

        # 查找行
        find_row = QHBoxLayout()
        find_row.setSpacing(6)
        self.find_label = BodyLabel("查找")
        self.find_box = _FindLineEdit(self.card)
        self.find_box.setPlaceholderText("输入要查找的内容")
        self.find_box.next_requested.connect(self.find_next)
        self.find_box.prev_requested.connect(self.find_previous)
        self.prev_btn = ToolButton(self.card)
        self.prev_btn.setText("上一个")
        self.prev_btn.setToolTip("查找上一个 (Ctrl+Shift+G)")
        self.prev_btn.clicked.connect(self.find_previous)
        self.next_btn = ToolButton(self.card)
        self.next_btn.setText("下一个")
        self.next_btn.setToolTip("查找下一个 (Ctrl+G)")
        self.next_btn.clicked.connect(self.find_next)
        self.count_label = BodyLabel(self.card)
        find_row.addWidget(self.find_label)
        find_row.addWidget(self.find_box, 1)
        find_row.addWidget(self.prev_btn)
        find_row.addWidget(self.next_btn)
        find_row.addWidget(self.count_label)
        layout.addLayout(find_row)

        # 替换行
        replace_row = QHBoxLayout()
        replace_row.setSpacing(6)
        self.replace_label = BodyLabel("替换")
        self.replace_box = LineEdit(self.card)
        self.replace_box.setPlaceholderText("替换为")
        self.replace_btn = PushButton("替换")
        self.replace_btn.setToolTip("替换当前匹配并跳转到下一个")
        self.replace_btn.clicked.connect(self.replace_current)
        self.replace_all_btn = PushButton("全部替换")
        self.replace_all_btn.clicked.connect(self.replace_all)
        replace_row.addWidget(self.replace_label)
        replace_row.addWidget(self.replace_box, 1)
        replace_row.addWidget(self.replace_btn)
        replace_row.addWidget(self.replace_all_btn)
        layout.addLayout(replace_row)

        # 选项行：单个单选框，选中=区分大小写，默认不选中（不敏感）
        option_row = QHBoxLayout()
        self.case_sensitive_radio = RadioButton("区分大小写", self.card)
        option_row.addWidget(self.case_sensitive_radio)
        option_row.addStretch(1)
        layout.addLayout(option_row)

        # 底部按钮行：关闭（与帮助对话框一致）
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.close_btn = PushButton("关闭")
        self.close_btn.clicked.connect(self.hide)
        button_row.addWidget(self.close_btn)
        layout.addLayout(button_row)

    # ---------- 状态 ----------

    def eventFilter(self, obj, event):
        # 主窗口缩放 → 尺寸与字体实时跟随（非模态窗口始终打开，须随主窗变化）
        if obj is self._main and event.type() == QEvent.Resize:
            self._sync_size_and_font()
        # 主窗口移动/缩放 → 保持居中
        if obj is self._main and event.type() in (QEvent.Move, QEvent.Resize) and self.isVisible():
            self._center_over_parent()
        return super().eventFilter(obj, event)

    def _capture_base_fonts(self):
        """快照所有控件的基准字体（未缩放前），供目标系数整体重算。"""
        self._base_fonts = {
            w: QFont(w.font()) for w in [self] + self.findChildren(QWidget)
        }

    def _apply_font_target(self, target):
        """按目标系数从基准字体重算全部字体（幂等，无累积漂移）。"""
        for w, base in self._base_fonts.items():
            f = QFont(base)
            if f.pointSizeF() > 0:
                f.setPointSizeF(f.pointSizeF() * target)
            elif f.pixelSize() > 0:
                f.setPixelSize(max(int(f.pixelSize() * target), 1))
            else:
                continue
            w.setFont(f)
        self._font_scale = target

    def _sync_size_and_font(self):
        """按主窗口当前尺寸重算卡片宽度与字体缩放。"""
        parent = self._main
        w, _ = _dialog_size(parent, 0.6, 0.2, 620, 160)
        self.card.setMinimumWidth(w)
        self._apply_font_target(_font_scale(parent))
        self.adjustSize()  # 双向跟随：缩小主窗时窗口随之收缩

    def _center_over_parent(self):
        parent = self.parentWidget()
        if parent is None:
            return
        # 用 sizeHint 计算，不依赖当前几何（首次 show 时布局已就绪）
        size = self.sizeHint()
        x = parent.x() + (parent.width() - size.width()) // 2
        y = parent.y() + (parent.height() - size.height()) // 2
        self.move(max(x, 0), max(y, 0))

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_size_and_font()  # 覆盖隐藏期间主窗已缩放的情况
        self._center_over_parent()

    def closeEvent(self, event):
        # 关闭 = 隐藏，保留查找词与选项
        event.ignore()
        self.hide()

    def _query(self):
        return self.find_box.text()

    def _case_sensitive(self):
        return self.case_sensitive_radio.isChecked()

    def show_find(self):
        """打开窗口：有选中文本则预填查找框并全选。"""
        cursor = self._editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText():
            self.find_box.setText(cursor.selectedText())
            self.find_box.selectAll()
        self.show()
        self.raise_()
        self.activateWindow()
        self.find_box.setFocus()
        self.find_box.selectAll()

    # ---------- 计数 ----------

    def _refresh_count(self):
        query = self._query()
        self.replace_btn.setEnabled(bool(query))
        self.replace_all_btn.setEnabled(bool(query))
        if not query:
            self.count_label.setText("输入查找内容")
            return
        count = count_matches(self._editor.document(), query, self._case_sensitive())
        self.count_label.setText(f"共 {count} 处" if count else "无匹配")

    # ---------- 查找 ----------

    def find_next(self):
        """查找下一个（从当前光标向后，到末尾循环）。"""
        self._find(backward=False)

    def find_previous(self):
        """查找上一个（从当前光标向前，到开头循环）。"""
        self._find(backward=True)

    def _find(self, backward):
        query = self._query()
        if not query:
            self.show_find()
            return
        document = self._editor.document()
        find_flags = _find_flags(self._case_sensitive(), backward)

        start = self._search_start(backward)
        found = document.find(query, start, find_flags)
        wrapped = found.isNull()
        if wrapped:
            # 循环：从头 / 从尾再搜一次
            if backward:
                found = document.find(query, document.characterCount(), find_flags)
            else:
                found = document.find(query, 0, find_flags)
        if found.isNull():
            return
        self._editor.setTextCursor(found)
        self._editor.ensureCursorVisible()
        if wrapped:
            self._main.notify(
                "info", "查找",
                "已到文件末尾，循环到开头" if not backward else "已到文件开头，循环到末尾",
                duration=2000,
            )

    def _search_start(self, backward):
        """搜索起点：当前选中即查找词时跳过它，避免原地打转。"""
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            return cursor.position()
        selected = cursor.selectedText()
        query = self._query()
        same = selected == query if self._case_sensitive() else selected.lower() == query.lower()
        if same:
            return cursor.selectionStart() if backward else cursor.selectionEnd()
        return cursor.selectionStart() if backward else cursor.position()

    # ---------- 替换 ----------

    def replace_current(self):
        """替换当前选中的匹配，然后自动查找下一个。"""
        if not self._query():
            return
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            selected = cursor.selectedText()
            query = self._query()
            same = selected == query if self._case_sensitive() else selected.lower() == query.lower()
            if same:
                cursor.insertText(self.replace_box.text())
        self.find_next()

    def replace_all(self):
        """从文档开头替换全部匹配（反向位置替换，免疫自引用），报告数量。"""
        query = self._query()
        if not query:
            return
        document = self._editor.document()
        find_flags = _find_flags(self._case_sensitive())
        replacement = self.replace_box.text()

        spans = []
        cursor = document.find(query, 0, find_flags)
        while not cursor.isNull():
            spans.append((cursor.selectionStart(), cursor.selectionEnd()))
            cursor = document.find(query, cursor.selectionEnd(), find_flags)
        if not spans:
            self._main.notify("info", "替换", "未找到匹配项", duration=2000)
            return
        for start, end in reversed(spans):
            c = QTextCursor(document)
            c.setPosition(start)
            c.setPosition(end, QTextCursor.KeepAnchor)
            c.insertText(replacement)
        self._editor.setTextCursor(QTextCursor(document))
        self._main.notify("success", "替换", f"已替换 {len(spans)} 处", duration=2500)
