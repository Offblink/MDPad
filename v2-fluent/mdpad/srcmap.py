"""源码行号映射：给顶层块插 <!--mdpad-src:N--> 标记（预览跟随光标用）。

python-markdown 不像 markdown-it 那样给 token 带源码位置（token.map），
所以在解析之前先按"空行分段 + 同类构造合并"把正文切成顶层块，在每块首行
插一条注释标记它的起始行号。渲染结果里这些注释是独立的 DOM 注释节点、保持
文档顺序，前端用 Range 量出它的纵向位置即可——比"第 N 个子元素就是第 N 块"
稳（一块渲染成几个元素都不影响定位）。

标记只插在块首（空行之后）：那里不会破坏段落/标题/代码段/表格；
连续的列表项、引用行、表格行、缩进代码行会合并成同一块，避免标记夹在
列表项之间把列表劈成两个。
"""
import re

MARKER_PREFIX = 'mdpad-src:'

_LIST_RE = re.compile(r'^[ \t]{0,3}(?:[-*+]|\d{1,9}[.)])[ \t]')
_QUOTE_RE = re.compile(r'^[ \t]{0,3}>')
_TABLE_RE = re.compile(r'^[ \t]{0,3}\|')
_INDENT_RE = re.compile(r'^(?: {4}|\t)')
_FENCE_RE = re.compile(r'^[ \t]{0,3}(`{3,}|~{3,})')


def _family(line):
    """行所属的块族：同类构造的相邻段落要合并成一块，标记才不会打断它们。"""
    if _LIST_RE.match(line):
        return 'list'
    if _QUOTE_RE.match(line):
        return 'quote'
    if _TABLE_RE.match(line):
        return 'table'
    if _INDENT_RE.match(line):
        return 'code'
    return None


def tag_top_blocks(text):
    """返回插好行号标记的正文（标记行本身不属于原文档）。"""
    if not text:
        return text
    lines = text.split('\n')
    out = []
    total = len(lines)
    i = 0
    fence = None
    while i < total:
        if not lines[i].strip() and fence is None:
            out.append(lines[i])
            i += 1
            continue

        start_line = i + 1
        family = _family(lines[i]) if fence is None else None
        block = []
        while i < total:
            line = lines[i]
            fence_match = _FENCE_RE.match(line)
            if fence is None and fence_match:
                fence = fence_match.group(1)[0] * 3
                block.append(line)
                i += 1
                continue
            if fence is not None:
                if line.lstrip().startswith(fence):
                    fence = None
                block.append(line)
                i += 1
                continue
            if not line.strip():
                # 空行：仅当下一段属于同一构造时才继续吸收（松散列表、多段引用等）
                j = i
                while j < total and not lines[j].strip():
                    j += 1
                if j >= total or not family or _family(lines[j]) != family:
                    break
                block.extend(lines[i:j])
                i = j
                continue
            block.append(line)
            i += 1

        out.append(f'<!--{MARKER_PREFIX}{start_line}-->')
        out.extend(block)
    return '\n'.join(out)
