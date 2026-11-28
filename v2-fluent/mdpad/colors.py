"""字体颜色：Markdown 短标记 ``[红]文字[/]``、``[#e81123]文字[/]``。

颜色是文档内容而不是编辑器主题：预览 / 导出时由 `color_ext` 换成
``<span style="color:#rrggbb">``；编辑器里由 `highlight` 直接按颜色显示文字、
把标记淡成水印。旧文档里的 ``<span style="color:#rrggbb">`` 走同一套识别逻辑，
写入一律用短标记：预设色 3 + 3 个字符（``[红]`` / ``[/]``），自定义色 9 + 3。

本模块只做纯逻辑与菜单色块图标，UI 编排在 main_window，渲染在两处：
`color_ext`（预览 / 导出）与 `highlight`（编辑器着色）。
"""
import re
from collections import namedtuple

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap

#: 菜单预设色（标记名, #RRGGBB）；标记名是单字，写进文档就是 ``[红]``
PRESET_COLORS = (
    ("红", "#E81123"),
    ("绿", "#107C10"),
    ("蓝", "#0078D4"),
)

_NAME_BY_HEX = {hex_color.lower(): name for name, hex_color in PRESET_COLORS}

_HEX = r"#[0-9A-Fa-f]{6}"
_NAMES = "|".join(re.escape(name) for name, _ in PRESET_COLORS)

#: 开标记：``[红]`` / ``[#e81123]``，以及旧语法 ``<span style="color:#e81123">``
_OPEN_PATTERN = r"\[(?:" + _NAMES + r"|" + _HEX + r")\]"
_SPAN_OPEN_PATTERN = r'<span style="color:' + _HEX + r'">'
#: 闭标记：两种语法各一个（``[/]`` 是短语法的统一闭标签）
_CLOSE_PATTERN = r"\[/\]"
_SPAN_CLOSE = "</span>"

_TOKEN_RE = re.compile(
    r"(?P<short>" + _OPEN_PATTERN + r"|" + _CLOSE_PATTERN + r")"
    r"|(?P<span_open>" + _SPAN_OPEN_PATTERN + r")"
    r"|(?P<span_close>" + re.escape(_SPAN_CLOSE) + r")"
)
_OPEN_ONLY_RE = re.compile(_OPEN_PATTERN)
_SPAN_OPEN_ONLY_RE = re.compile(_SPAN_OPEN_PATTERN)
_TRAILING_OPEN_RE = re.compile(r"(?:" + _OPEN_PATTERN + r"|" + _SPAN_OPEN_PATTERN + r")\Z")
_LEADING_CLOSE_RE = re.compile(r"(?:" + _CLOSE_PATTERN + r"|" + re.escape(_SPAN_CLOSE) + r")")
_WHOLE_RE = re.compile(
    r"(" + _OPEN_PATTERN + r"|" + _SPAN_OPEN_PATTERN + r")"
    r"(.*)"
    r"(" + _CLOSE_PATTERN + r"|" + re.escape(_SPAN_CLOSE) + r")",
    re.S,
)
_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")

#: 一个标记：起止偏移、开/闭、颜色（闭标签只可能取到外层仍在栈里的颜色）
Token = namedtuple("Token", "start end kind color")


def normalize_color(color):
    """把预设名 / ``#RRGGBB`` / ``RRGGBB`` / QColor 统一成小写 ``#rrggbb``。"""
    if isinstance(color, QColor):
        return color.name().lower()
    text = str(color).strip()
    for name, hex_color in PRESET_COLORS:
        if text == name:
            return hex_color.lower()
    match = _HEX_RE.match(text)
    if not match:
        raise ValueError(f"不是有效的颜色值: {color!r}")
    return "#" + match.group(1).lower()


def open_marker(color):
    """颜色的开标记：预设色用单字名，其余用 6 位 hex。"""
    hex_color = normalize_color(color)
    name = _NAME_BY_HEX.get(hex_color)
    return f"[{name}]" if name else f"[{hex_color}]"


def _balanced(text):
    """内层标记成对（不含跨出边界的开 / 闭标签）。"""
    opens = len(_OPEN_ONLY_RE.findall(text)) + len(_SPAN_OPEN_ONLY_RE.findall(text))
    closes = len(re.findall(_CLOSE_PATTERN, text)) + text.count(_SPAN_CLOSE)
    return opens == closes


def _token_color(match):
    """从开标记的匹配里取颜色。"""
    if match.group("span_open"):
        return match.group("span_open")[len('<span style="color:'):-2].lower()
    short = match.group("short")
    return normalize_color(short[1:-1])


def _code_spans(text):
    """行内代码区间（成对的反引号）；未闭合的反引号按普通文本处理。"""
    spans = []
    index, total = 0, len(text)
    while index < total:
        if text[index] != "`":
            index += 1
            continue
        run_end = index
        while run_end < total and text[run_end] == "`":
            run_end += 1
        run = run_end - index
        scanned = run_end
        closing = None
        while scanned < total:
            if text[scanned] == "`":
                close_end = scanned
                while close_end < total and text[close_end] == "`":
                    close_end += 1
                if close_end - scanned == run:
                    closing = close_end
                    break
                scanned = close_end
            else:
                scanned += 1
        if closing is None:
            index = run_end
        else:
            spans.append((index, closing))
            index = closing
    return spans


def iter_tokens(text):
    """按出现顺序产出颜色标记（跳过转义与行内代码里的假标记）。"""
    code_spans = _code_spans(text)
    cursor = 0
    for match in _TOKEN_RE.finditer(text):
        while cursor < len(code_spans) and code_spans[cursor][1] <= match.start():
            cursor += 1
        if cursor < len(code_spans) and code_spans[cursor][0] <= match.start():
            continue  # 行内代码里：不是标记
        backslashes = 0
        back = match.start() - 1
        while back >= 0 and text[back] == "\\":
            backslashes += 1
            back -= 1
        if backslashes % 2:
            continue  # ``\[红]`` 是转义后的普通文本
        if match.group("short") == "[/]" or match.group("span_close"):
            yield Token(match.start(), match.end(), "close", None)
        else:
            yield Token(match.start(), match.end(), "open", _token_color(match))


def whole_wrapped(text):
    """整段被一个颜色标记包住时返回 (内部文本, 颜色)；否则 None。"""
    match = _WHOLE_RE.fullmatch(text)
    if not match:
        return None
    opening, inner, closing = match.groups()
    if opening.startswith("<") != closing.startswith("<"):
        return None  # 开闭分属两种语法，不是同一个标记
    if not _balanced(inner):
        return None
    return inner, normalize_color(opening[1:-1] if not opening.startswith("<")
                                  else opening[len('<span style="color:'):-2])


def wrap_colored(text, color):
    """给文本包上短标记；已被整个标记包住时只换开标记（不嵌套）。"""
    token = open_marker(color)
    whole = whole_wrapped(text)
    if whole is not None:
        return token + whole[0] + "[/]"
    return token + text + "[/]"


def unwrap_colored(text):
    """剥掉整段的颜色标记；没有标记返回 None。"""
    whole = whole_wrapped(text)
    return None if whole is None else whole[0]


def surrounding_span(block_text, start, end):
    """选区被某个颜色标记包住（前后紧邻开/闭标记）时返回 (标记起点, 标记终点, 颜色)。

    起点/终点是**块内**偏移，终点为闭标记之后。选区自身包含整段标记时由
    `whole_wrapped` 负责，这里只处理"选中标记内部文字"的常见情形。
    """
    if not (0 <= start < end <= len(block_text)):
        return None
    opened = _TRAILING_OPEN_RE.search(block_text, 0, start)
    if opened is None:
        return None
    closing = _LEADING_CLOSE_RE.match(block_text, end)
    if closing is None:
        return None
    if opened.group(0).startswith("<") != closing.group(0).startswith("<"):
        return None
    # 选区内层要成对，否则这个闭标记属于更外层的标记
    if not _balanced(block_text[opened.end():end]):
        return None
    return opened.start(), closing.end(), _token_color_from_open(opened.group(0))


def _token_color_from_open(token):
    """开标记文本 → 颜色。"""
    if token.startswith("<"):
        return token[len('<span style="color:'):-2].lower()
    return normalize_color(token[1:-1])


def swatch_icon(color, size=16):
    """菜单用的圆角色块图标。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor(0, 0, 0, 40))
    painter.setBrush(QColor(normalize_color(color)))
    painter.drawRoundedRect(QRectF(1.5, 1.5, size - 3, size - 3), 4, 4)
    painter.end()
    return QIcon(pixmap)
