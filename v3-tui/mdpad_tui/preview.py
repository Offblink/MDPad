"""预览区 — Markdown 渲染 + 链接/图片点击分发。

复用 mdpad.links 的分类与路径解析纯函数，语义与 GUI 版一致：

- 网址 (http/https/mailto)     → 默认浏览器
- 本地文件 (盘符/file:/相对路径) → 系统默认程序打开（图片同理：
  Textual 的 image 节点被当作 link(src) 发 LinkClicked, 走同一条分发）
- 页内锚点 (#xxx)              → 暂不跳转，提示

Markdown 构造必须传 open_links=False：Markdown 自身默认会把任何 href
丢给 app.open_url (_markdown.py:997,1139)，会绕过这里的本地分流。
"""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from textual.widgets import Markdown

from mdpad.links import classify_navigation_url, local_path_from_navigation


def open_href(href: str, doc_dir: Path, notify) -> None:
    """把一个 href 分流到 浏览器 / 系统默认程序；失败时 notify 提示。"""
    if href.startswith("#"):
        # classify 的 anchor 判定需要 current_doc_url, 这里直接前置
        notify("页内锚点暂不支持跳转")
        return
    kind = classify_navigation_url(href)
    if kind == "anchor":
        notify("页内锚点暂不支持跳转")
        return
    if kind == "file":
        path = local_path_from_navigation(href)
        target = Path(path) if path else doc_dir / href
    elif not urlparse(href).scheme:
        # 相对路径 (classify 归为 web, 这里按本地文件处理)
        target = doc_dir / href
    else:
        webbrowser.open(href)
        return
    try:
        os.startfile(str(target))
    except OSError:
        notify(f"打不开: {target}")


class Preview(Markdown):
    """实时预览面板。"""

    def __init__(self, **kwargs) -> None:
        super().__init__(open_links=False, **kwargs)
        self.can_focus = True  # 预览模式下接管键盘焦点
        self.doc_dir: Path = Path.cwd()

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        event.stop()
        open_href(event.href, self.doc_dir, self.app.notify)
