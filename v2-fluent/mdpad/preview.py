"""Markdown 预览组件：QWebEngineView + 链接拦截 + 图片基准目录。"""
import json
import os
import webbrowser
import html as html_module

from PyQt5.QtCore import Qt, QUrl, QObject, pyqtSlot
from PyQt5.QtWebEngineWidgets import (
    QWebEngineView, QWebEnginePage, QWebEngineSettings,
)
from PyQt5.QtWebChannel import QWebChannel

import markdown

from .links import classify_navigation_url, local_path_from_navigation, _fix_local_paths
from .math_ext import KATEX_CSS, KATEX_DIR, KATEX_JS, MathExtension, render_function_js
from .srcmap import tag_top_blocks


# 预览页基础 HTML：样式 + JS→Python 桥 + 外部协议链接拦截
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!--mdpad-katex-head-->
    <style>
        /* GitHub风格的Markdown样式 */
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            font-size: 16px;
            line-height: 1.6;
            color: #24292e;
            background-color: #fff;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }

        /* 标题 */
        h1, h2, h3, h4, h5, h6 {
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
            padding-bottom: 0.3em;
            border-bottom: 1px solid #eaecef;
        }

        h1 { font-size: 2em; }
        h2 { font-size: 1.5em; }
        h3 { font-size: 1.25em; }
        h4 { font-size: 1em; }
        h5 { font-size: 0.875em; }
        h6 { font-size: 0.85em; color: #6a737d; }

        /* 段落和文本 */
        p {
            margin-top: 0;
            margin-bottom: 16px;
        }

        /* 列表 */
        ul, ol {
            padding-left: 2em;
            margin-top: 0;
            margin-bottom: 16px;
        }

        li + li {
            margin-top: 0.25em;
        }

        /* 代码 */
        code {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
            font-size: 85%;
            padding: 0.2em 0.4em;
            margin: 0;
            background-color: rgba(27,31,35,0.05);
            border-radius: 3px;
        }

        pre {
            background-color: #f6f8fa;
            border-radius: 3px;
            padding: 16px;
            overflow: auto;
            line-height: 1.45;
        }

        pre code {
            background-color: transparent;
            padding: 0;
            border-radius: 0;
        }

        /* 引用 */
        blockquote {
            padding: 0 1em;
            color: #6a737d;
            border-left: 0.25em solid #dfe2e5;
            margin: 0 0 16px 0;
        }

        blockquote > :first-child {
            margin-top: 0;
        }

        blockquote > :last-child {
            margin-bottom: 0;
        }

        /* 表格 */
        table {
            border-spacing: 0;
            border-collapse: collapse;
            margin-bottom: 16px;
            width: 100%;
        }

        th, td {
            padding: 6px 13px;
            border: 1px solid #dfe2e5;
        }

        th {
            font-weight: 600;
            background-color: #f6f8fa;
        }

        tr:nth-child(2n) {
            background-color: #f6f8fa;
        }

        /* 链接 */
        a {
            color: #0366d6;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        /* 图片 */
        img {
            max-width: 100%;
            box-sizing: initial;
            background-color: #fff;
            border-style: none;
        }

        /* 水平线 */
        hr {
            height: 0.25em;
            padding: 0;
            margin: 24px 0;
            background-color: #e1e4e8;
            border: 0;
        }

        /* 任务列表 */
        .task-list-item {
            list-style-type: none;
        }

        .task-list-item-checkbox {
            margin: 0 0.2em 0.25em -1.6em;
            vertical-align: middle;
        }

        /* 换行标签样式 */
        br {
            display: block;
            content: "";
            margin-top: 0.5em;
        }

        /* 代码高亮 */
        .codehilite .hll { background-color: #ffffcc }
        .codehilite  { background: #f8f8f8; }
        .codehilite .c { color: #408080; font-style: italic } /* Comment */
        .codehilite .err { border: 1px solid #FF0000 } /* Error */
        .codehilite .k { color: #008000; font-weight: bold } /* Keyword */
        .codehilite .o { color: #666666 } /* Operator */
        .codehilite .ch { color: #408080; font-style: italic } /* Comment.Hashbang */
        .codehilite .cm { color: #408080; font-style: italic } /* Comment.Multiline */
        .codehilite .cp { color: #BC7A00 } /* Comment.Preproc */
        .codehilite .cpf { color: #408080; font-style: italic } /* Comment.PreprocFile */
        .codehilite .c1 { color: #408080; font-style: italic } /* Comment.Single */
        .codehilite .cs { color: #408080; font-style: italic } /* Comment.Single */
        .codehilite .gd { color: #A00000 } /* Generic.Deleted */
        .codehilite .ge { font-style: italic } /* Generic.Emph */
        .codehilite .gr { color: #FF0000 } /* Generic.Error */
        .codehilite .gh { color: #000080; font-weight: bold } /* Generic.Heading */
        .codehilite .gi { color: #00A000 } /* Generic.Inserted */
        .codehilite .go { color: #888888 } /* Generic.Output */
        .codehilite .gp { color: #000080; font-weight: bold } /* Generic.Prompt */
        .codehilite .gs { font-weight: bold } /* Generic.Strong */
        .codehilite .gu { color: #800080; font-weight: bold } /* Generic.Subheading */
        .codehilite .gt { color: #0044DD } /* Generic.Traceback */
        .codehilite .kc { color: #008000; font-weight: bold } /* Keyword.Constant */
        .codehilite .kd { color: #008000; font-weight: bold } /* Keyword.Declaration */
        .codehilite .kn { color: #008000; font-weight: bold } /* Keyword.Namespace */
        .codehilite .kp { color: #008000 } /* Keyword.Pseudo */
        .codehilite .kr { color: #008000; font-weight: bold } /* Keyword.Reserved */
        .codehilite .kt { color: #B00040 } /* Keyword.Type */
        .codehilite .m { color: #666666 } /* Literal.Number */
        .codehilite .s { color: #BA2121 } /* Literal.String */
        .codehilite .na { color: #7D9029 } /* Name.Attribute */
        .codehilite .nb { color: #008000 } /* Name.Builtin */
        .codehilite .nc { color: #0000FF; font-weight: bold } /* Name.Class */
        .codehilite .no { color: #880000 } /* Name.Constant */
        .codehilite .nd { color: #AA22FF } /* Name.Decorator */
        .codehilite .ni { color: #999999; font-weight: bold } /* Name.Entity */
        .codehilite .ne { color: #D2413A; font-weight: bold } /* Name.Exception */
        .codehilite .nf { color: #0000FF } /* Name.Function */
        .codehilite .nl { color: #A0A000 } /* Name.Label */
        .codehilite .nn { color: #0000FF; font-weight: bold } /* Name.Namespace */
        .codehilite .nt { color: #008000; font-weight: bold } /* Name.Tag */
        .codehilite .nv { color: #19177C } /* Name.Variable */
        .codehilite .ow { color: #AA22FF; font-weight: bold } /* Operator.Word */
        .codehilite .w { color: #bbbbbb } /* Text.Whitespace */
        .codehilite .mb { color: #666666 } /* Literal.Number.Bin */
        .codehilite .mf { color: #666666 } /* Literal.Number.Float */
        .codehilite .mh { color: #666666 } /* Literal.Number.Hex */
        .codehilite .mi { color: #666666 } /* Literal.Number.Integer */
        .codehilite .mo { color: #666666 } /* Literal.Number.Oct */
        .codehilite .sa { color: #BA2121 } /* Literal.String.Affix */
        .codehilite .sb { color: #BA2121 } /* Literal.String.Backtick */
        .codehilite .sc { color: #BA2121 } /* Literal.String.Char */
        .codehilite .dl { color: #BA2121 } /* Literal.String.Delimiter */
        .codehilite .sd { color: #BA2121; font-style: italic } /* Literal.String.Doc */
        .codehilite .s2 { color: #BA2121 } /* Literal.String.Double */
        .codehilite .se { color: #BB6622; font-weight: bold } /* Literal.String.Escape */
        .codehilite .sh { color: #BA2121 } /* Literal.String.Heredoc */
        .codehilite .si { color: #BB6688; font-weight: bold } /* Literal.String.Interpol */
        .codehilite .sx { color: #008000 } /* Literal.String.Other */
        .codehilite .sr { color: #BB6688 } /* Literal.String.Regex */
        .codehilite .s1 { color: #BA2121 } /* Literal.String.Single */
        .codehilite .ss { color: #19177C } /* Literal.String.Symbol */
        .codehilite .bp { color: #008000 } /* Name.Builtin.Pseudo */
        .codehilite .fm { color: #0000FF } /* Name.Function.Magic */
        .codehilite .vc { color: #19177C } /* Name.Variable.Class */
        .codehilite .vg { color: #19177C } /* Name.Variable.Global */
        .codehilite .vi { color: #19177C } /* Name.Variable.Instance */
        .codehilite .vm { color: #19177C } /* Name.Variable.Magic */
        .codehilite .il { color: #666666 } /* Literal.Number.Integer.Long */

        /* 数学公式（KaTeX 渲染前的占位元素） */
        .mdpad-math {
            white-space: nowrap;
        }

        .mdpad-math-display {
            display: block;
            text-align: center;
            margin: 1em 0;
            overflow-x: auto;
            overflow-y: hidden;
        }

        .mdpad-math-display .katex-display {
            margin: 0;
        }

        /* 查找命中（分屏/预览模式下的预览侧高亮） */
        mark.mdpad-find {
            background: #fff3b0;
            color: inherit;
            padding: 0;
        }

        mark.mdpad-find.mdpad-find-active {
            background: #9ecbff;
        }
    </style>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        // 连接 JS→Python 桥
        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.mdpadBridge = channel.objects.bridge;
        });
        // 拦截 mailto: 等外部协议链接：Chromium 会在导航管线前吞掉它们，
        // acceptNavigationRequest 收不到，这里阻止页面内导航并交给 Python 打开。
        document.addEventListener('click', function (e) {
            var el = e.target;
            while (el && el.tagName !== 'A') { el = el.parentElement; }
            if (!el) return;
            var href = el.getAttribute('href') || '';
            var m = href.match(/^([a-zA-Z][a-zA-Z0-9+.\\-]*):/);
            if (!m) return;  // 相对路径/锚点：正常走导航拦截
            var scheme = m[1].toLowerCase();
            if (scheme === 'http' || scheme === 'https' || scheme === 'file' ||
                scheme === 'data' || scheme === 'about') return;  // 交给 acceptNavigationRequest
            e.preventDefault();
            if (window.mdpadBridge) { window.mdpadBridge.openExternal(href); }
        });
        /*mdpad-render-math*/

        // 查找命中高亮：把预览里所有命中包成 <mark>（当前命中蓝底），
        // 可选把当前命中滚到视野中间。公式渲染结果（.katex）与脚本/样式跳过，
        // 免得把 KaTeX 的排版结构拆坏。
        var mdpadHighlightState = null;

        function mdpadClearHighlight(root) {
            var marks = (root || document).querySelectorAll('mark.mdpad-find');
            for (var i = 0; i < marks.length; i++) {
                var mark = marks[i];
                var parent = mark.parentNode;
                if (!parent) { continue; }
                parent.replaceChild(document.createTextNode(mark.textContent), mark);
                parent.normalize();
            }
        }

        function mdpadHighlight(term, index, caseSensitive, scroll) {
            var root = document.getElementById('content');
            if (!root) { return; }
            mdpadClearHighlight(root);
            mdpadHighlightState = [term, index, caseSensitive, scroll];
            if (!term) { return; }
            var needle = caseSensitive ? term : term.toLowerCase();
            var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
                acceptNode: function (node) {
                    if (!node.data) { return NodeFilter.FILTER_REJECT; }
                    var p = node.parentNode;
                    while (p && p !== root) {
                        var name = p.nodeName.toLowerCase();
                        if (name === 'script' || name === 'style' || name === 'mark') {
                            return NodeFilter.FILTER_REJECT;
                        }
                        if (p.classList && p.classList.contains('katex')) {
                            return NodeFilter.FILTER_REJECT;
                        }
                        p = p.parentNode;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            });
            var nodes = [];
            var node;
            while ((node = walker.nextNode())) { nodes.push(node); }
            var marks = [];
            for (var i = 0; i < nodes.length; i++) {
                var text = nodes[i].data;
                var hay = caseSensitive ? text : text.toLowerCase();
                var at = hay.indexOf(needle);
                if (at < 0) { continue; }
                var frag = document.createDocumentFragment();
                var cursor = 0;
                while (at >= 0) {
                    if (at > cursor) { frag.appendChild(document.createTextNode(text.slice(cursor, at))); }
                    var mark = document.createElement('mark');
                    mark.className = 'mdpad-find';
                    mark.textContent = text.slice(at, at + term.length);
                    frag.appendChild(mark);
                    marks.push(mark);
                    cursor = at + term.length;
                    at = hay.indexOf(needle, cursor);
                }
                if (cursor < text.length) { frag.appendChild(document.createTextNode(text.slice(cursor))); }
                nodes[i].parentNode.replaceChild(frag, nodes[i]);
            }
            if (!marks.length) { return; }
            var active = marks[Math.min(Math.max(index, 0), marks.length - 1)];
            active.className = 'mdpad-find mdpad-find-active';
            if (scroll) {
                var box = active.getBoundingClientRect();
                var target = window.scrollY + box.top - (window.innerHeight / 2) + (box.height / 2);
                mdpadScrollTo(Math.max(0, target));
            }
        }

        // 内容重建（每次更新都是整块 innerHTML 替换）后重新包一遍，但不抢滚动位置
        function mdpadReapplyHighlight() {
            if (!mdpadHighlightState) { return; }
            mdpadHighlight(mdpadHighlightState[0], mdpadHighlightState[1],
                           mdpadHighlightState[2], false);
        }

        // 跟随光标滚动：把光标所在源码行对应的块钉在可见区底边。
        // 语义与 VIMD 一致——预览被推到最底下时才跟随；用户自己滚开（不在底部）即停跟，
        // 滚回底部（滚轮/End）自动恢复。标记（<!--mdpad-src:N-->）在内容里是注释节点，
        // 注释没有布局盒，位置靠它的兄弟节点量（见 mdpadMarkerY）。
        var mdpadFollowArmed = true;
        var mdpadSelfScroll = false;

        // 程序自己滚（跟随 / 更新内容后恢复位置）要先打标记，否则会被下面
        // 的 scroll 监听当成"用户滚开"而误停跟；标记用定时器清，避免没有滚动
        // 事件时把下一次真实滚动吞掉。
        function mdpadScrollTo(y) {
            mdpadSelfScroll = true;
            window.scrollTo(0, y);
            setTimeout(function () { mdpadSelfScroll = false; }, 120);
        }

        window.addEventListener('scroll', function () {
            if (mdpadSelfScroll) { return; }
            mdpadFollowArmed =
                (window.scrollY + window.innerHeight) >= (document.body.scrollHeight - 4);
        });

        function mdpadFollowCursor(line) {
            var root = document.getElementById('content');
            if (!root) { return; }
            if (!mdpadFollowArmed) { return; }
            var PREFIX = 'mdpad-src:';
            var walker = document.createTreeWalker(root, NodeFilter.SHOW_COMMENT, null);
            var y = null;
            var node;
            while ((node = walker.nextNode())) {
                var data = node.data || '';
                if (data.indexOf(PREFIX) !== 0) { continue; }
                var n = parseInt(data.slice(PREFIX.length), 10);
                if (isNaN(n) || n > line) { continue; }
                var marker = mdpadMarkerY(node);
                if (marker !== null) { y = marker; }
            }
            if (y === null) { return; }
            var viewH = window.innerHeight;
            if (y > window.scrollY + viewH - 40) {
                mdpadScrollTo(Math.max(0, y - viewH + 60));
            }
        }

        // 注释节点没有布局盒（Range 也量不到位置），靠它的下一个兄弟节点定位；
        // 没有下一个兄弟（块在文档末尾）时退到上一个兄弟的底边。
        function mdpadMarkerY(node) {
            var sib = node.nextSibling;
            while (sib && sib.nodeType === 3 && !sib.data.trim()) { sib = sib.nextSibling; }
            if (sib) {
                var range = document.createRange();
                range.setStartBefore(sib);
                range.setEndAfter(sib);
                var box = range.getBoundingClientRect();
                if (box.height || box.width) { return window.scrollY + box.top; }
                if (sib.nodeType === 1) {
                    var rect = sib.getBoundingClientRect();
                    if (rect.height || rect.width) { return window.scrollY + rect.top; }
                }
            }
            var prev = node.previousSibling;
            while (prev && prev.nodeType === 3 && !prev.data.trim()) { prev = prev.previousSibling; }
            if (prev && prev.nodeType === 1) {
                var prevRect = prev.getBoundingClientRect();
                if (prevRect.height || prevRect.width) { return window.scrollY + prevRect.bottom; }
            }
            return null;
        }
    </script>
</head>
<body>
    <div id="content"></div>
</body>
</html>
"""

# KaTeX 资产：以 file:// URI 直接引用（预览页的 base_url 是本地目录，
# LocalContentCanAccessFileUrls 已开）。资产缺失时公式退回原文显示。
if KATEX_CSS.is_file() and KATEX_JS.is_file():
    _KATEX_HEAD_HTML = (
        f'    <link rel="stylesheet" href="{KATEX_CSS.as_uri()}">\n'
        f'    <script src="{KATEX_JS.as_uri()}"></script>\n'
    )
else:  # pragma: no cover - 随仓库分发，缺失只可能是打包漏了资产
    _KATEX_HEAD_HTML = '    <!-- KaTeX 资产缺失：公式按原文显示 -->\n'

BASE_HTML = BASE_HTML.replace('    <!--mdpad-katex-head-->', _KATEX_HEAD_HTML)
BASE_HTML = BASE_HTML.replace('        /*mdpad-render-math*/', render_function_js())


class _ExternalLinkBridge(QObject):
    """JS→Python 桥：把预览页中 Chromium 在导航管线前就拦截的外部协议链接（mailto: 等）交给 Python 打开"""

    @pyqtSlot(str)
    def openExternal(self, url):
        webbrowser.open(url)


class PreviewWebEnginePage(QWebEnginePage):
    """自定义 WebEnginePage：拦截预览中的链接跳转。

    本地文件链接 → 系统默认程序打开；
    网址链接 → 默认浏览器打开（不会在预览框内导航）；
    锚点与预览自身内容 → 页面内放行。
    """

    def acceptNavigationRequest(self, url, _type, is_main_frame):
        url_str = url.toString()
        action = classify_navigation_url(url_str, self.url().toString())
        if action in ("preview", "anchor"):
            return True
        if action == "file":
            path = local_path_from_navigation(url_str)
            if path:
                try:
                    os.startfile(path)
                except OSError as e:
                    preview = self.parent()
                    editor = getattr(preview, '_parent', None)
                    if editor is not None and hasattr(editor, 'status_bar'):
                        editor.status_bar.showMessage(f"无法打开文件: {path} — {e}", 5000)
            return False
        # 网址及其他链接：交给系统默认浏览器
        webbrowser.open(url_str)
        return False


class MarkdownPreview(QWebEngineView):
    """Markdown 预览组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        # 设置自定义页面来拦截外部链接
        self.setPage(PreviewWebEnginePage(self))
        # JS→Python 桥：处理 mailto: 等外部协议链接（Chromium 在导航前拦截，acceptNavigationRequest 收不到）
        self._bridge = _ExternalLinkBridge(self)
        self._channel = QWebChannel(self.page())
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)
        # 允许预览页加载本地图片（file:///...）和远程图片（http/https）
        settings = self.page().settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        # 初始化时加载一个基本的HTML框架，包含样式
        self._is_initialized = False
        self._pending_update = None
        self._current_markdown = ""
        self._base_dir = None  # 当前预览的相对路径基准目录（当前 Markdown 文件所在目录）
        self._base_html = BASE_HTML
        # 查找命中高亮状态：内容重建后据此重包（term, index, case_sensitive）
        self._highlight_state = None

        # 连接加载完成信号
        self.loadFinished.connect(self._on_load_finished)
        self._scroll_position = 0

    def _on_load_finished(self, ok):
        """页面加载完成后，恢复滚动位置并处理待更新"""
        if ok:
            # 标记为已初始化
            self._is_initialized = True

            # 恢复滚动位置
            if self._scroll_position > 0:
                self.page().runJavaScript(f"mdpadScrollTo(0, {self._scroll_position});")

            # 如果有待更新的内容，现在更新
            if self._pending_update is not None:
                self._update_content_with_js(self._pending_update)
                self._pending_update = None
            if self._highlight_state:
                self.page().runJavaScript("mdpadReapplyHighlight();")

    def _save_scroll_position(self, position):
        """JavaScript回调函数，用于保存滚动位置"""
        if position is not None:
            self._scroll_position = position

    def _update_content_with_js(self, html_content):
        """通过JavaScript更新内容，而不是重新加载整个页面"""
        # 先保存当前滚动位置
        self.page().runJavaScript("window.scrollY;", self._save_scroll_position)

        # 安全地转义HTML内容中的特殊字符
        escaped_content = json.dumps(html_content)

        # 通过JavaScript更新内容
        js_code = f"""
        (function() {{
            try {{
                var contentDiv = document.getElementById('content');
                if (contentDiv) {{
                    // 先获取当前的滚动位置
                    var scrollTop = window.scrollY;

                    // 更新内容
                    contentDiv.innerHTML = {escaped_content};

                    // 渲染数学公式（KaTeX）
                    if (window.mdpadRenderMath) {{ window.mdpadRenderMath(contentDiv); }}

                    // 恢复滚动位置（走 mdpadScrollTo：自己滚的，不该被当成用户滚开）
                    mdpadScrollTo(scrollTop);
                }}
            }} catch (e) {{
                console.error('更新内容时出错:', e);
            }}
        }})();
        """

        self.page().runJavaScript(js_code)
        if self._highlight_state:
            # 内容整块重建后 <mark> 也没了，重包一遍（不抢滚动位置）
            self.page().runJavaScript("mdpadReapplyHighlight();")

    def highlight(self, term, index=0, case_sensitive=False, scroll=True):
        """在预览里高亮所有命中，当前命中（index，0 起）蓝底，可选滚到视野中间。

        term 为空即清除高亮。高亮会在预览内容重建后自动重包（见 _update_content_with_js）。
        """
        self._highlight_state = (term or "", int(index), bool(case_sensitive)) if term else None
        if not self._is_initialized:
            return
        payload = json.dumps([term or "", int(index), bool(case_sensitive), bool(scroll)])
        self.page().runJavaScript(f"mdpadHighlight.apply(null, {payload});")

    def follow_cursor(self, source_line):
        """把光标所在源码行对应的块推到预览可见区（只向下推进，绝不回滚）。

        语义与 VIMD 一致：光标行的块掉到视野下方才滚；用户自己往上翻即停止跟随，
        重新写到底部又会自然跟上。
        """
        if not self._is_initialized:
            return
        self.page().runJavaScript(f"mdpadFollowCursor({int(source_line)});")

    def update_preview(self, markdown_text):
        """更新预览内容"""
        self._current_markdown = markdown_text
        try:
            # 使用多个扩展
            extensions = [
                'markdown.extensions.extra',
                'markdown.extensions.codehilite',
                'markdown.extensions.toc',
                'markdown.extensions.tables',
                'markdown.extensions.fenced_code',
                'markdown.extensions.nl2br',
                MathExtension(),
            ]

            # 顶层块先打上源码行号标记（跟随光标用；标记是 HTML 注释，不影响显示）
            html_content = markdown.markdown(tag_top_blocks(markdown_text), extensions=extensions)
            # 修正本地路径引用（Windows 盘符、反斜杠）
            html_content = _fix_local_paths(html_content)

            # 以当前 Markdown 文件所在目录作为相对路径（图片/链接）的基准
            editor = getattr(self, '_parent', None)
            base_dir = os.path.dirname(editor.current_file) if editor and editor.current_file else None

            # 基准目录变化或页面未初始化时，重新加载页面框架
            if not self._is_initialized or base_dir != self._base_dir:
                self._base_dir = base_dir
                self._is_initialized = False
                self._pending_update = html_content
                self._scroll_position = 0  # 打开新文档从顶部开始
                base_url = QUrl.fromLocalFile(
                    base_dir + os.sep if base_dir else str(KATEX_DIR) + os.sep
                )
                # 加载基本HTML页面，并指定基准目录
                self.setHtml(self._base_html, base_url)
            else:
                # 直接通过JavaScript更新内容
                self._update_content_with_js(html_content)

        except Exception as e:
            # 如果发生错误，回退到完整HTML显示错误
            error_html = f"<h1>预览错误</h1><p>{html_module.escape(str(e))}</p>"
            if not self._is_initialized:
                self.setHtml(f"<html><body>{error_html}</body></html>")
            else:
                self._update_content_with_js(error_html)
