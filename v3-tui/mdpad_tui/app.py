"""MDPad TUI 应用主体 — 三视图、状态栏、文件生命周期、快捷键调度。

架构:
    Editor (TextArea) ──Changed──> 防抖 ──> Preview (Markdown)
    纯逻辑复用 v2-fluent/mdpad/{io,links}.py (零 Qt 依赖)

视图模式 (持久化到 %APPDATA%/MDPad/tui_settings.json):
    F2 编辑 · F3 预览 · F4 分屏
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, Static

from mdpad.io import FileGuard, read_text_file, write_text_file

from .dialogs import HelpScreen, PathPrompt, QuitConfirm
from .editor import Editor
from .findbar import FindBar
from .preview import Preview

MODES = ("edit", "preview", "split")
PREVIEW_DEBOUNCE = 0.2  # 秒; 与 GUI 版 v1.3.0 同思路: 连续输入合并渲染


def _settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "MDPad" / "tui_settings.json"


class MDPadApp(App):
    """MDPad 终端版应用。"""

    TITLE = "MDPad TUI"
    CSS = """
    #body { height: 1fr; }
    #body > Editor, #body > Preview { width: 100%; }
    #body.m-split > Editor, #body.m-split > Preview { width: 50%; }
    FindBar { display: none; height: 1; background: $panel; }
    FindBar > Input { width: 1fr; border: none; background: $panel; }
    FindBar > Static { width: auto; padding: 0 1; color: $text-muted; }
    #status { height: 1; background: $panel; color: $text-muted; padding: 0 1; }
    HelpScreen, PathPrompt, QuitConfirm { align: center middle; }
    #help-box, #prompt-box, #quit-box {
        width: auto; height: auto; max-width: 70%;
        padding: 1 2; background: $surface; border: thick $accent;
    }
    #help-hint, #quit-title { margin-top: 1; }
    #quit-buttons { margin-top: 1; }
    #quit-buttons Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("ctrl+s", "save", "保存"),
        Binding("ctrl+shift+s", "save_as", "另存为"),
        Binding("ctrl+o", "open", "打开"),
        Binding("ctrl+f", "find", "查找"),
        Binding("ctrl+g", "find_next", "下一个"),
        Binding("ctrl+shift+g", "find_prev", "上一个"),
        Binding("f1", "show_help", "帮助"),
        Binding("f2", "mode_edit", "编辑"),
        Binding("f3", "mode_preview", "预览"),
        Binding("f4", "mode_split", "分屏"),
        Binding("ctrl+q", "request_quit", "退出"),
    ]

    def __init__(self, path: str | None = None) -> None:
        super().__init__()
        self.path_arg = path
        self.file_path: Path | None = None
        self.file_guard = FileGuard()
        self._saved_text = ""
        self._mode = "edit"
        self._preview_gen = 0  # 防抖代数计数

    # ── 组装 ────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield Editor(id="editor")
            yield Preview(id="preview")
        yield FindBar(id="findbar")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        mode = self._load_mode()
        if self.path_arg:
            p = Path(self.path_arg)
            if p.exists():
                self._open_file(p)
            else:
                # 新文件: 记住路径, 保存时创建
                self.file_path = p
                self.query_one(Preview).doc_dir = p.parent
        self._apply_mode(mode)
        self.refresh_status()

    # ── 设置持久化 ──────────────────────────────────────────
    def _load_mode(self) -> str:
        try:
            data = json.loads(_settings_path().read_text(encoding="utf-8"))
            mode = data.get("mode")
            if mode in MODES:
                return mode
        except (OSError, ValueError):
            pass
        return "edit"

    def _store_mode(self) -> None:
        try:
            path = _settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"mode": self._mode}), encoding="utf-8"
            )
        except OSError:
            pass  # 设置写不进去不影响编辑

    # ── 视图模式 ────────────────────────────────────────────
    def _apply_mode(self, mode: str) -> None:
        self._mode = mode
        body = self.query_one("#body", Horizontal)
        for m in MODES:
            body.remove_class("m-" + m)
        body.add_class("m-" + mode)
        editor, preview = self.query_one(Editor), self.query_one(Preview)
        editor.display = mode in ("edit", "split")
        preview.display = mode in ("preview", "split")
        if mode == "preview":
            preview.focus()
        else:
            editor.focus()
        self._store_mode()
        self._render_preview_now()  # 切到预览立即刷新, 不等防抖
        self.refresh_status()

    def action_mode_edit(self) -> None:
        self._apply_mode("edit")

    def action_mode_preview(self) -> None:
        self._apply_mode("preview")

    def action_mode_split(self) -> None:
        self._apply_mode("split")

    # ── 预览防抖 ────────────────────────────────────────────
    def on_text_area_changed(self, event) -> None:
        del event
        self._preview_gen += 1
        gen = self._preview_gen
        self.set_timer(PREVIEW_DEBOUNCE, lambda: self._render_if(gen))
        self.refresh_status()

    def on_text_area_selection_changed(self, event) -> None:
        del event
        self.refresh_status()

    def _render_if(self, gen: int) -> None:
        if gen == self._preview_gen:
            self._render_preview_now()

    def _render_preview_now(self) -> None:
        self.query_one(Preview).update(self.query_one(Editor).text)

    # ── 状态栏 ──────────────────────────────────────────────
    def refresh_status(self) -> None:
        editor = self.query_one(Editor)
        row, col = editor.cursor_location
        name = self.file_path.name if self.file_path else "未命名"
        dirty = "● " if editor.text != self._saved_text else ""
        self.query_one("#status", Static).update(
            f" {dirty}{name}  ({self._mode})  {row + 1}:{col + 1}"
        )

    # ── 文件操作 ────────────────────────────────────────────
    def _open_file(self, path: Path) -> None:
        content = read_text_file(path)
        self.file_path = path
        self.file_guard.acquire(str(path))
        editor = self.query_one(Editor)
        editor.text = content
        self._saved_text = content
        preview = self.query_one(Preview)
        preview.doc_dir = path.parent
        preview.update(content)
        self.refresh_status()
        self.notify(f"已打开 {path.name}")

    def action_open(self) -> None:
        initial = str(self.file_path.parent if self.file_path else Path.cwd())
        self.push_screen(PathPrompt("打开文件", initial), self._on_open_path)

    def _on_open_path(self, value: str | None) -> None:
        if not value:
            return
        path = Path(value)
        if path.is_dir():
            path = path / "未命名.md"
        if path.is_file():
            self._open_file(path)
        else:
            self.notify(f"文件不存在: {path}", severity="warning")

    def action_save(self) -> None:
        if self.file_path is None:
            self.action_save_as()
            return
        text = self.query_one(Editor).text
        write_text_file(self.file_path, text)
        self._saved_text = text
        self.refresh_status()
        self.notify(f"已保存 {self.file_path.name}")

    def action_save_as(self) -> None:
        initial = self.file_path.name if self.file_path else "未命名.md"
        self.push_screen(PathPrompt("另存为", initial), self._on_save_as_path)

    def _on_save_as_path(self, value: str | None) -> None:
        if not value:
            return
        path = Path(value)
        if not path.suffix:
            path = path.with_suffix(".md")
        self.file_path = path
        self.query_one(Preview).doc_dir = path.parent
        self.file_guard.acquire(str(path))
        self.action_save()

    # ── 查找替换 ────────────────────────────────────────────
    def action_find(self) -> None:
        bar = self.query_one(FindBar)
        bar.display = True
        editor = self.query_one(Editor)
        selection = editor.selected_text
        find_input = bar.query_one("#find-input", Input)
        if selection and "\n" not in selection:
            find_input.value = selection
        find_input.focus()
        bar.refresh_count(editor)

    def action_find_next(self) -> None:
        self.query_one(FindBar).find_next(self.query_one(Editor))

    def action_find_prev(self) -> None:
        self.query_one(FindBar).find_next(
            self.query_one(Editor), backward=True
        )

    # ── 帮助与退出 ──────────────────────────────────────────
    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_request_quit(self) -> None:
        if self.query_one(Editor).text != self._saved_text:
            self.push_screen(QuitConfirm(), self._on_quit_choice)
        else:
            self.exit()

    def _on_quit_choice(self, choice: str) -> None:
        if choice == "save":
            if self.file_path is not None:
                self.action_save()
                self.exit()
            else:
                # 未命名文档: 先另存为, 存完自动退出
                self.push_screen(
                    PathPrompt("另存为", "未命名.md"), self._save_then_quit
                )
        elif choice == "discard":
            self.exit()

    def _save_then_quit(self, value: str | None) -> None:
        if not value:
            return
        path = Path(value)
        if not path.suffix:
            path = path.with_suffix(".md")
        self.file_path = path
        self.file_guard.acquire(str(path))
        self.action_save()
        self.exit()
