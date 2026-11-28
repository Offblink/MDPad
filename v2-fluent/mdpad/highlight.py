"""编辑器内的颜色标记着色：标记里的文字直接按颜色显示，标记本身淡成水印。

跨行段：markdown 侧按「段落」配对（`color_ext` 不跨空行），所以这里的未闭合栈也要
带过块边界。QSyntaxHighlighter 的块状态只能是 int，用一张表把「颜色栈」编码成下标；
空行视作段落边界、栈清空。围栏代码里的标记不着色（与预览一致）。

「淡」用前景色的透明度实现，而不是预混背景色：主题是 Theme.AUTO，背景可能变，
透明度对明暗背景都成立，省掉主题切换时重算色值。
"""
import re

from PyQt5.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

from .colors import iter_tokens

#: 标记本身的透明度（0–255）：越小越像不存在；字符仍占位，不是隐藏
MARKER_ALPHA = 70
_FENCE_RE = re.compile(r"^[ \t]{0,3}(?:`{3,}|~{3,})")
_FALLBACK_COLOR = "#808080"


class ColorMarkupHighlighter(QSyntaxHighlighter):
    """给 ``[红]文字[/]`` 着色；写法见 colors.iter_tokens。"""

    def __init__(self, document):
        super().__init__(document)
        self._formats = {}
        self._states = []
        self._state_ids = {}

    # ---------- 块状态：把颜色栈编码成一个 int ----------

    def _entry(self, state):
        if 0 < state <= len(self._states):
            return self._states[state - 1]
        return "text", ()

    def _state_for(self, entry):
        state = self._state_ids.get(entry)
        if state is None:
            self._states.append(entry)
            state = len(self._states)
            self._state_ids[entry] = state
        return state

    # ---------- 格式 ----------

    def _format(self, color, marker):
        key = (color, marker)
        fmt = self._formats.get(key)
        if fmt is None:
            qcolor = QColor(color or _FALLBACK_COLOR)
            if marker:
                qcolor.setAlpha(MARKER_ALPHA)
            fmt = QTextCharFormat()
            fmt.setForeground(qcolor)
            self._formats[key] = fmt
        return fmt

    # ---------- 着色 ----------

    def highlightBlock(self, text):
        # PyQt 下 currentBlockState() 进块时是 -1（不反映上一块），跨块状态只能读
        # previousBlockState()：它就是上一块 setCurrentBlockState 存下的值。
        kind, stack = self._entry(self.previousBlockState())
        if _FENCE_RE.match(text) or kind == "code":
            # 围栏线：进出代码状态；代码内：保持状态、不做颜色处理
            self.setCurrentBlockState(self._state_for(("code", ())))
            return
        stack = list(stack)
        if not text.strip():
            stack = []  # 空行是段落边界，与 color_ext 的配对口径一致
        position = 0
        for token in iter_tokens(text):
            if position < token.start and stack:
                self.setFormat(position, token.start - position, self._format(stack[-1], False))
            if token.kind == "open":
                marker_color = token.color
            else:
                marker_color = stack[-1] if stack else None
            self.setFormat(token.start, token.end - token.start,
                           self._format(marker_color, True))
            if token.kind == "open":
                stack.append(token.color)
            elif stack:
                stack.pop()
            position = token.end
        if position < len(text) and stack:
            self.setFormat(position, len(text) - position, self._format(stack[-1], False))
        self.setCurrentBlockState(self._state_for(("text", tuple(stack))))
