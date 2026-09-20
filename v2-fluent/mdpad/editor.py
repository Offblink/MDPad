"""编辑器控件：平滑移动光标——**只有一个动画**：滑行（+ 运动期间的强调色）。

为什么自绘光标：QTextEdit 的原生光标是瞬移的，Qt 没有给插值的钩子。
做法是 `setCursorWidth(0)` 关掉原生光标，在 `paintEvent` 里自己画一个，
用 QTimer 逐帧插值；闪烁与颜色也由本控件自管。

行为（就这一套，打字 / 退格 / 方向键 / 点击 / 查找跳转全都一样）：
  - 滑行：起终点之间按 OutCubic 插值，同视觉行直接横移，跨行走 L 形
    （先纵向到位再横向）；时长按距离 70~110ms
  - 颜色：运动期间用 Fluent 强调色，停下 300ms 后回正文色
  - 落点在视口外：先把滚动条平滑滚过去（180ms），光标这段路一起走完
  - 连打（距上次移动 < 90ms）：直接落位。此时打字 / 退格正在让文字快速重排，
    任何滑行都会变成"追"着跑，观感就是抖；单发按键仍然滑行
  - 闪烁：移动后保持实心 500ms，之后 530ms 周期闪

三个实测坑（改这里之前先读）：
  1. `cursorPositionChanged` 对同一次移动会发多次信号，必须按光标位置去重；
     否则后到的信号会把动画起点重置到终点，动画直接消失（看着像没生效）。
  2. `cursorWidth=0` 时 `cursorRect()` 返回**宽度为 0 的空矩形**，在 Python 里是假值。
     任何 `a or b` 形式的挑选都会静默挑错，必须显式判 None；光标宽度也只能自己定。
  3. **起点/终点都不能拿"位置"现算——一个要延后算，一个只能取屏幕上的**：
     - 起点：取"改文档之前屏幕上真正画着的那个矩形"。退格 / 删除是"先改文档、
       再移动光标"，拿旧位置在新文本里重算会落到完全不同的地方（换行被删掉就是
       另一行，超出文档长度时甚至算到布局之外：实测文档末尾退格得到 y=-1227 的
       矩形，光标从 1900px 外飞进来）。
     - 终点：推迟一轮事件循环再算。在 `cursorPositionChanged` 里立刻 `cursorRect()`
       拿到的是"字改了但还没重排"的旧坐标，会让光标到位后又回弹几像素（实测 5~8px），
       连打退格时就是"抖"。
  另外 Qt 只重绘脏区域，自绘光标必须自己记账：移动、闪烁、滚动、缩放之后都要把
  「上一帧画过的矩形 ∪ 这一帧要画的矩形」交给 `viewport().update()`，否则会留下幽灵光标。
"""
from PyQt5.QtCore import QEasingCurve, QElapsedTimer, QRect, QRectF, Qt, QTimer, QVariantAnimation
from PyQt5.QtGui import QColor, QPainter, QTextCursor
from PyQt5.QtWidgets import QTextEdit

import os

if os.name == 'nt':
    import ctypes
    from ctypes import wintypes

    class _GUITHREADINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                    ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                    ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                    ("rcCaret", wintypes.RECT)]

    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32
    _kernel32 = ctypes.windll.kernel32
else:                                            # 非 Windows：不维护系统光标
    _user32 = None

ACCENT = (0, 120, 212)      # Fluent 强调色（运动期间的光标色）
CARET_W = 2                 # 自绘光标宽度（原生 1px，这里 2px 更显动画）
MOVE_MIN_MS = 70            # 滑行时长下限
MOVE_MAX_MS = 110           # 滑行时长上限（长距离也是这个量级：一次短促的滑行）
MOVE_MS_PER_PX = 0.25       # 距离 → 时长
BURST_MS = 90               # 距上次移动小于这个间隔就算"连打"：直接落位（不滑）
SCROLL_MS = 180             # 落点在视口外时的滚动时长
SOLID_MS = 500              # 移动后保持实心的时长，之后开始闪
BLINK_MS = 530              # 闪烁周期
ACCENT_MS = 300             # 运动结束后强调色保持时长
PAD = 3                     # 局部重绘外扩，避免残留边


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


class MarkdownEditor(QTextEdit):
    """QTextEdit + 平滑移动光标；其余行为与原控件一致。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursorWidth(0)                   # 关掉原生光标（它只会瞬移）

        self._last_pos = None                    # 去重：上次处理过的光标位置
        self._visual = None                      # 上一帧真正画在屏幕上的光标矩形
        self._from_rect = None                   # 本次动画起点（改文档前屏幕上的矩形）
        self._from_scroll = (0, 0)               # 记录起点时的滚动条值，滚动时跟着平移
        self._to_pos = None                      # 本次动画终点（字符位置，逐帧现算矩形）
        self._pos = None                         # 动画中的插值矩形；None = 没有在滑行
        self._duration = MOVE_MIN_MS
        self._accent_until = 0
        self._solid_until = 0
        self._caret_on = True
        self._composing = False                  # 输入法组词中：不做动画
        self._last_len = self.document().characterCount()   # 判断这次移动有没有改文档
        self._text_changed = False
        self._last_move_at = None                # 上次移动的时刻，用来识别"连打"
        self._painted = QRect()                  # 上一帧占用区域（用于擦除）
        self._caret_bitmap = None                # 隐形系统光标的位图（Windows）
        self._caret_bits = None
        self._scroll_ani = None

        self._clock = QElapsedTimer()
        self._clock.start()

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(12)         # ≈80 FPS
        self._anim_timer.timeout.connect(self._tick)

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(BLINK_MS)
        self._blink_timer.timeout.connect(self._blink)

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
        """静止时光标该画的位置：每次现算，文档重排 / 滚动后也永远是对的。"""
        if not self.hasFocus():
            return None
        return self._rect_for(self.textCursor().position())

    def _region(self):
        """这一帧要画的区域（当前光标矩形），带外扩。"""
        current = self._pos if self._pos is not None else self._idle_rect()
        if current is None:
            return QRect()
        return current.adjusted(-PAD, -PAD, PAD, PAD)

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

        self._caret_on = True
        self._solid_until = self._now() + SOLID_MS
        self._accent_until = self._now() + ACCENT_MS
        self._blink_timer.start()                # 重新计时闪烁周期

        # 起点取"改文档前屏幕上画着的矩形"（见 docstring 第 3 条）；终点延后算
        length = self.document().characterCount()
        self._text_changed = length != self._last_len
        self._last_len = length
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
            self._stop_animation()               # 连打 / 组词中 / 首次定位：直接落位
            self._visual = target
            self._schedule_paint()
            return
        if (start.left(), start.top()) == (target.left(), target.top()):
            self._stop_animation()               # 屏幕上没变（例如仅重排）：不滑行
            self._visual = target
            self._schedule_paint()
            return

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
            self._pos = None
            self._from_rect = None
            self._to_pos = None
            self._anim_timer.stop()
        self._caret_on = True
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

    # ---------- 闪烁 / 焦点 ----------

    def _blink(self):
        if self._now() < self._solid_until:
            self._caret_on = True
            return
        self._caret_on = not self._caret_on
        self._schedule_paint()

    def _system_caret_window(self):
        """当前线程的"系统光标"属于哪个窗口（None = 系统里没有光标）。"""
        if _user32 is None:
            return None
        info = _GUITHREADINFO()
        info.cbSize = ctypes.sizeof(_GUITHREADINFO)
        if not _user32.GetGUIThreadInfo(_kernel32.GetCurrentThreadId(), ctypes.byref(info)):
            return None
        return info.hwndCaret

    def _ensure_system_caret(self):
        """让 Windows 也知道光标在哪

        自绘光标用 `setCursorWidth(0)` 关掉原生光标之后，Qt 就不再创建系统光标了
        （实测 `hwndCaret = None`、`rcCaret = (0,0,0,0)`）。可输入法（以及"文本光标
        指示器"这类辅助功能）恰恰是问系统要这个位置的：拿到空值就把候选框贴到窗口
        左上角，光标在行首这种边界还会偏到上一行——只补 Qt 的 `inputMethodQuery` 不够，
        因为那条路不是所有输入法都走。

        这里自己建一个"有尺寸、但位图全 0（= 不可见）"的系统光标，并一直把它摆到
        真实光标位置：Windows 由位图 XOR 出光标，全 0 位图等于不改变屏幕，所以
        既不会多出一个光标，`rcCaret` 又是准的。
        """
        if _user32 is None or not self.hasFocus():
            return
        hwnd = int(self.viewport().winId())
        if not hwnd:
            return
        if not self._system_caret_window():
            height = max(self.fontMetrics().height(), 8)
            row_bytes = ((CARET_W + 15) // 16) * 2       # 1bpp 位图按 16 位对齐
            self._caret_bits = ctypes.create_string_buffer(row_bytes * height)   # 全 0
            self._caret_bitmap = _gdi32.CreateBitmap(CARET_W, height, 1, 1, self._caret_bits)
            if not self._caret_bitmap:
                return
            _user32.DestroyCaret()
            if not _user32.CreateCaret(hwnd, self._caret_bitmap, 0, 0):
                return
            _user32.ShowCaret(hwnd)
        rect = self._rect_for(self.textCursor().position())
        _user32.SetCaretPos(rect.left(), rect.top())

    def _destroy_system_caret(self):
        if _user32 is not None and self._system_caret_window():
            _user32.DestroyCaret()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._caret_on = True
        self._solid_until = self._now() + SOLID_MS
        self._blink_timer.start()
        self._ensure_system_caret()
        self._schedule_paint()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._blink_timer.stop()
        self._destroy_system_caret()             # 失焦后系统里也不该留光标
        self._schedule_paint()                   # 失焦后要擦掉自绘光标

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resync()

    def inputMethodEvent(self, event):
        self._composing = bool(event.preeditString())
        super().inputMethodEvent(event)
        self._composing = bool(event.preeditString())

    def inputMethodQuery(self, query):
        """把光标矩形查询补成有宽度的矩形——否则输入法的候选框会跑到窗口左上角。

        `setCursorWidth(0)` 之后 Qt 自己的查询结果宽度是 0（实测
        `ImCursorRectangle = QRectF(x, y, 0, h)`），Windows 拿这个矩形定位候选框时
        会退化成"窗口左上角"。这里直接用当前光标位置给一个正常宽度的矩形。
        """
        if query in (Qt.ImCursorRectangle, Qt.ImMicroFocus):
            rect = self.cursorRect(self.textCursor())
            return QRectF(rect.left(), rect.top(), max(CARET_W, 1), rect.height())
        return super().inputMethodQuery(query)

    # ---------- 绘制 ----------

    def paintEvent(self, event):
        super().paintEvent(event)
        self._ensure_system_caret()               # 每次重绘都把系统光标摆正（输入法靠它定位）
        rect = self._pos if self._pos is not None else self._idle_rect()
        self._visual = rect                      # 记下这一帧画在哪：下次动画的起点
        if rect is None:
            return
        painter = QPainter(self.viewport())
        if self._pos is not None or self._now() < self._accent_until:
            painter.fillRect(rect, QColor(*ACCENT))          # 运动期间：强调色
        elif self._caret_on:
            painter.fillRect(rect, self.palette().color(self.foregroundRole()))
