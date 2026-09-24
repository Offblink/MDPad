"""查找与替换底条。

操作 (与 GUI 版语义对齐, 键位适配终端):

- 输入查找词: 实时计数 (n 处匹配)
- Enter (查找框)     → 下一个
- Enter (替换框)     → 全部替换
- Ctrl+G / Ctrl+Shift+G (全局) → 下一个 / 上一个, 循环
- F6 → 区分大小写开关
- Esc → 收起

替换逐处调用 TextArea.replace: 每处是一个独立 undo 批次
(GUI 版全部替换一次性完成, 这是已知简化)。
"""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.document._document import Selection
from textual.widgets import Input, Static

from .editor import Editor


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


class FindBar(Horizontal):
    """底部查找/替换条 (默认隐藏, Ctrl+F 唤出)。"""

    BINDINGS = [
        Binding("f6", "toggle_case", "区分大小写"),
        Binding("escape", "hide", "关闭"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.case_sensitive = False

    def compose(self) -> ComposeResult:
        yield Input(placeholder="查找 (Enter 下一个)", id="find-input")
        yield Input(placeholder="替换 (Enter 全部替换)", id="replace-input")
        yield Static("", id="find-count")

    # ── 查找 ────────────────────────────────────────────────
    @property
    def query_text(self) -> str:
        return self.query_one("#find-input", Input).value

    def _matches(self, editor: Editor) -> list[tuple[int, int]]:
        """当前全部匹配的 (起, 止) 偏移列表。"""
        if not self.query_text:
            return []
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return [
            m.span()
            for m in re.finditer(re.escape(self.query_text), editor.text, flags)
        ]

    def refresh_count(self, editor: Editor) -> None:
        count = len(self._matches(editor))
        label = f"{count} 处匹配" if self.query_text else ""
        if self.case_sensitive and label:
            label += "（区分大小写）"
        self.query_one("#find-count", Static).update(label)

    def find_next(self, editor: Editor, backward: bool = False) -> None:
        matches = self._matches(editor)
        if not matches:
            if self.query_text:
                self.app.notify("找不到: " + self.query_text)
            return
        cursor = _offset_of(editor.text, *editor.cursor_location)
        if backward:
            before = [m for m in matches if m[1] <= cursor]
            start, end = before[-1] if before else matches[-1]
        else:
            after = [m for m in matches if m[0] >= cursor]
            start, end = after[0] if after else matches[0]
        self._select(editor, start, end)

    def _select(self, editor: Editor, start: int, end: int) -> None:
        text = editor.text
        editor.selection = Selection(
            _location_of(text, start), _location_of(text, end)
        )
        editor.scroll_cursor_visible()

    # ── 替换 ────────────────────────────────────────────────
    def replace_all(self, editor: Editor) -> None:
        replacement = self.query_one("#replace-input", Input).value
        matches = self._matches(editor)
        if not matches:
            self.app.notify("没有可替换的匹配")
            return
        text = editor.text
        # 从后往前替换, 前面匹配的偏移不受影响
        for start, end in reversed(matches):
            editor.replace(
                replacement,
                _location_of(text, start),
                _location_of(text, end),
            )
        self.refresh_count(editor)
        self.app.notify(f"已替换 {len(matches)} 处")

    def replace_current(self, editor: Editor) -> None:
        """替换当前选中项 (须恰好是一个匹配), 然后跳到下一个。"""
        matches = self._matches(editor)
        text = editor.text
        sel_start = _offset_of(text, *editor.selection.start)
        sel_end = _offset_of(text, *editor.selection.end)
        if (sel_start, sel_end) in matches:
            replacement = self.query_one("#replace-input", Input).value
            editor.replace(
                replacement, editor.selection.start, editor.selection.end
            )
            self.refresh_count(editor)
        self.find_next(editor)

    # ── 交互 ────────────────────────────────────────────────
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "find-input":
            self.refresh_count(self.app.query_one(Editor))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        editor = self.app.query_one(Editor)
        if event.input.id == "find-input":
            self.find_next(editor)
        elif event.input.id == "replace-input":
            self.replace_all(editor)

    def action_toggle_case(self) -> None:
        self.case_sensitive = not self.case_sensitive
        self.refresh_count(self.app.query_one(Editor))

    def action_hide(self) -> None:
        self.display = False
        self.app.query_one(Editor).focus()
