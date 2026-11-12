"""Markdown 流程图扩展：把 ```mermaid 围栏摘成预览页可渲染的占位元素。

为什么不能只丢给前端：fenced_code + codehilite 会先把围栏当代码块处理，
mermaid 在 Pygments 里没有词法（会掉进"猜语言"的兜底高亮），语言信息在这一步
就丢了，前端再也认不出这是流程图。所以本扩展的预处理器排在 fenced_code
（优先级 25）之前，把 ```mermaid 围栏整块换成
`<div class="mdpad-mermaid">源码原文</div>` 直接入 htmlStash，
后续的高亮、行内规则都碰不到它。

元素内容是流程图源码（HTML 转义后的文本），由预览页 / 导出页里的 mermaid JS
读取 textContent 渲染成 SVG（见 preview.py、本模块的 render_function_js 与
mermaid_head_html）。资产缺失或渲染失败时，源码原文照常显示。
"""
import html
import json
import re
from pathlib import Path

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

# mermaid 资产（随仓库分发，见 assets/mermaid）；打包时由 MDPad.spec 收集
MERMAID_DIR = Path(__file__).resolve().parent / 'assets' / 'mermaid'
MERMAID_JS = MERMAID_DIR / 'mermaid.min.js'

MERMAID_CLASS = 'mdpad-mermaid'

# 开围栏：0-3 空格缩进的 ``` 或 ~~~，语言词正好是 mermaid（后面只许跟空白或行尾）
_FENCE_START_RE = re.compile(
    r'^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[ \t]*mermaid(?=[ \t]|$).*$'
)


def _closing_re(fence):
    """闭围栏：同一串围栏字符，后面只许有空白（与 fenced_code 口径一致）。"""
    return re.compile(r'^[ \t]*' + re.escape(fence) + r'[ \t]*$')


class MermaidBlockPreprocessor(Preprocessor):
    """```mermaid 围栏 → <div class="mdpad-mermaid">源码原文</div>（入 htmlStash）。"""

    def run(self, lines):
        out = []
        i, total = 0, len(lines)
        while i < total:
            m = _FENCE_START_RE.match(lines[i])
            if not m:
                out.append(lines[i])
                i += 1
                continue
            close_re = _closing_re(m.group('fence'))
            j = i + 1
            while j < total and not close_re.match(lines[j]):
                j += 1
            if j >= total:
                # 没有闭合：不是合法围栏，交回给 fenced_code 按普通代码块处理
                out.append(lines[i])
                i += 1
                continue
            source = '\n'.join(lines[i + 1:j])
            out.append(self.md.htmlStash.store(
                f'<div class="{MERMAID_CLASS}">'
                f'{html.escape(source, quote=False)}</div>'
            ))
            i = j + 1
        return out


class MermaidExtension(Extension):
    """注册 mermaid 围栏预处理器（须排在 fenced_code 之前）。"""

    def extendMarkdown(self, md):
        # fenced_code 在 25；26 与 MathBlockPreprocessor 同级，两者不相干
        md.preprocessors.register(MermaidBlockPreprocessor(md), 'mdpad_mermaid', 26)


def has_mermaid(html_text):
    """渲染结果里是否真的出现了流程图（导出时据此决定要不要带上 mermaid）。"""
    return MERMAID_CLASS in html_text


_RENDER_FN_JS = """
var mdpadMermaidLoader = null;
var mdpadMermaidInited = false;
var mdpadMermaidSeq = 0;

// 首次遇到流程图才拉脚本（2.8MB，不该让每次预览启动都付这个钱）；
// 资产缺失或加载失败时占位元素里的源码原文照常显示。
function mdpadLoadMermaid() {
    if (typeof mermaid !== 'undefined') { return Promise.resolve(); }
    if (!mdpadMermaidSrc) { return Promise.reject(new Error('mermaid 资产缺失')); }
    if (!mdpadMermaidLoader) {
        mdpadMermaidLoader = new Promise(function (resolve, reject) {
            var s = document.createElement('script');
            s.src = mdpadMermaidSrc;
            s.onload = function () { resolve(); };
            s.onerror = function () { reject(new Error('mermaid 加载失败')); };
            document.head.appendChild(s);
        });
    }
    return mdpadMermaidLoader;
}

// mermaid.render 失败时会把临时元素留在 body 里（id 与 d+id），清掉
function mdpadDropMermaidTemp(id) {
    [id, 'd' + id].forEach(function (nid) {
        var el = document.getElementById(nid);
        if (el && el.parentNode) { el.parentNode.removeChild(el); }
    });
}

// 渲染页面里所有还没画过的流程图；返回 Promise，调用方好在 SVG 高度出来后
// 把滚动位置钉回去（见 preview.py 的 _update_content_with_js）。
function mdpadRenderMermaid(root) {
    var nodes = (root || document).querySelectorAll('.mdpad-mermaid');
    if (!nodes.length) { return Promise.resolve(); }
    return mdpadLoadMermaid().then(function () {
        if (!mdpadMermaidInited) {
            mdpadMermaidInited = true;
            mermaid.initialize({ startOnLoad: false });
        }
        var jobs = [];
        for (var i = 0; i < nodes.length; i++) {
            jobs.push((function (node) {
                if (node.getAttribute('data-mdpad-mermaid') === 'done') { return null; }
                node.setAttribute('data-mdpad-mermaid', 'done');
                var source = node.textContent;
                var id = 'mdpad-mermaid-' + (++mdpadMermaidSeq);
                var fallback = function () {
                    mdpadDropMermaidTemp(id);
                    node.textContent = source;  // 渲染失败退回源码原文
                };
                var pending;
                try {
                    pending = mermaid.render(id, source);
                } catch (e) {
                    fallback();
                    return null;
                }
                return Promise.resolve(pending).then(function (svg) {
                    node.innerHTML = svg;
                    node.classList.add('mdpad-mermaid-done');
                }, fallback);
            })(nodes[i]));
        }
        return Promise.all(jobs.filter(Boolean));
    }, function () {
        // 资产缺失 / 加载失败：什么都不做，源码原文已经在那儿了
    });
}
"""


def render_function_js(src_uri=None):
    """预览页 / 导出页共用的 JS 渲染函数（页面内 HTML 更新后调用一次）。

    src_uri 是 mermaid.min.js 的加载地址：预览页传 file:// URI 走懒加载，
    资产缺失时传 None；导出页不传——脚本已内联，直接用全局 mermaid。
    """
    return 'var mdpadMermaidSrc = %s;\n%s' % (
        json.dumps(src_uri) if src_uri else 'null', _RENDER_FN_JS,
    )


def mermaid_head_html():
    """自足的 mermaid 头（脚本内联），导出 HTML 用。

    导出的单个 HTML 文件不依赖外部资源、断网也能渲染。资产缺失时返回空串
    （导出照旧，流程图显示为源码原文）。
    """
    if not MERMAID_JS.is_file():
        return ''
    js = MERMAID_JS.read_text(encoding='utf-8')
    return (
        f'<script>{js}</script>\n'
        f'<script>{render_function_js()}\n'
        f'window.addEventListener("DOMContentLoaded", function () '
        f'{{ mdpadRenderMermaid(document.body); }});</script>\n'
    )
