"""编辑器：QPlainTextEdit + 行号栏（可开关）。

行号按"视觉行"标：软换行的续行也算一行（与 VIMD 口径一致），编号从文档第一行
顺次排下来、不跳号也不重头开始。关掉行号时栏宽归零，不占地方。

编号只能"数出来"，不能用几何反推（`块顶 y ÷ 行高`）——实测两种错法：
- 行高不齐：带 emoji 的块高 33px，而 `fontMetrics().lineSpacing()` 是 26px，每过一行
  就多算约半行，编号越往下越偏（第 6 行显示 7、第 22 行显示 25，中间还跳号）；
- 懒排版：`QPlainTextDocumentLayout` 只排到视口附近，一旦发生滚动跳转，块几何的原点就
  可能是那个排版窗口而不是文档开头（实测跳到底部后首可见块几何 top 与
  `contentOffset().y()` 都是 0），编号从 1 重排。
几何只用来定 y（它是视口坐标，恒正确）。行数"数出来"：块已排版的用它自己的折行数，
没排版的（视口外）按文本宽度估；整篇前缀按 (revision, 可用宽度, 字体) 缓存，视口里
发现前缀是旧估算算的（块刚排版出来、行数对不上）就重算一次并整栏重画。
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
        self._rows_cache = None
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
        """整篇的视觉行数（软换行的续行也算一行），只用来定行号栏的位数。"""
        return self.visual_row_prefix()[-1]

    def visual_row_prefix(self, force=False):
        """每块之前的视觉行数：prefix[i] = 第 i 块之前排了几个视觉行。

        len(prefix) == blockCount + 1，prefix[-1] 即全篇行数。行数优先取控件自己
        排版的结果（`block.layout().lineCount()`，O(1) 且与显示严格一致）；没排过的
        块按文本宽度估（不触发布局）。按 (文档 revision, 可用宽度, 字体) 缓存：
        正文、换行宽度、字号任一变化才重算，force=True 时无视缓存。
        """
        key = (self.document().revision(), self.viewport().width(), self.font().key())
        cache = self._rows_cache
        if cache is not None and not force and cache[0] == key:
            return cache[1]
        metrics = self.fontMetrics()
        width = max(1, self.viewport().width())
        # 单字形宽度上限：整行字符数 × 它都不超过可用宽度，就一定不折行
        widest = max(metrics.maxWidth(), metrics.horizontalAdvance('W'),
                     metrics.horizontalAdvance('国'), metrics.horizontalAdvance('✅️'))
        prefix = [0]
        total = 0
        block = self.document().firstBlock()
        while block.isValid():
            layout = block.layout()
            rows = layout.lineCount() if layout is not None else 0
            if rows <= 0:  # 未排版：退回宽度估算
                text = block.text()
                length = len(text)
                if length == 0:
                    rows = 1
                elif length * widest <= width:
                    rows = 1
                else:
                    advance = metrics.horizontalAdvance(text)
                    rows = max(1, (advance + width - 1) // width)
            total += rows
            prefix.append(total)
            block = block.next()
        self._rows_cache = (key, prefix)
        return prefix

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
        if self._paint_numbers(event, self.visual_row_prefix()):
            # 视口里有块的行数跟前缀对不上：前缀是按"那时还没排版的块"估的。
            # 重算前缀并整栏重画（下一次绘制就用准确行数）。
            self.visual_row_prefix(force=True)
            self._line_number_area.update()

    def _paint_numbers(self, event, prefix):
        """按 prefix 画编号；返回是否发现视口里的块跟前缀对不上（前缀是旧的估算）。"""
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), self.palette().window())
        painter.setPen(self.palette().text().color())

        line_height = self.line_height()
        width = self._line_number_area.width() - 6
        stale = False
        block = self.firstVisibleBlock()
        # 坐标必须是整数：drawText 用 float 会抛 TypeError，而绘制事件里的异常会直接
        # abort 进程（实测退出码 9、没有任何 Python 栈）
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        event_top = event.rect().top()
        event_bottom = event.rect().bottom()
        while block.isValid() and top <= event_bottom:
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible():
                # 本块首个视觉行的编号 = 前面所有块的行数之和 + 1；
                # 块里每个折行顺次 +1（编号是数出来的，跟 y 无关）
                index = block.blockNumber()
                rows = max(1, prefix[index + 1] - prefix[index])
                layout = block.layout()
                if layout is not None and layout.lineCount() > 0 and layout.lineCount() != rows:
                    stale = True
                first = prefix[index] + 1
                for row in range(rows):
                    y = top + row * line_height
                    if y + line_height < event_top:
                        continue
                    painter.drawText(0, y, width, line_height, Qt.AlignRight, str(first + row))
            block = block.next()
            top += height
        painter.end()
        return stale
