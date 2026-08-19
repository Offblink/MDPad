"""主窗口：Fluent 组件 + 文件操作编排。"""
import os
import threading

from PyQt5.QtCore import Qt, QSettings, QObject, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QDragEnterEvent, QDropEvent, QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QSplitter,
    QStatusBar, QFileDialog, QShortcut,
)
from qfluentwidgets import (
    FluentIcon, ToolButton, SegmentedWidget, InfoBar, InfoBarPosition,
    MessageBox, MessageBoxBase, BodyLabel, SubtitleLabel,
    PrimaryPushButton, PushButton, setTheme, Theme, StateToolTip,
)

from .preview import MarkdownPreview
from .dialogs import HelpDialog, _font_scale, _apply_font_scale
from . import io, ai_naming, __app_name__, __org_name__


class _AiWorker(QObject):
    """AI 命名后台任务：daemon 线程执行网络请求，完成后经信号回到主线程。

    使用 daemon 线程：窗口关闭时不会阻塞退出，请求随进程结束被中断（只读 API，无副作用）。
    """
    done = pyqtSignal(object, object)  # (name, error)

    def start(self, content):
        threading.Thread(target=self._run, args=(content,), daemon=True).start()

    def _run(self, content):
        name, error = ai_naming.generate_filename_with_ai(content)
        self.done.emit(name, error)


class SaveChangesDialog(MessageBoxBase):
    """三路保存确认：保存 / 不保存 / 取消。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.choice = "cancel"
        self.titleLabel = SubtitleLabel("保存更改")
        self.contentLabel = BodyLabel("文件已修改，是否保存更改？")
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)
        self.saveBtn = PrimaryPushButton("保存")
        self.discardBtn = PushButton("不保存")
        self.cancelBtn = PushButton("取消")
        self.saveBtn.clicked.connect(self._choose_save)
        self.discardBtn.clicked.connect(self._choose_discard)
        self.cancelBtn.clicked.connect(self._choose_cancel)
        self.buttonLayout.addWidget(self.saveBtn)
        self.buttonLayout.addWidget(self.discardBtn)
        self.buttonLayout.addWidget(self.cancelBtn)

        # MessageBoxBase 自带 OK/Cancel 默认按钮，隐藏掉，只保留三路选择
        self.buttonLayout.removeWidget(self.yesButton)
        self.buttonLayout.removeWidget(self.cancelButton)
        self.yesButton.hide()
        self.cancelButton.hide()

        # 字体随主窗口尺寸缩放；窗口尺寸由内容自适应（内容少时避免大面积空白）
        _apply_font_scale(self, _font_scale(parent))
        self.widget.setMinimumSize(360, 180)  # 小保底，内容多时自然撑大

    def _choose_save(self):
        self.choice = "save"
        self.accept()

    def _choose_discard(self):
        self.choice = "discard"
        self.accept()

    def _choose_cancel(self):
        self.choice = "cancel"
        self.reject()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.split_mode = True
        self.editing_mode = True
        self.settings = QSettings(__org_name__, __app_name__)
        # AI 命名异步状态
        self._ai_worker = _AiWorker(self)
        self._ai_worker.done.connect(self._on_ai_done)
        self._ai_busy = False
        self._ai_callback = None
        self._ai_tip = None
        # 启用拖放功能（编辑/预览组件自身不拦截）
        self.setAcceptDrops(True)
        self.init_ui()
        self.load_settings()

    # ---------- UI ----------

    def init_ui(self):
        self.setWindowTitle('MDPad - Markdown 编辑器')
        self.setGeometry(100, 100, 1200, 800)

        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.build_toolbar_area()
        main_layout.addWidget(self.toolbar_area)

        self.build_editor_area()
        main_layout.addWidget(self.editor_splitter, 1)

        self.build_status_bar()

        self.apply_theme()
        self.set_split_mode(True)

    def build_toolbar_area(self):
        """顶部工具栏：文件操作 + 视图模式切换（格式按钮、帮助按钮由后续切片加入）。"""
        self.toolbar_area = QWidget(self)
        bar = QHBoxLayout(self.toolbar_area)
        bar.setContentsMargins(12, 8, 12, 8)
        bar.setSpacing(6)

        # 文件操作
        self.new_btn = self._tool_button(FluentIcon.ADD, "新建 (Ctrl+N)", self.new_file)
        self.open_btn = self._tool_button(FluentIcon.FOLDER, "打开 (Ctrl+O)", self.open_file)
        self.save_btn = self._tool_button(FluentIcon.SAVE, "保存 (Ctrl+S)", self.save_file)
        self.save_as_btn = self._tool_button(FluentIcon.SAVE_AS, "另存为 (Ctrl+Shift+S)", self.save_file_as)
        self.export_btn = self._tool_button(FluentIcon.SHARE, "导出为 HTML", self.export_html)
        for btn in (self.new_btn, self.open_btn, self.save_btn, self.save_as_btn, self.export_btn):
            bar.addWidget(btn)

        bar.addSpacing(12)

        # 格式操作
        self.bold_btn = self._text_button("B", "加粗 (Ctrl+B)", lambda: self.insert_formatting("**", "**"))
        self.italic_btn = self._text_button("I", "斜体 (Ctrl+I)", lambda: self.insert_formatting("*", "*"))
        self.header_btn = self._text_button("H", "插入标题", self.insert_header)
        self.link_btn = self._tool_button(FluentIcon.LINK, "插入链接 (Ctrl+L)", self.insert_link)
        self.code_btn = self._tool_button(FluentIcon.CODE, "插入代码块 (Ctrl+K)", self.insert_code_block)
        for btn in (self.bold_btn, self.italic_btn, self.header_btn, self.link_btn, self.code_btn):
            bar.addWidget(btn)

        bar.addStretch(1)

        # 视图模式切换
        self.mode_seg = SegmentedWidget(self.toolbar_area)
        self.mode_seg.addItem("edit", "编辑", onClick=lambda: self.set_editing_mode(True))
        self.mode_seg.addItem("preview", "预览", onClick=lambda: self.set_editing_mode(False))
        self.mode_seg.addItem("split", "分屏", onClick=lambda: self.set_split_mode(True))
        self.mode_seg.setCurrentItem("split")
        bar.addWidget(self.mode_seg)

        bar.addSpacing(12)

        # 帮助
        self.help_btn = self._tool_button(FluentIcon.HELP, "帮助 (F1)", self.show_help)
        bar.addWidget(self.help_btn)

        # 快捷键
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_file)
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_file)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_file)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.save_file_as)
        QShortcut(QKeySequence("Ctrl+B"), self, lambda: self.insert_formatting("**", "**"))
        QShortcut(QKeySequence("Ctrl+I"), self, lambda: self.insert_formatting("*", "*"))
        QShortcut(QKeySequence("Ctrl+K"), self, self.insert_code_block)
        QShortcut(QKeySequence("Ctrl+L"), self, self.insert_link)
        QShortcut(QKeySequence("F2"), self, lambda: self.set_editing_mode(True))
        QShortcut(QKeySequence("F3"), self, lambda: self.set_editing_mode(False))
        QShortcut(QKeySequence("F4"), self, self.toggle_split_view)
        QShortcut(QKeySequence("F1"), self, self.show_help)

    def _text_button(self, text, tip, slot):
        btn = ToolButton(self.toolbar_area)
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setFixedSize(34, 34)
        btn.clicked.connect(slot)
        return btn

    def _tool_button(self, icon, tip, slot):
        btn = ToolButton(self.toolbar_area)
        btn.setIcon(icon)
        btn.setToolTip(tip)
        btn.setFixedSize(34, 34)
        btn.clicked.connect(slot)
        return btn

    def build_editor_area(self):
        self.editor_splitter = QSplitter(Qt.Horizontal)

        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Consolas", 11))
        self.text_edit.textChanged.connect(self.update_preview)
        self.text_edit.cursorPositionChanged.connect(self.update_cursor_position)
        # 编辑框自身不拦截拖放，交给父窗口处理
        self.text_edit.setAcceptDrops(False)

        self.preview = MarkdownPreview()
        self.preview._parent = self
        self.preview.setAcceptDrops(False)

        self.editor_splitter.addWidget(self.text_edit)
        self.editor_splitter.addWidget(self.preview)
        self.editor_splitter.setAcceptDrops(False)

    def build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.cursor_position_label = BodyLabel("行: 1, 列: 1")
        self.status_bar.addPermanentWidget(self.cursor_position_label)

    def apply_theme(self):
        """跟随系统明暗主题。"""
        setTheme(Theme.AUTO)

    def show_help(self):
        """弹出帮助窗口（F1 / 帮助按钮）。"""
        dialog = HelpDialog(self)
        dialog.exec()

    # ---------- 设置持久化与命令行 ----------

    def load_settings(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        split_sizes = self.settings.value("split_sizes")
        if split_sizes:
            self.editor_splitter.setSizes([int(size) for size in split_sizes])

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("split_sizes", self.editor_splitter.sizes())

    def open_path(self, file_path):
        """打开命令行/文件关联传入的路径（含非 Markdown 扩展名确认）。"""
        if not self.check_save_changes():
            return
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ('.md', '.markdown', '.txt'):
            box = MessageBox("打开文件", f'文件 "{os.path.basename(file_path)}" 不是标准的Markdown文件 (扩展名: {ext})。\n\n仍然要打开吗？', self)
            box.yesButton.setText("仍然打开")
            box.cancelButton.setText("取消")
            proceed = []
            box.yesSignal.connect(lambda: proceed.append(True))
            box.cancelSignal.connect(lambda: proceed.append(False))
            box.exec()
            if not proceed or not proceed[0]:
                return
        self.load_file(file_path)

    def closeEvent(self, event):
        if self.check_save_changes():
            self.save_settings()
            event.accept()
        else:
            event.ignore()

    def notify(self, level, title, content, duration=3000):
        """Fluent InfoBar 提示。level: success / info / warning / error"""
        getattr(InfoBar, level)(
            title, content,
            isClosable=True, duration=duration,
            position=InfoBarPosition.TOP_RIGHT, parent=self,
        )

    # ---------- 视图模式 ----------

    def set_split_mode(self, enabled):
        self.split_mode = enabled
        self.mode_seg.setCurrentItem("split" if enabled else ("edit" if self.editing_mode else "preview"))
        self.update_view_mode()

    def toggle_split_view(self):
        self.split_mode = not self.split_mode
        self.mode_seg.setCurrentItem("split" if self.split_mode else ("edit" if self.editing_mode else "preview"))
        self.update_view_mode()

    def set_editing_mode(self, editing):
        self.editing_mode = editing
        self.split_mode = False
        self.mode_seg.setCurrentItem("edit" if editing else "preview")
        self.update_view_mode()

    def update_view_mode(self):
        if self.split_mode:
            self.text_edit.show()
            self.preview.show()
            total = self.text_edit.width() + self.preview.width()
            if total > 0:
                half = total // 2
                self.editor_splitter.setSizes([half, half])
        else:
            if self.editing_mode:
                self.text_edit.show()
                self.preview.hide()
            else:
                self.text_edit.hide()
                self.preview.show()
                self.update_preview()

    def update_cursor_position(self):
        cursor = self.text_edit.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self.cursor_position_label.setText(f"行: {line}, 列: {column}")

    def update_preview(self):
        if self.preview.isVisible():
            self.preview.update_preview(self.text_edit.toPlainText())

    # ---------- 格式插入 ----------

    def insert_formatting(self, prefix, suffix):
        """插入格式标记（加粗/斜体）。"""
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            cursor.insertText(f"{prefix}{selected_text}{suffix}")
        else:
            cursor.insertText(f"{prefix}{suffix}")
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(suffix))
            self.text_edit.setTextCursor(cursor)

    def insert_header(self):
        cursor = self.text_edit.textCursor()
        cursor.insertText("# ")

    def insert_link(self):
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            cursor.insertText(f"[{selected_text}](url)")
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 5)
        else:
            cursor.insertText("[链接文本](url)")
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 9)
        self.text_edit.setTextCursor(cursor)

    def insert_code_block(self):
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            cursor.insertText(f"```\n{selected_text}\n```\n")
        else:
            cursor.insertText("```\n\n```")
            cursor.movePosition(QTextCursor.Up, QTextCursor.MoveAnchor, 1)
        self.text_edit.setTextCursor(cursor)

    # ---------- 文件操作 ----------

    def new_file(self):
        if self.check_save_changes():
            self.text_edit.clear()
            self.current_file = None
            self.setWindowTitle('MDPad - Markdown 编辑器')
            self.notify("info", "已新建文件", "", duration=2000)

    def open_file(self):
        if not self.check_save_changes():
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "",
            "所有文件 (*.*);;Markdown文件 (*.md *.markdown *.txt)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path):
        try:
            content = io.read_text_file(file_path)
        except Exception as e:
            self.notify("error", "打开失败", str(e))
            return
        self.text_edit.setPlainText(content)
        self.current_file = file_path
        self.setWindowTitle(f'MDPad - {os.path.basename(file_path)}')
        # 强制更新预览，无论其当前是否可见
        self.preview.update_preview(content)

    def save_file(self):
        if self.current_file:
            self.save_to_file(self.current_file)
        else:
            self.save_file_as()

    def save_file_as(self):
        """另存为：先异步获取 AI 文件名建议，再弹出保存对话框（不阻塞 UI）。"""
        self._ai_suggested_name(self._proceed_save_as)

    def _proceed_save_as(self, suggested):
        if suggested:
            initial_file = suggested + ".md"
        elif self.current_file:
            initial_file = os.path.basename(self.current_file)
        else:
            initial_file = "无标题.md"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存Markdown文件", initial_file,
            "Markdown文件 (*.md *.markdown);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            if not any(file_path.endswith(ext) for ext in ['.md', '.markdown', '.txt']):
                file_path += '.md'
            self.save_to_file(file_path)

    def save_to_file(self, file_path):
        try:
            io.write_text_file(file_path, self.text_edit.toPlainText())
            self.current_file = file_path
            self.setWindowTitle(f'MDPad - {os.path.basename(file_path)}')
            self.text_edit.document().setModified(False)
            self.notify("success", "已保存", file_path)
        except Exception as e:
            self.notify("error", "保存失败", str(e))

    def export_html(self):
        """导出为 HTML：先异步获取 AI 文件名建议，再弹出保存对话框（不阻塞 UI）。"""
        self._ai_suggested_name(self._proceed_export)

    def _proceed_export(self, suggested):
        if suggested:
            base = suggested
        elif self.current_file:
            base = os.path.splitext(os.path.basename(self.current_file))[0]
        else:
            base = "导出文档"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出为HTML", base + ".html",
            "HTML文件 (*.html *.htm);;所有文件 (*.*)"
        )
        if not file_path:
            return
        try:
            html_content = io.render_export_html(self.text_edit.toPlainText())
            io.write_text_file(file_path, html_content)
            self.notify("success", "已导出", file_path)
        except Exception as e:
            self.notify("error", "导出失败", str(e))

    def check_save_changes(self):
        """返回 True 表示可以继续（放弃或已保存），False 表示用户取消。"""
        if not self.text_edit.document().isModified():
            return True
        dialog = SaveChangesDialog(self)
        dialog.exec()
        if dialog.choice == "save":
            self.save_file()
            return True
        if dialog.choice == "discard":
            return True
        return False

    def _ai_suggested_name(self, callback):
        """异步调用 AI 生成文件名建议，完成后经回调返回；期间不阻塞 UI。

        回调签名: callback(name)，name 为 None 表示无建议（失败/空文档/已在请求中）。
        """
        content = self.text_edit.toPlainText()
        if not content or not content.strip():
            callback(None)
            return
        if self._ai_busy:
            callback(None)  # 已有请求在跑，直接走默认名
            return
        self._ai_busy = True
        self._ai_callback = callback
        self._ai_tip = StateToolTip("AI 命名中", "正在根据内容生成文件名…", self)
        self._ai_tip.move(self._ai_tip.getSuitablePos())
        self._ai_tip.show()
        self._ai_worker.start(content)

    def _on_ai_done(self, name, error):
        self._ai_busy = False
        callback, self._ai_callback = self._ai_callback, None
        tip, self._ai_tip = self._ai_tip, None
        if error:
            if tip is not None:
                tip.setContent(error)
                tip.setState(False)
                QTimer.singleShot(2000, tip.hide)
            callback(None)
            return
        if tip is not None:
            tip.setContent(f"AI 命名完成: {name}" if name else "AI 未返回文件名")
            tip.setState(True)  # 成功状态：1 秒后自动淡出
        callback(name)

    # ---------- 拖放 ----------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        file_path = event.mimeData().urls()[0].toLocalFile()
        if not file_path:
            self.notify("warning", "拖放错误", "无法获取有效的文件路径。")
            return
        if not os.path.exists(file_path):
            self.notify("warning", "文件不存在", file_path)
            return
        if not os.path.isfile(file_path):
            self.notify("warning", "不是文件", file_path)
            return
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ('.md', '.markdown', '.txt'):
            box = MessageBox("打开文件", f'文件 "{os.path.basename(file_path)}" 不是标准的Markdown文件 (扩展名: {ext})。\n\n仍然要打开吗？', self)
            box.yesButton.setText("仍然打开")
            box.cancelButton.setText("取消")
            proceed = []
            box.yesSignal.connect(lambda: proceed.append(True))
            box.cancelSignal.connect(lambda: proceed.append(False))
            box.exec()
            if not proceed or not proceed[0]:
                event.acceptProposedAction()
                return
        if self.check_save_changes():
            self.load_file(file_path)
        event.acceptProposedAction()
