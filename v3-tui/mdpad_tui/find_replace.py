"""查找与替换 — 居中弹窗 (ModalScreen) + 可独立调用的查找函数。

弹窗内键位: Enter(查找框)=下一个 · Enter(替换框)=全部替换 ·
F6=区分大小写 · Esc=关闭。查询状态存在 app.find_state —
关掉弹窗后 Ctrl+G / Ctrl+Shift+G 仍按最后的查询继续跳转。

与 GUI 版语义对齐 (下一个/上一个循环、实时计数); 替换逐处调用
TextArea.replace, 每处是独立 undo 批次 (已知简化)。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.document._document import Selection
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from .editor import Editor


@dataclass
class FindState:
    """跨弹窗存续的查找状态 (由 app 持有)。"""

    query: str = ""
    replace: str = ""
    case: bool = False


def _offset_of(text: str, row: int, col: int) -> int:
    """(行, 列) → 全文偏移。"""
    offset = 0
    for i, line in enumerate(text.split("\n")):
        if i == row:
            return offset + col
        offset += len(line) + 1
    return offset


def _location_of(text: str, offset: int) -> tuple[int, int]:
    """全文偏移 → (行, 列)。"""
    row = 0
    col = offset
    for line in text.split("\n"):
        if col <= len(line):
            return row, col
        col -= len(line) + 1
        row += 1
    return row, col


def _matches(text: str, state: FindState) -> list[tuple[int, int]]:
    """state.query 在 text 中全部匹配的 (起, 止) 偏移列表。"""
    if not state.query:
        return []
    flags = 0 if state.case else re.IGNORECASE
    return [
        m.span() for m in re.finditer(re.escape(state.query), text, flags)
    ]


def find_next(editor: Editor, state: FindState, backward: bool = False,
              notify=None) -> None:
    """选中下一个/上一个匹配, 到头循环。"""
    matches = _matches(editor.text, state)
    if not matches:
        if state.query and notify:
            notify("找不到: " + state.query)
        return
    cursor = _offset_of(editor.text, *editor.cursor_location)
    if backward:
        before = [m for m in matches if m[1] <= cursor]
        start, end = before[-1] if before else matches[-1]
    else:
        after = [m for m in matches if m[0] >= cursor]
        start, end = after[0] if after else matches[0]
    text = editor.text
    editor.selection = Selection(
        _location_of(text, start), _location_of(text, end)
    )
    editor.scroll_cursor_visible()


def replace_all(editor: Editor, state: FindState, notify=None) -> None:
    """全部替换 (从后往前, 前面匹配的偏移不受影响)。"""
    matches = _matches(editor.text, state)
    if not matches:
        if notify:
            notify("没有可替换的匹配")
        return
    text = editor.text
    for start, end in reversed(matches):
        editor.replace(
            state.replace,
            _location_of(text, start),
            _location_of(text, end),
        )
    if notify:
        notify(f"已替换 {len(matches)} 处")


class FindScreen(ModalScreen[None]):
    """居中的查找/替换弹窗。"""

    CSS = """
    #find-box {
        width: 64; height: auto; max-width: 90%; max-height: 90%;
        padding: 1 2; background: $surface; border: thick $accent;
    }
    #find-box Input { width: 100%; margin-top: 1; }
    #find-count { margin-top: 1; color: $text-muted; }
    #find-hint { margin-top: 1; color: $text-muted; }
    """
    BINDINGS = [
        Binding("f6", "toggle_case", "区分大小写"),
        Binding("escape", "close", "关闭"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="find-box"):
            yield Static("[bold]查找与替换[/bold]", id="find-title")
            yield Input(placeholder="查找 (Enter 下一个)", id="find-input")
            yield Input(placeholder="替换 (Enter 全部替换)", id="replace-input")
            yield Static("", id="find-count")
            yield Static(
                "[dim]Enter 下一个 · 替换框 Enter 全部替换 · "
                "F6 大小写 · Esc 关闭[/dim]",
                id="find-hint",
            )

    @property
    def state(self) -> FindState:
        return self.app.find_state

    @property
    def editor(self) -> Editor:
        return self.app.query_one(Editor)

    def on_mount(self) -> None:
        state = self.state
        find_input = self.query_one("#find-input", Input)
        replace_input = self.query_one("#replace-input", Input)
        find_input.value = state.query
        replace_input.value = state.replace
        # 有单行选区时用它做初始查询
        selection = self.editor.selected_text
        if selection and "\n" not in selection and not state.query:
            find_input.value = selection
            state.query = selection
        find_input.focus()
        self.refresh_count()

    def refresh_count(self) -> None:
        count = len(_matches(self.editor.text, self.state))
        label = f"{count} 处匹配" if self.state.query else ""
        if self.state.case and label:
            label += "（区分大小写）"
        self.query_one("#find-count", Static).update(label)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "find-input":
            self.state.query = event.value
        elif event.input.id == "replace-input":
            self.state.replace = event.value
        self.refresh_count()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "find-input":
            find_next(self.editor, self.state, notify=self.app.notify)
        elif event.input.id == "replace-input":
            replace_all(self.editor, self.state, notify=self.app.notify)

    def action_toggle_case(self) -> None:
        self.state.case = not self.state.case
        self.refresh_count()

    def action_close(self) -> None:
        self.dismiss(None)
