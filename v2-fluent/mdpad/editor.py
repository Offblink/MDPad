"""编辑器：QPlainTextEdit + 行号栏（可开关）。

行号按块（视觉行）标：软换行的续行不编号，编号只出现在每个块的第一视觉行，
和左栏文字对齐。关掉行号时栏宽归零，不占地方。
"""
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QPlainTextEdit, QWidget


class LineNumberArea(QWidget):
    """行号栏：绘制与尺寸都委托给编辑器。"""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """Markdown 源码编辑器。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_numbers_visible = True
        self._margin = -1
        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(lambda _: self.update_line_number_area_width())
        # 视觉行号：换行宽度变化/正文增减都会改总行数（行号栏宽度跟着位数走）
        self.document().documentLayout().documentSizeChanged.connect(
            lambda _: self.update_line_number_area_width()
        )
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width()

    # ---------- 行号 ----------

    def line_numbers_visible(self):
        return self._line_numbers_visible

    def set_line_numbers_visible(self, visible):
        """显示/隐藏行号；返回是否发生了变化。"""
        visible = bool(visible)
        if visible == self._line_numbers_visible:
            return False
        self._line_numbers_visible = visible
        self._line_number_area.setVisible(visible)
        self.update_line_number_area_width()
        self.viewport().update()
        return True

    def line_number_area_width(self):
        if not self._line_numbers_visible:
            return 0
        digits = max(2, len(str(self.visual_line_count())))
        return 12 + self.fontMetrics().horizontalAdvance('9') * digits

    def line_height(self):
        """一个视觉行的高（等宽单字体下每行等高）。"""
        return max(1, self.fontMetrics().lineSpacing())

    def visual_line_count(self):
        """整篇视觉行数的估算（软换行的续行也算一行，与 VIMD 的行号口径一致）。

        只用来定行号栏的位数：QPlainTextEdit 不排版整个文档，实测
        `documentLayout().documentSize()` 返回的是"排过的那部分"（长文档给一行的高度）、
        滚动条范围在内容短于视口时也给不出内容高度；而逐块 `blockBoundingRect` 会强制
        排版全文。这里按 "字符数 / 每行容量" 估，O(块数)、不触发布局，宁可略偏大
        （偏大只是栏宽多一位）。
        """
        width = self.viewport().width()
        unit = max(1, self.fontMetrics().horizontalAdvance('W'))
        capacity = max(1, width // unit)
        rows = 0
        block = self.document().firstBlock()
        while block.isValid():
            length = len(block.text())
            rows += max(1, (length + capacity - 1) // capacity)
            block = block.next()
        return max(rows, self.blockCount())

    def visual_line_number(self, block):
        """某个块第一个视觉行的行号（1 起）。"""
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        # 文档第一个视觉行的 y = contentOffset().y()（块 0 的几何从 0 起）
        return max(1, int(round((top - self.contentOffset().y()) / self.line_height())) + 1)

    def update_line_number_area_width(self):
        margin = self.line_number_area_width()
        if margin == self._margin:
            return  # 值没变就别再 setViewportMargins（会引发重排）
        self._margin = margin
        self.setViewportMargins(margin, 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if not self._line_numbers_visible:
            return
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        contents = self.contentsRect()
        self._line_number_area.setGeometry(
            contents.left(), contents.top(),
            self.line_number_area_width(), contents.height(),
        )

    def paint_line_numbers(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), self.palette().window())
        painter.setPen(self.palette().text().color())

        line_height = self.line_height()
        width = self._line_number_area.width() - 6
        block = self.firstVisibleBlock()
        # 坐标必须是整数：drawText 用 float 会抛 TypeError，而绘制事件里的异常会直接
        # abort 进程（实测退出码 9、没有任何 Python 栈）
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible():
                # 视觉行号：块里每个折行都算新行，从块首行号顺次排下来
                first = self.visual_line_number(block)
                rows = max(1, round(height / line_height))
                for row in range(rows):
                    y = top + row * line_height
                    if y + line_height < event.rect().top():
                        continue
                    painter.drawText(0, y, width, line_height, Qt.AlignRight, str(first + row))
            block = block.next()
            top += height
