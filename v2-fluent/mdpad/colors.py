"""字体颜色：Markdown 内联 HTML 颜色标记（`<span style="color:#RRGGBB">…</span>`）。

颜色是文档内容而不是编辑器主题：预览与导出 HTML 都原样显示（`markdown` 的 extra
扩展默认直通 inline HTML）。本模块只做纯逻辑与菜单色块图标，UI 编排在 main_window。
"""
import re

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap

#: 菜单预设色（名称, #RRGGBB）
PRESET_COLORS = (
    ("红色", "#E81123"),
    ("绿色", "#107C10"),
    ("蓝色", "#0078D4"),
    ("黑色", "#000000"),
)

_COLOR = r"(#[0-9A-Fa-f]{6})"
# 整段就是一个颜色标记（内层不再有未闭合的 span 才算）
_WHOLE_RE = re.compile(r'<span style="color:' + _COLOR + r'">(.*)</span>', re.S)
_TRAILING_OPEN_RE = re.compile(r'<span style="color:' + _COLOR + r'">$')
_LEADING_CLOSE_RE = re.compile(r"</span>")
_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")


def normalize_color(color):
    """把 `#RRGGBB` / `RRGGBB` / QColor 统一成小写 `#rrggbb`。"""
    if isinstance(color, QColor):
        return color.name().lower()
    match = _HEX_RE.match(str(color).strip())
    if not match:
        raise ValueError(f"不是有效的颜色值: {color!r}")
    return "#" + match.group(1).lower()


def _balanced(inner):
    """内层 span 成对（不含跨出标记边界的开/闭标签）。"""
    return inner.count("<span") == inner.count("</span>")


def whole_wrapped(text):
    """整段被一个颜色标记包住时返回 (内部文本, 颜色)；否则 None。"""
    match = _WHOLE_RE.fullmatch(text)
    if not match:
        return None
    inner = match.group(2)
    if not _balanced(inner):
        return None
    return inner, normalize_color(match.group(1))


def wrap_colored(text, color):
    """给文本包上颜色标记；已整段包裹时只改颜色值（不嵌套）。"""
    hex_color = normalize_color(color)
    whole = whole_wrapped(text)
    if whole is not None:
        return f'<span style="color:{hex_color}">{whole[0]}</span>'
    return f'<span style="color:{hex_color}">{text}</span>'


def unwrap_colored(text):
    """剥掉整段的颜色标记；没有标记返回 None。"""
    whole = whole_wrapped(text)
    return None if whole is None else whole[0]


def surrounding_span(block_text, start, end):
    """选区被某个颜色标记包住（前后紧邻开/闭标签）时返回 (标记起点, 标记终点, 颜色)。

    起点/终点是**块内**偏移，终点为闭标签之后。选区自身包含整段标记时由
    `whole_wrapped` 负责，这里只处理"选中标记内部文字"的常见情形。
    """
    if not (0 <= start < end <= len(block_text)):
        return None
    opened = _TRAILING_OPEN_RE.search(block_text, 0, start)
    if opened is None:
        return None
    closed = _LEADING_CLOSE_RE.match(block_text, end)
    if closed is None:
        return None
    # 选区内层要成对，否则这个闭标签属于更外层的标记
    if not _balanced(block_text[opened.end():end]):
        return None
    return opened.start(), closed.end(), normalize_color(opened.group(1))


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
