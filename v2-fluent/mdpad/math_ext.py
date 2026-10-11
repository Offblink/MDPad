"""Markdown 数学公式扩展：把 $...$ / $$...$$ 摘成 KaTeX 的占位元素。

为什么不能只丢给前端：python-markdown 的强调与转义规则会先吃掉公式里的
`_`、`*`、`\\`（`x_i` 会被斜体化），所以公式必须在行内规则之前整体摘出来。

- 行内公式 `$...$` → `<span class="mdpad-math">`（行内规则优先级 185，
  夹在 backtick(190) 与 escape(180) 之间：代码段里的 `$` 不受影响，
  `\\$` 转义也仍然有效）
- 显示公式 `$$...$$`（单行或跨行成段）→ `<div class="mdpad-math-display">`
  由预处理阶段整段提取，代码围栏（``` / ~~~）与四空格缩进代码块里的
  `$$` 原样保留

元素内容是公式原文（HTML 转义后的文本），由预览页 / 导出页里的 KaTeX
读取 textContent 渲染（见 preview.py 的 mdpadRenderMath、本模块的
katex_head_html）。
"""
import base64
import html
import re
from pathlib import Path
from xml.etree import ElementTree as etree

from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.preprocessors import Preprocessor

# KaTeX 资产（随仓库分发，见 assets/katex）；打包时由 MDPad.spec 收集
KATEX_DIR = Path(__file__).resolve().parent / 'assets' / 'katex'
KATEX_JS = KATEX_DIR / 'katex.min.js'
KATEX_CSS = KATEX_DIR / 'katex.min.css'

INLINE_CLASS = 'mdpad-math'
DISPLAY_CLASS = 'mdpad-math-display'

# 行内公式：开 $ 后不接空白、闭 $ 前不接空白；内容里不许有裸 $ 与裸反引号
# （反引号交给 backtick 优先级处理），\\. 允许转义；不跨行。
# 两侧的 $ 守卫（不能紧挨另一个 $）保证 $$...$$ 不会被拆成两层单 $ 公式
INLINE_RE = (
    r'(?<![\\$])\$(?![\s$])(?P<math>(?:[^\\$`\n]|\\.)+?)(?<![\s$])(?<!\\)\$(?!\$)'
)

# 行内出现的 $$...$$（整行单独成段的由预处理阶段接管）：当作显示公式
DISPLAY_INLINE_RE = (
    r'(?<![\\$])\$\$(?![\s$])(?P<math>(?:[^\\$`\n]|\\.)+?)(?<![\s$])(?<!\\)\$\$(?!\$)'
)

# 显示公式：允许最多 3 个空格缩进；4 空格缩进属于代码块，不碰
_BLOCK_START_RE = re.compile(r'^[ \t]{0,3}\$\$(?P<rest>.*)$')
_BLOCK_END_RE = re.compile(r'^(?P<body>.*?)\$\$[ \t]*$')
_FENCE_RE = re.compile(r'^[ \t]{0,3}(`{3,}|~{3,})')


class MathInlineProcessor(InlineProcessor):
    """行内 $...$ → <span class="mdpad-math">。"""

    def handleMatch(self, m, data):
        el = etree.Element('span')
        el.set('class', INLINE_CLASS)
        el.text = m.group('math')
        return el, m.start(0), m.end(0)


class MathDisplayInlineProcessor(InlineProcessor):
    """行内出现的 $$...$$ → <span class="mdpad-math-display">（KaTeX displayMode）。"""

    def handleMatch(self, m, data):
        el = etree.Element('span')
        el.set('class', DISPLAY_CLASS)
        el.text = m.group('math')
        return el, m.start(0), m.end(0)


class MathBlockPreprocessor(Preprocessor):
    """把成段的 $$...$$ 提成 <div class="mdpad-math-display">。"""

    def run(self, lines):
        out = []
        i = 0
        fence = None
        total = len(lines)
        while i < total:
            line = lines[i]
            stripped = line.lstrip()
            if fence is None:
                fm = _FENCE_RE.match(line)
                if fm:
                    fence = fm.group(1)[0] * 3
                    out.append(line)
                    i += 1
                    continue
            else:
                if stripped.startswith(fence):
                    fence = None
                out.append(line)
                i += 1
                continue

            start = _BLOCK_START_RE.match(line)
            if not start:
                out.append(line)
                i += 1
                continue

            rest = start.group('rest')
            # 单行 $$...$$
            single = _BLOCK_END_RE.match(rest)
            if single and single.group('body').strip():
                out.append(self._display_html(single.group('body').strip()))
                i += 1
                continue

            # 跨行：收集到收尾的 $$ 那一行为止
            collected = [line]
            body = [rest] if rest.strip() else []
            i += 1
            closed = False
            while i < total:
                line = lines[i]
                collected.append(line)
                end = _BLOCK_END_RE.match(line)
                if end is not None:
                    body.append(end.group('body'))
                    i += 1
                    closed = True
                    break
                body.append(line)
                i += 1
            if closed:
                out.append(self._display_html('\n'.join(body).strip('\n')))
            else:
                # 未闭合：原样放回，交给后面的规则当普通文本
                out.extend(collected)
        return out

    @staticmethod
    def _display_html(body):
        return f'<div class="{DISPLAY_CLASS}">{html.escape(body, quote=False)}</div>'


class MathExtension(Extension):
    """注册行内 / 显示公式规则。"""

    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            MathDisplayInlineProcessor(DISPLAY_INLINE_RE, md), 'mdpad_math_display', 186
        )
        md.inlinePatterns.register(MathInlineProcessor(INLINE_RE, md), 'mdpad_math', 185)
        md.preprocessors.register(MathBlockPreprocessor(md), 'mdpad_math_block', 26)


def has_math(html_text):
    """渲染结果里是否真的出现了公式（导出时据此决定要不要带上 KaTeX）。"""
    return INLINE_CLASS in html_text or DISPLAY_CLASS in html_text


_RENDER_FN_JS = """
function mdpadRenderMath(root) {
    if (typeof katex === 'undefined') { return; }
    var nodes = (root || document).querySelectorAll('.%(inline)s, .%(display)s');
    for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        if (node.getAttribute('data-mdpad-math') === 'done') { continue; }
        node.setAttribute('data-mdpad-math', 'done');
        try {
            katex.render(node.textContent, node, {
                displayMode: node.classList.contains('%(display)s'),
                throwOnError: false,
            });
        } catch (e) {
            // 渲染失败就保留公式原文
        }
    }
}
""" % {'inline': INLINE_CLASS, 'display': DISPLAY_CLASS}


def render_function_js():
    """预览页共用的 JS 渲染函数（页面内 HTML 更新后调用一次）。"""
    return _RENDER_FN_JS


def katex_head_html():
    """自足的 KaTeX 头（样式 + 脚本内联），导出 HTML 用。

    字体在 CSS 里以 data: URI 内联，导出的单个 HTML 文件不依赖外部资源、
    断网也能渲染。资产缺失时返回空串（导出照旧，公式显示为原文）。
    """
    if not (KATEX_JS.is_file() and KATEX_CSS.is_file()):
        return ''
    css = KATEX_CSS.read_text(encoding='utf-8')
    for font in sorted((KATEX_DIR / 'fonts').glob('*.woff2')):
        # 只把 woff2 换成本地 data: URI；CSS 里 woff/ttf 兜底项保持原样 ——
        # 它们指向没随仓库分发的文件，但浏览器按 src 顺序优先取 woff2，不会去碰它们
        data_uri = 'data:font/woff2;base64,' + base64.b64encode(font.read_bytes()).decode('ascii')
        css = css.replace(f'url(fonts/{font.name})', f'url({data_uri})')
    js = KATEX_JS.read_text(encoding='utf-8')
    return (
        f'<style>{css}</style>\n'
        f'<script>{js}</script>\n'
        f'<script>{_RENDER_FN_JS}\nwindow.addEventListener("DOMContentLoaded", function () '
        f'{{ mdpadRenderMath(document.body); }});</script>\n'
    )
