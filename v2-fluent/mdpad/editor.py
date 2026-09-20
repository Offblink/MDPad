"""编辑器控件：平滑移动光标（滑行 + 尾迹 + 落点脉冲）。

为什么自绘光标：QTextEdit 的原生光标是瞬移的，Qt 没有给插值的钩子。
做法是 `setCursorWidth(0)` 关掉原生光标，在 `paintEvent` 里自己画一个，
用 QTimer 逐帧插值；闪烁、尾迹、脉冲、强调色都由本控件自管。

三个实测坑（改这里之前先读）：
  1. `cursorPositionChanged` 对同一次移动会发多次信号，必须按光标位置去重；
     否则后到的信号会把动画起点重置到终点，动画直接消失（看着像没生效）。
  2. `cursorWidth=0` 时 `cursorRect()` 返回**宽度为 0 的空矩形**，在 Python 里是假值。
     任何 `a or b` 形式的挑选都会静默挑错，必须显式判 None；
     同时意味着光标宽度只能自己定（不随 cursorRect）。
  3. Qt 只重绘脏区域，自绘光标必须自己记账：移动、闪烁、脉冲、滚动、缩放之后
     都要把「上一帧画过的矩形 ∪ 这一帧要画的矩形」交给 `viewport().update()`，
     否则界面上会留下幽灵光标（尤其是滚动和改变窗口大小时）。
"""
from PyQt5.QtCore import QEasingCurve, QElapsedTimer, QRect, QTimer, QVariantAnimation
from PyQt5.QtGui import QColor, QPainter, QTextCursor
from PyQt5.QtWidgets import QTextEdit

ACCENT = (0, 120, 212)      # Fluent 强调色（运动期间的光标色）
CARET_W = 2                 # 自绘光标宽度（原生 1px，这里 2px 更显动画）
MOVE_MIN_MS = 70            # 滑行时长下限（打字逐字符移动用这个量级）
MOVE_MAX_MS = 170           # 滑行时长上限
MOVE_MS_PER_PX = 0.6        # 距离 → 时长
SCROLL_MS = 180             # 落点在视口外时的滚动时长
TRAIL_MS = 80               # 尾迹渐隐时长
TRAIL_ALPHA = 90
PULSE_MS = 60               # 落点脉冲时长
PULSE_ALPHA = 130
PULSE_PAD = 2               # 脉冲晕每侧宽度
SOLID_MS = 500              # 移动后保持实心的时长，之后开始闪
BLINK_MS = 530              # 闪烁周期
ACCENT_MS = 300             # 运动结束后强调色保持时长
PAD = PULSE_PAD + 2         # 局部重绘外扩，避免残留边


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


class MarkdownEditor(QTextEdit):
    """QTextEdit + 平滑移动光标；其余行为与原控件一致。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursorWidth(0)                   # 关掉原生光标（它只会瞬移）

        self._last_pos = None                    # 去重：上次处理过的光标位置
        self._visual = None                      # 静止时屏幕上的光标矩形（视口坐标）
        self._from_pos = None                    # 动画起点（字符位置）
        self._to_pos = None                      # 动画终点（字符位置）
        self._pos = None                         # 动画中的插值矩形；None = 没有在滑行
        self._duration = MOVE_MIN_MS
        self._nav = False                        # 本次移动是否导航类（决定要不要落点脉冲）
        self._trail = []                         # [(矩形, 记录时刻)]，用于尾迹渐隐
        self._pulse_until = 0
        self._accent_until = 0
        self._solid_until = 0
        self._caret_on = True
        self._composing = False                  # 输入法组词中：不做动画
        self._painted = QRect()                  # 上一帧占用区域（用于擦除）
        self._scroll_ani = None

        self._clock = QElapsedTimer()
        self._clock.start()

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(12)         # ≈80 FPS
        self._anim_timer.timeout.connect(self._tick)

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(BLINK_MS)
        self._blink_timer.timeout.connect(self._blink)

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
        """静止时应画的光标矩形。"""
        if not self.hasFocus():
            return None
        return self._visual if self._visual is not None else self._rect_for(self.textCursor().position())

    def _region(self):
        """这一帧占用的区域（尾迹 + 脉冲晕 + 光标），带外扩。"""
        region = QRect()
        now = self._now()
        if self._visual is not None:
            region = region.united(self._visual)
        if self._pos is not None:
            region = region.united(self._pos)
        for rect, stamp in self._trail:
            if now - stamp < TRAIL_MS:
                region = region.united(rect)
        if region.isNull():
            return region
        return region.adjusted(-PAD, -PAD, PAD, PAD)

    def _schedule_paint(self):
        """把「上一帧区域 ∪ 这一帧区域」交给 Qt 重绘（Qt 只重绘脏区域）。"""
        new = self._region()
        dirty = self._painted.united(new)
        self._painted = new
        if not dirty.isNull():
            self.viewport().update(dirty)

    def _resync(self):
        """滚动/缩放后重新对齐静止光标，并擦掉它原来的位置。"""
        if self._pos is not None:                # 滑行中：每帧都按当前位置重算，不用管
            return
        new = self._rect_for(self.textCursor().position())
        if self._visual is not None and new == self._visual:
            return
        old, self._visual = self._visual, new
        if not self._caret_on and new is not None:
            self._caret_on = True
        self._painted = self._painted.united(old) if old is not None else self._painted
        self._schedule_paint()

    # ---------- 移动 / 动画 ----------

    def _on_cursor_moved(self):
        cursor = self.textCursor()
        position = cursor.position()
        if position == self._last_pos:           # 同一次移动的重复信号，忽略
            return
        previous = self._last_pos
        self._last_pos = position

        target = self._rect_for(position)
        self._solid_until = self._now() + SOLID_MS
        self._accent_until = self._now() + ACCENT_MS
        self._caret_on = True
        self._blink_timer.start()                # 重新计时闪烁周期

        start = self._pos if self._pos is not None else self._visual
        if self._composing or previous is None or start is None:
            # 组词中 / 首次定位 / 无起点：直接落位，不做滑行
            self._stop_animation()
            self._visual = target
            self._schedule_paint()
            return
        if (start.left(), start.top()) == (target.left(), target.top()):
            self._visual = target
            self._schedule_paint()
            return

        self._nav = start.top() != target.top() or abs(position - previous) > 1
        self._from_pos, self._to_pos = previous, position
        distance = abs(target.left() - start.left()) + abs(target.top() - start.top())
        self._duration = int(min(MOVE_MAX_MS, MOVE_MIN_MS + distance * MOVE_MS_PER_PX))
        if not self._scroll_into_view(target):
            self._duration = max(self._duration, SCROLL_MS + 40)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._trail.clear()
        self._pulse_until = 0
        self._anim_timer.start()

    def _scroll_into_view(self, target):
        """落点不在视口内时平滑滚动过去；已在视口内返回 True。"""
        viewport = self.viewport().rect()
        if viewport.contains(target):
            return True
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
        self._from_pos = self._to_pos = None
        self._trail.clear()
        self._pulse_until = 0

    def _tick(self):
        now = self._now()
        animating = self._from_pos is not None
        if animating:
            total = min(1.0, self._elapsed.elapsed() / self._duration)
            self._pos = self._interpolate(total)
            if total >= 1.0:
                self._visual = self._pos
                self._pos = None
                self._from_pos = self._to_pos = None
                if self._nav:
                    self._pulse_until = now + PULSE_MS
            else:
                self._trail.append((self._pos, now))
                self._caret_on = True
        self._trail = [(rect, stamp) for rect, stamp in self._trail if now - stamp < TRAIL_MS]
        if not animating and not self._trail and now >= self._pulse_until:
            self._anim_timer.stop()              # 滑行、尾迹、脉冲都结束了
        self._schedule_paint()

    def _interpolate(self, total):
        """L 形路径：先沿起点列纵向移动，再沿终点行横向移动。

        两段的时间按各自距离分摊（并各留 30% 上限/下限），否则同行移动会有一大段
        "原地不动"的死时间——实测第一版固定 60/40 时，同行动画前 60% 位移为 0。
        """
        start = self._rect_for(self._from_pos)
        end = self._rect_for(self._to_pos)
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

    # ---------- 闪烁 / 焦点 ----------

    def _blink(self):
        if self._now() < self._solid_until:
            self._caret_on = True
            return
        self._caret_on = not self._caret_on
        self._schedule_paint()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._caret_on = True
        self._solid_until = self._now() + SOLID_MS
        self._blink_timer.start()
        self._resync()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._blink_timer.stop()
        self._resync()                           # 失焦后要擦掉自绘光标

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resync()

    def inputMethodEvent(self, event):
        self._composing = bool(event.preeditString())
        super().inputMethodEvent(event)
        self._composing = bool(event.preeditString())

    # ---------- 绘制 ----------

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.hasFocus():
            return
        now = self._now()
        painter = QPainter(self.viewport())

        for rect, stamp in self._trail:          # 尾迹：越旧越淡
            age = now - stamp
            if age >= TRAIL_MS:
                continue
            alpha = int(TRAIL_ALPHA * (1 - age / TRAIL_MS))
            painter.fillRect(rect, QColor(*ACCENT, alpha))

        rect = self._pos if self._pos is not None else self._visual
        if rect is None:
            return
        if self._pos is None and now < self._pulse_until:   # 落点脉冲：到位后极轻的一次加宽
            progress = 1 - (self._pulse_until - now) / PULSE_MS
            alpha = int(PULSE_ALPHA * (1 - progress))
            painter.fillRect(rect.adjusted(-PULSE_PAD, 0, PULSE_PAD, 0), QColor(*ACCENT, alpha))

        if not self._caret_on and self._pos is None:
            return
        if now < self._accent_until:             # 运动期间用强调色，之后回正文色
            painter.fillRect(rect, QColor(*ACCENT))
        else:
            painter.fillRect(rect, self.palette().color(self.foregroundRole()))
