"""编辑器控件：平滑移动光标（滑行 + 尾迹 + 落点脉冲）。

为什么自绘光标：QTextEdit 的原生光标是瞬移的，Qt 没有给插值的钩子。
做法是 `setCursorWidth(0)` 关掉原生光标，在 `paintEvent` 里自己画一个，
用 QTimer 逐帧插值；闪烁、尾迹、脉冲、强调色都由本控件自管。

四个实测坑（改这里之前先读）：
  1. `cursorPositionChanged` 对同一次移动会发多次信号，必须按光标位置去重；
     否则后到的信号会把动画起点重置到终点，动画直接消失（看着像没生效）。
  2. `cursorWidth=0` 时 `cursorRect()` 返回**宽度为 0 的空矩形**，在 Python 里是假值。
     任何 `a or b` 形式的挑选都会静默挑错，必须显式判 None；光标宽度也只能自己定。
  3. Qt 只重绘脏区域，自绘光标必须自己记账：移动、闪烁、脉冲、滚动、缩放之后
     都要把「上一帧画过的矩形 ∪ 这一帧要画的矩形」交给 `viewport().update()`，
     否则界面上会留下幽灵光标（尤其是滚动和改窗口大小时）。
  4. **动画起点不能拿"上一次的光标位置"重新算**：退格 / 删除是"先改文档、再移动光标"，
     那个旧位置在新文本里可能落到完全不同的地方（换行被删掉就是另一行），
     甚至超出文档长度、算到布局之外——实测在文档末尾退格会得到 y=-1227 的矩形，
     光标从 1900px 外飞进来。起点只能取"改文档之前屏幕上真正画着的那个矩形"
     （`_visual` → `_from_rect`），终点则每次插值时按当前光标位置现算
     （这样滚动 / 重排之后终点也自动是对的）。
  5. **编辑类移动和导航类移动必须分开处理**：打字 / 退格 / 删除时文字自己在动，
     若还给光标做长距离滑行，就会出现三件事一起抖：光标落后真实位置几十像素、
     删到折行处目标突然跳到上一行行尾（光标朝右扫过去）、每次按键都闪一次强调色
     与脉冲。实测连打退格时画面上的光标会向右回退、相邻帧跳变 56px。
     所以编辑类只做极短促的跟手滑行（≤1 字符），大跳（删换行、删选区、整段重排）
     直接落位，并且不改色、不做脉冲；只有导航类（方向键、点击、查找跳转）
     才用完整的滑行 + L 形路径 + 强调色 + 落点脉冲。
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
EDIT_MS = 40                # 编辑类移动（打字 / 退格）的跟手滑行时长
EDIT_SNAP_DX = 60           # 编辑类移动横向超过这个距离就干脆不滑（约 4 个字符）
BURST_MS = 90               # 距上一次移动不超过这个间隔就算"连打"：编辑类直接落位
PAD = PULSE_PAD + 2         # 局部重绘外扩，避免残留边


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


class MarkdownEditor(QTextEdit):
    """QTextEdit + 平滑移动光标；其余行为与原控件一致。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursorWidth(0)                   # 关掉原生光标（它只会瞬移）

        self._last_pos = None                    # 去重：上次处理过的光标位置
        self._last_len = self.document().characterCount()   # 用来区分"编辑"和"导航"
        self._last_move_at = None                # 上次移动的时刻，用来识别"连打"
        self._visual = None                      # 上一帧真正画在屏幕上的光标矩形
        self._from_rect = None                   # 本次动画起点（改文档前屏幕上的矩形）
        self._from_scroll = (0, 0)               # 记录起点时的滚动条值，用于滚动时跟随
        self._to_pos = None                      # 本次动画终点（字符位置，逐帧现算矩形）
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

        # 移动信号里不立刻算目标矩形（那时布局还没重排完），推迟一轮事件循环
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
        """静止时光标该画的位置：每次现算，文档重排 / 滚动后也永远是对的。"""
        if not self.hasFocus():
            return None
        return self._rect_for(self.textCursor().position())

    def _region(self):
        """这一帧要画的内容区域（光标 + 尾迹 + 脉冲晕），带外扩。"""
        region = QRect()
        now = self._now()
        current = self._pos if self._pos is not None else self._idle_rect()
        if current is not None:
            region = region.united(current)
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
        """滚动 / 缩放 / 文档重排之后重新对齐光标（现算新位置并擦掉旧位置）。"""
        if self._pos is not None:                # 滑行中：每帧都按当前位置重算，不用管
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
        edited = length != self._last_len        # 文档长度变了 => 打字 / 删除
        self._last_len = length

        self._caret_on = True
        self._solid_until = self._now() + SOLID_MS
        self._blink_timer.start()                # 重新计时闪烁周期

        # 起点取"改文档前屏幕上画着的矩形"；滑行中则从当前插值位置接着走。
        # 注意：不能用 previous 位置现算——退格 / 删除之后那个位置已经不可信。
        start = self._pos if self._pos is not None else self._visual
        self._pending = (start, previous, position, edited)
        # 终点矩形要等这一轮事件循环结束、布局重排完成之后再算：在
        # cursorPositionChanged 里立刻 cursorRect() 拿到的还是"删了字但没重排"的
        # 旧坐标，实测会让光标到位后又回弹几个像素（看着就是抖）
        if not self._pending_timer.isActive():
            self._pending_timer.start()

    def _apply_pending_move(self):
        """一轮事件循环之后处理这次移动：此时布局已经稳定，矩形是准的。"""
        pending, self._pending = self._pending, None
        if pending is None:
            return
        start, previous, position, edited = pending
        if position != self.textCursor().position():
            return                               # 期间又动过：等它的信号自己处理

        target = self._rect_for(position)
        burst = self._last_move_at is not None and (self._now() - self._last_move_at) < BURST_MS
        self._last_move_at = self._now()
        if edited:
            # 编辑类：文字自己在动（还会重排），光标只做短促的跟手滑行，并且
            # 不改色、不做脉冲、不留尾迹——连打退格时这几样叠在一起就是"抖"。
            # 连打（或大跳：删换行、删选区、整段重排）直接落位，最稳。
            self._accent_until = 0
            near = start is not None and not burst \
                and abs(target.left() - start.left()) <= EDIT_SNAP_DX \
                and target.top() == start.top()
            if near and not self._composing:
                self._nav = False
                self._begin_animation(start, position, target, EDIT_MS)
            else:
                self._stop_animation()
                self._visual = target        # 立刻对齐：下一次移动要以它为起点
                self._schedule_paint()
            return

        # 导航类：方向键 / 点击 / 查找跳转 —— 完整滑行 + 强调色 + 落点脉冲
        self._accent_until = self._now() + ACCENT_MS
        if start is None and previous is not None:
            # 还没画过光标（_visual 为空）时，用旧位置现算起点：导航类文本没变，
            # 这个位置是可靠的（编辑类不能这么算，见 docstring 第 4 条）
            start = self._rect_for(previous)
        if start is None or self._composing or previous is None:
            self._stop_animation()               # 组词中 / 首次定位 / 无起点：直接落位
            self._visual = target
            self._schedule_paint()
            return
        if (start.left(), start.top()) == (target.left(), target.top()):
            self._stop_animation()               # 屏幕上没变（例如仅重排）：不滑行
            self._visual = target
            self._schedule_paint()
            return

        self._nav = start.top() != target.top() or abs(position - previous) > 1
        distance = abs(target.left() - start.left()) + abs(target.top() - start.top())
        duration = int(min(MOVE_MAX_MS, MOVE_MIN_MS + distance * MOVE_MS_PER_PX))
        self._begin_animation(start, position, target, duration)

    def _begin_animation(self, start, position, target, duration):
        """启动一次滑行：起点是屏幕矩形，终点是字符位置（逐帧现算）。"""
        self._from_rect = QRect(start)
        self._from_scroll = (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
        self._to_pos = position
        self._duration = max(1, duration)
        if self._scroll_into_view(target):
            # 有滚动动画在跑：让滑行晚一点落地，光标跟着滚动一起到位
            self._duration = max(self._duration, SCROLL_MS + 40)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._trail.clear()
        self._pulse_until = 0
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
        self._trail.clear()
        self._pulse_until = 0

    def _start_rect(self):
        """动画起点：捕获时屏幕上的矩形，按之后的滚动量平移（滚动中仍贴合原内容）。"""
        dx = self.horizontalScrollBar().value() - self._from_scroll[0]
        dy = self.verticalScrollBar().value() - self._from_scroll[1]
        return self._from_rect.translated(-dx, -dy)

    def _target_rect(self):
        """动画终点：按当前光标位置现算（滚动 / 重排后自动跟随）。"""
        return self._rect_for(self._to_pos)

    def _tick(self):
        now = self._now()
        animating = self._from_rect is not None
        if animating:
            total = min(1.0, self._elapsed.elapsed() / self._duration)
            self._pos = self._interpolate(total)
            if total >= 1.0:
                self._visual = self._target_rect()   # 落位后立刻对齐：下一次移动从这里起步
                self._pos = None
                self._from_rect = None
                self._to_pos = None
                if self._nav:
                    self._pulse_until = now + PULSE_MS
            else:
                if self._nav:                    # 尾迹只给导航类，编辑时留痕会显得闪
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
        self._schedule_paint()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._blink_timer.stop()
        self._schedule_paint()                   # 失焦后要擦掉自绘光标

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
        rect = self._pos if self._pos is not None else self._idle_rect()
        self._visual = rect                      # 记下这一帧画在哪：下次动画的起点
        if rect is None:
            return
        now = self._now()
        painter = QPainter(self.viewport())

        for ghost, stamp in self._trail:         # 尾迹：越旧越淡
            age = now - stamp
            if age >= TRAIL_MS:
                continue
            alpha = int(TRAIL_ALPHA * (1 - age / TRAIL_MS))
            painter.fillRect(ghost, QColor(*ACCENT, alpha))

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
