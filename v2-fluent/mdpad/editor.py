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
        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(lambda _: self.update_line_number_area_width())
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
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance('9') * digits

    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

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

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())
        width = self._line_number_area.width() - 6
        height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(0, top, width, height, Qt.AlignRight, str(block_number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1
