"""编辑器控件：平滑移动光标——**只有一个动画**：滑行（+ 运动期间的强调色）。

光标策略（别再改回去，两个坑都在这里）：
  - 平时保留 **Qt 的原生光标**（`cursorWidth = 1`）。系统光标、输入法候选框定位、
    辅助功能读的全是它：`setCursorWidth(0)` 之后实测 `hwndCaret = None`、
    `rcCaret = (0,0,0,0)`，输入法拿到空位置就把候选框贴到窗口左上角、光标在行首
    还会偏到上一行；只补 `inputMethodQuery` 不够，因为不是所有输入法都走那条路。
  - 只有滑行动画的那 ~100ms 把宽度设成 0，改由自绘光标画（避免两个光标叠在一起），
    动画一结束立刻交还原生光标。**输入法组词期间不做动画**，所以候选框定位全程
    走原生路径。

动画本身：起终点之间按 OutCubic 插值（同视觉行直接横移，跨行先纵向到位再横向，
时长按距离 70~110ms）；落点在视口外时先把滚动条平滑滚过去；连打（间隔 <90ms）
直接落位（打字/退格时文字在快速重排，滑行会变成"追"着跑）。

四个实测坑（改这里之前先读）：
  1. `cursorPositionChanged` 对同一次移动会发多次信号，必须按光标位置去重；
     否则后到的信号会把动画起点重置到终点，动画直接消失（看着像没生效）。
  2. `cursorWidth=0` 时 `cursorRect()` 返回**宽度为 0 的空矩形**，在 Python 里是假值。
     任何 `a or b` 形式的挑选都会静默挑错，必须显式判 None；光标宽度也只能自己定。
  3. **起点/终点都不能拿"位置"现算——一个只能取屏幕上的，一个要延后算**：
     - 起点：取"改文档之前屏幕上真正画着的那个矩形"。退格 / 删除是"先改文档、
       再移动光标"，拿旧位置在新文本里重算会落到完全不同的地方（换行被删掉就是
       另一行，超出文档长度时甚至算到布局之外：实测文档末尾退格得到 y=-1227 的
       矩形，光标从 1900px 外飞进来）。
     - 终点：推迟一轮事件循环再算。在 `cursorPositionChanged` 里立刻 `cursorRect()`
       拿到的是"字改了但还没重排"的旧坐标，会让光标到位后又回弹几像素（实测 5~8px），
       连打退格时就是"抖"。
  另外 Qt 只重绘脏区域，自绘光标必须自己记账：动画的每一帧都要把
  「上一帧画过的矩形 ∪ 这一帧要画的矩形」交给 `viewport().update()`，
  否则会留下幽灵光标（尤其是滚动和改窗口大小时）。
"""
from PyQt5.QtCore import QEasingCurve, QElapsedTimer, QRect, QRectF, Qt, QTimer, QVariantAnimation
from PyQt5.QtGui import QColor, QPainter, QTextCursor
from PyQt5.QtWidgets import QTextEdit

ACCENT = (0, 120, 212)      # Fluent 强调色（运动期间的光标色）
CARET_W = 2                 # 自绘光标宽度（动画期间用）
MOVE_MIN_MS = 70            # 滑行时长下限
MOVE_MAX_MS = 110           # 滑行时长上限（长距离也是这个量级：一次短促的滑行）
MOVE_MS_PER_PX = 0.25       # 距离 → 时长
BURST_MS = 90               # 距上次移动小于这个间隔就算"连打"：直接落位（不滑）
SCROLL_MS = 180             # 落点在视口外时的滚动时长
PAD = 3                     # 局部重绘外扩，避免残留边


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


class MarkdownEditor(QTextEdit):
    """QTextEdit + 平滑移动光标；其余行为与原控件一致。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursorWidth(1)                   # 平时用原生光标，见模块 docstring

        self._last_pos = None                    # 去重：上次处理过的光标位置
        self._last_len = self.document().characterCount()   # 判断这次移动有没有改文档
        self._text_changed = False
        self._last_move_at = None                # 上次移动的时刻，用来识别"连打"
        self._visual = None                      # 上一帧屏幕上的光标矩形（动画起点）
        self._from_rect = None                   # 本次动画起点（改文档前屏幕上的矩形）
        self._from_scroll = (0, 0)               # 记录起点时的滚动条值，滚动时跟着平移
        self._to_pos = None                      # 本次动画终点（字符位置，逐帧现算矩形）
        self._pos = None                         # 动画中的插值矩形；None = 没有在滑行
        self._duration = MOVE_MIN_MS
        self._composing = False                  # 输入法组词中：不做动画
        self._painted = QRect()                  # 上一帧占用区域（用于擦除）
        self._scroll_ani = None

        self._clock = QElapsedTimer()
        self._clock.start()

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(12)         # ≈80 FPS
        self._anim_timer.timeout.connect(self._tick)

        # 移动信号里不立刻算终点矩形（那时布局还没重排完），推迟一轮事件循环
        self._pending = None
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.setInterval(0)
        self._pending_timer.timeout.connect(self._apply_pending_move)

        self.cursorPositionChanged.connect(self._on_cursor_moved)
        self.verticalScrollBar().valueChanged.connect(self._resync)
        self.horizontalScrollBar().valueChanged.connect(self._resync)

    # ---------- 几何 ----------

    def _now(self):
        return self._clock.elapsed()

    def _rect_for(self, position):
        """某个字符位置在视口里的光标矩形（宽度恒为 CARET_W）。"""
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        rect = self.cursorRect(cursor)
        return QRect(rect.left(), rect.top(), CARET_W, rect.height())

    def _idle_rect(self):
        """静止时光标的位置（现算，供动画取起点用；绘制交给 Qt 的原生光标）。"""
        if not self.hasFocus():
            return None
        return self._rect_for(self.textCursor().position())

    def _region(self):
        """动画这一帧要画的区域（自绘光标），带外扩。"""
        if self._pos is None:
            return QRect()
        return self._pos.adjusted(-PAD, -PAD, PAD, PAD)

    def _schedule_paint(self):
        """把「上一帧区域 ∪ 这一帧区域」交给 Qt 重绘（Qt 只重绘脏区域）。"""
        new = self._region()
        dirty = self._painted.united(new)
        self._painted = new
        if not dirty.isNull():
            self.viewport().update(dirty)

    def _resync(self):
        """滚动 / 缩放 / 文档重排之后重新对齐（动画中每帧现算，静止时交给原生光标）。"""
        if self._pos is not None:
            return
        self._schedule_paint()

    # ---------- 移动 / 动画 ----------

    def _on_cursor_moved(self):
        cursor = self.textCursor()
        position = cursor.position()
        if position == self._last_pos:           # 同一次移动的重复信号，忽略
            return
        previous = self._last_pos
        self._last_pos = position

        length = self.document().characterCount()
        self._text_changed = length != self._last_len
        self._last_len = length

        # 起点取"改文档前屏幕上画着的矩形"（见 docstring 第 3 条）；终点延后算
        start = self._pos if self._pos is not None else self._visual
        self._pending = (start, previous, position)
        if not self._pending_timer.isActive():
            self._pending_timer.start()

    def _apply_pending_move(self):
        """一轮事件循环之后处理这次移动：此时布局已经稳定，矩形是准的。"""
        pending, self._pending = self._pending, None
        if pending is None:
            return
        start, previous, position = pending
        if position != self.textCursor().position():
            return                               # 期间又动过：等它的信号自己处理

        target = self._rect_for(position)
        if start is None and not self._text_changed and previous is not None:
            # 还没画过光标：用旧位置现算起点。只有"文本没变"的移动才能这么算——
            # 编辑类必须先改文档再移动光标，旧位置在新文本里可能完全不是那个地方
            start = self._rect_for(previous)
        # 连打（打字 / 按住退格）时文字在快速重排，任何滑行都会变成"追"着跑，
        # 直接落位才干净；单发按键仍然滑行，所以观感上还是一套动画
        burst = self._last_move_at is not None and (self._now() - self._last_move_at) < BURST_MS
        self._last_move_at = self._now()
        if burst or start is None or self._composing:
            self._finish_move(target)            # 连打 / 组词中 / 首次定位：直接落位
            return
        if (start.left(), start.top()) == (target.left(), target.top()):
            self._finish_move(target)            # 屏幕上没变（例如仅重排）：不滑行
            return

        distance = abs(target.left() - start.left()) + abs(target.top() - start.top())
        duration = int(min(MOVE_MAX_MS, MOVE_MIN_MS + distance * MOVE_MS_PER_PX))
        self._begin_animation(start, position, target, duration)

    def _finish_move(self, target):
        """不滑行：立刻落位（把自绘动画停掉，光标交还 Qt）。"""
        self._stop_animation()
        self._visual = target
        self._schedule_paint()

    def _begin_animation(self, start, position, target, duration):
        """启动一次滑行：起点是屏幕矩形，终点是字符位置（逐帧现算）。"""
        self.setCursorWidth(0)                   # 动画期间自绘，避免与原生光标重叠
        self._from_rect = QRect(start)
        self._from_scroll = (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
        self._to_pos = position
        self._duration = max(1, duration)
        if self._scroll_into_view(target):
            # 有滚动动画在跑：让滑行晚一点落地，光标跟着滚动一起到位
            self._duration = max(self._duration, SCROLL_MS + 40)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._anim_timer.start()

    def _scroll_into_view(self, target):
        """落点不在视口内时平滑滚动过去。

        返回：True = 已经起了一个滚动动画；False = 已在视口内，或滚不动（到达边界）。
        """
        viewport = self.viewport().rect()
        if viewport.contains(target):
            return False
        bar = self.verticalScrollBar()
        margin = max(target.height(), 8)
        if target.top() < viewport.top():
            delta = target.top() - viewport.top() - margin
        else:
            delta = target.bottom() - viewport.bottom() + margin
        end = max(bar.minimum(), min(bar.maximum(), bar.value() + delta))
        if end == bar.value():
            return False
        self._scroll_ani = QVariantAnimation(self)
        self._scroll_ani.setStartValue(bar.value())
        self._scroll_ani.setEndValue(end)
        self._scroll_ani.setDuration(SCROLL_MS)
        self._scroll_ani.setEasingCurve(QEasingCurve.OutCubic)
        self._scroll_ani.valueChanged.connect(lambda value: bar.setValue(int(value)))
        self._scroll_ani.start()
        return True

    def _stop_animation(self):
        self._anim_timer.stop()
        if self._scroll_ani is not None:
            self._scroll_ani.stop()
            self._scroll_ani = None
        self._pos = None
        self._from_rect = None
        self._to_pos = None
        self.setCursorWidth(1)                   # 交还 Qt 的原生光标（输入法靠它定位）

    def _start_rect(self):
        """动画起点：捕获时屏幕上的矩形，按之后的滚动量平移（滚动中仍贴合原内容）。"""
        dx = self.horizontalScrollBar().value() - self._from_scroll[0]
        dy = self.verticalScrollBar().value() - self._from_scroll[1]
        return self._from_rect.translated(-dx, -dy)

    def _target_rect(self):
        """动画终点：按当前光标位置现算（滚动 / 重排后自动跟随）。"""
        return self._rect_for(self._to_pos)

    def _tick(self):
        if self._from_rect is None:
            self._anim_timer.stop()
            return
        total = min(1.0, self._elapsed.elapsed() / self._duration)
        self._pos = self._interpolate(total)
        if total >= 1.0:
            self._visual = self._target_rect()   # 落位后立刻对齐：下一次移动从这里起步
            self._painted = self._painted.united(self._pos)
            self._pos = None
            self._from_rect = None
            self._to_pos = None
            self._anim_timer.stop()
            self.setCursorWidth(1)               # 落位，交还原生光标
        self._schedule_paint()

    def _interpolate(self, total):
        """同视觉行直接横移；跨行走 L 形（先纵向到位再横向），两段按距离分摊时间。

        同一行时不做纵向分段，否则会有"原地不动"的死时间（实测固定 60/40 时，
        同行动画前 60% 位移为 0）。
        """
        start = self._start_rect()
        end = self._target_rect()
        dx = end.left() - start.left()
        dy = end.top() - start.top()
        if dy == 0:
            progress = _ease_out_cubic(total)
            return QRect(int(round(start.left() + dx * progress)), end.top(), CARET_W, end.height())
        if dx == 0:
            progress = _ease_out_cubic(total)
            return QRect(end.left(), int(round(start.top() + dy * progress)), CARET_W, end.height())
        split = max(0.3, min(0.7, abs(dy) / (abs(dx) + abs(dy))))
        if total < split:
            progress = _ease_out_cubic(total / split)
            x, y = start.left(), start.top() + dy * progress
        else:
            progress = _ease_out_cubic((total - split) / (1 - split))
            x, y = start.left() + dx * progress, end.top()
        return QRect(int(round(x)), int(round(y)), CARET_W, end.height())

    # ---------- 输入法 ----------

    def inputMethodEvent(self, event):
        self._composing = bool(event.preeditString())
        super().inputMethodEvent(event)
        self._composing = bool(event.preeditString())

    def inputMethodQuery(self, query):
        """动画期间（`cursorWidth = 0`）也要给输入法一个正常的光标矩形。

        平时由 Qt 原生实现回答；只有动画那一小段会返回宽度 0 的矩形，
        这里补成有宽度的，位置仍是当前光标位置。
        """
        if self.cursorWidth() == 0 and query in (Qt.ImCursorRectangle, Qt.ImMicroFocus):
            rect = self.cursorRect(self.textCursor())
            return QRectF(rect.left(), rect.top(), max(CARET_W, 1), rect.height())
        return super().inputMethodQuery(query)

    # ---------- 绘制 ----------

    def paintEvent(self, event):
        super().paintEvent(event)                # Qt 自己会画原生光标（静止时）
        rect = self._pos if self._pos is not None else self._idle_rect()
        self._visual = rect                      # 记下这一帧光标在哪：下次动画的起点
        if self._pos is None:                    # 静止：原生光标已经画好了，不用我们画
            return
        painter = QPainter(self.viewport())
        painter.fillRect(self._pos, QColor(*ACCENT))          # 运动期间：强调色
