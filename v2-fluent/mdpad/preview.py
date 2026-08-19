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


# 预览页基础 HTML：样式 + JS→Python 桥 + 外部协议链接拦截
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
    </script>
</head>
<body>
    <div id="content"></div>
</body>
</html>
"""


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
                self.page().runJavaScript(f"window.scrollTo(0, {self._scroll_position});")

            # 如果有待更新的内容，现在更新
            if self._pending_update is not None:
                self._update_content_with_js(self._pending_update)
                self._pending_update = None

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

                    // 恢复滚动位置
                    window.scrollTo(0, scrollTop);
                }}
            }} catch (e) {{
                console.error('更新内容时出错:', e);
            }}
        }})();
        """

        self.page().runJavaScript(js_code)

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
            ]

            html_content = markdown.markdown(markdown_text, extensions=extensions)
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
                base_url = QUrl.fromLocalFile(base_dir + os.sep) if base_dir else QUrl()
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
