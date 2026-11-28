"""Markdown 扩展：把颜色短标记 ``[红]…[/]`` / ``[#e81123]…[/]`` 换成内联 HTML。

为什么是预处理器而不是行内处理器：一个颜色段可能跨过 `**加粗**`、`*斜体*`、链接等
其它行内元素，行内处理器匹配的只是一段原文、拿不到已经转换过的兄弟节点；在源码层面
把开闭标记换成 ``<span>`` / ``</span>``（markdown 默认直通 inline HTML），里面其余
标记照常解析，嵌套也自然成立。

三条边界：

- 只认**成对**的标记（栈式配对，且不跨空行）：落单的 ``[红]`` 原样保留，不会把后文
  整段染色；``\\[红]`` 是转义写法，同样原样保留。
- 行内代码（反引号里）与缩进代码块里的同名文本不转换。
- 优先级 20 排在 fenced_code（25）之后：围栏代码此时已入 htmlStash，碰不到。
"""
import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

from .colors import iter_tokens

#: 缩进代码块：段首 4 空格或制表符（段与段之间一定有空行，见 run()）
_INDENTED_RE = re.compile(r"^(?: {4,}|\t)")
_SPAN_OPEN = '<span style="color:{color}">'
_SPAN_CLOSE = "</span>"


class ColorMarkupPreprocessor(Preprocessor):
    """按段落把成对的颜色标记换成 span（段落之间用空行切开）。"""

    def run(self, lines):
        out = []
        paragraph = []
        for line in lines:
            if line.strip():
                paragraph.append(line)
                continue
            if paragraph:
                out.extend(self._convert("\n".join(paragraph)).split("\n"))
                paragraph = []
            out.append(line)
        if paragraph:
            out.extend(self._convert("\n".join(paragraph)).split("\n"))
        return out

    def _convert(self, paragraph):
        if _INDENTED_RE.match(paragraph):
            return paragraph  # 缩进代码块：整段不碰
        tokens = list(iter_tokens(paragraph))
        stack, pairs = [], []
        for index, token in enumerate(tokens):
            if token.kind == "open":
                stack.append(index)
            elif stack:
                pairs.append((stack.pop(), index))
        if not pairs:
            return paragraph
        replacements = {}
        for open_index, close_index in pairs:
            opening, closing = tokens[open_index], tokens[close_index]
            replacements[opening.start] = (_SPAN_OPEN.format(color=opening.color), opening.end)
            replacements[closing.start] = (_SPAN_CLOSE, closing.end)
        pieces, cursor = [], 0
        for start in sorted(replacements):
            value, end = replacements[start]
            pieces.append(paragraph[cursor:start])
            pieces.append(value)
            cursor = end
        pieces.append(paragraph[cursor:])
        return "".join(pieces)


class ColorExtension(Extension):
    """预览与导出共用：短标记 → 内联 HTML。"""

    def extendMarkdown(self, md):
        # fenced_code 在 25；20 排它之后，围栏代码已经进 htmlStash
        md.preprocessors.register(ColorMarkupPreprocessor(md), "mdpad_color", 20)
