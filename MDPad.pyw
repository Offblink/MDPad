import sys
import os
import webbrowser
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QSplitter, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QAction, QLabel, QTabWidget, QScrollArea, QGroupBox, QPushButton,
    QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QFontComboBox,
    QCheckBox, QTextBrowser
)
from PyQt5.QtCore import Qt, QUrl, QSize, QSettings, QMimeData, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QKeySequence, QIcon, QColor, QPixmap, QDragEnterEvent, QDropEvent
from PyQt5.QtWebEngineWidgets import QWebEngineView
import markdown
import markdown.extensions
import html
import requests
import json

class AboutDialog(QDialog):
    """关于对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 MDPad")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        # 标题
        title_label = QLabel("MDPad Markdown 编辑器")
        title_font = title_label.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 版本信息
        version_label = QLabel("版本 1.1.0")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        layout.addSpacing(20)
        
        # 描述
        desc_label = QLabel(
            "MDPad 是一个功能完整的 Markdown 编辑器，支持实时预览、\n"
            "分屏编辑、语法高亮等功能。\n\n"
            "基于 PyQt5 和 Python-Markdown 构建。"
        )
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # 作者信息
        author_label = QLabel("© 2026 Blinvo")
        author_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(author_label)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        
        self.setLayout(layout)

class HelpDialog(QDialog):
    """帮助对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MDPad 帮助")
        self.resize(600, 500)
        
        layout = QVBoxLayout()
        
        # 创建选项卡
        tabs = QTabWidget()
        
        # 快捷键标签页
        shortcuts_tab = QScrollArea()
        shortcuts_widget = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_widget)
        
        # 文件操作
        file_group = QGroupBox("文件操作")
        file_layout = QFormLayout()
        file_layout.addRow("新建文件", QLabel("Ctrl + N"))
        file_layout.addRow("打开文件", QLabel("Ctrl + O"))
        file_layout.addRow("保存文件", QLabel("Ctrl + S"))
        file_layout.addRow("另存为", QLabel("Ctrl + Shift + S"))
        file_group.setLayout(file_layout)
        shortcuts_layout.addWidget(file_group)
        
        # 编辑操作
        edit_group = QGroupBox("编辑操作")
        edit_layout = QFormLayout()
        edit_layout.addRow("撤销", QLabel("Ctrl + Z"))
        edit_layout.addRow("重做", QLabel("Ctrl + Y 或 Ctrl + Shift + Z"))
        edit_layout.addRow("复制", QLabel("Ctrl + C"))
        edit_layout.addRow("粘贴", QLabel("Ctrl + V"))
        edit_layout.addRow("插入单个换行标签", QLabel("Alt + Enter"))
        edit_layout.addRow("为所有行添加换行标签", QLabel("Alt + Shift + Enter"))
        edit_layout.addRow("全选", QLabel("Ctrl + A"))
        edit_group.setLayout(edit_layout)
        shortcuts_layout.addWidget(edit_group)
        
        # 格式操作
        format_group = QGroupBox("格式操作")
        format_layout = QFormLayout()
        format_layout.addRow("加粗", QLabel("Ctrl + B"))
        format_layout.addRow("斜体", QLabel("Ctrl + I"))
        format_layout.addRow("代码块", QLabel("Ctrl + K"))
        format_layout.addRow("插入链接", QLabel("Ctrl + L"))
        format_group.setLayout(format_layout)
        shortcuts_layout.addWidget(format_group)
        
        # 视图操作
        view_group = QGroupBox("视图操作")
        view_layout = QFormLayout()
        view_layout.addRow("编辑模式", QLabel("F2"))
        view_layout.addRow("预览模式", QLabel("F3"))
        view_layout.addRow("分屏模式", QLabel("F4"))
        view_group.setLayout(view_layout)
        shortcuts_layout.addWidget(view_group)
        
        shortcuts_layout.addStretch()
        shortcuts_tab.setWidget(shortcuts_widget)
        
        # 关于标签页
        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        
        about_text = QTextBrowser()
        about_text.setPlainText("""
MDPad Markdown 编辑器

版本: 1.1.0
构建日期: 2026年3月

功能特性:
- 实时 Markdown 预览
- 分屏编辑模式
- 语法高亮
- 导出 HTML
- 自定义主题
- 快捷键支持
- 拖放打开文件
- 自动添加换行标签
- AI智能文件名总结

技术栈:
- Python 3.x
- PyQt5
- Python-Markdown
- PyQtWebEngine
        """)
        about_layout.addWidget(about_text)
        
        # 添加所有标签页
        tabs.addTab(shortcuts_tab, "快捷键")
        tabs.addTab(about_tab, "关于")
        
        layout.addWidget(tabs)
        
        # 按钮
        buttons = QDialogButtonBox()
        close_button = buttons.addButton("关闭", QDialogButtonBox.RejectRole)
        close_button.clicked.connect(self.reject)
        
        github_button = QPushButton("GitHub 仓库")
        github_button.clicked.connect(lambda: webbrowser.open("https://github.com"))
        buttons.addButton(github_button, QDialogButtonBox.ActionRole)
        
        layout.addWidget(buttons)
        self.setLayout(layout)

class MarkdownPreview(QWebEngineView):
    """Markdown预览组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        
    def update_preview(self, markdown_text):
        """更新预览内容"""
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
            
            # 完整的HTML模板
            html_template = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    /* GitHub风格的Markdown样式 */
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                        font-size: 16px;
                        line-height: 1.6;
                        color: #24292e;
                        background-color: #fff;
                        padding: 20px;
                        max-width: 800px;
                        margin: 0 auto;
                    }}
                    
                    /* 标题 */
                    h1, h2, h3, h4, h5, h6 {{
                        margin-top: 24px;
                        margin-bottom: 16px;
                        font-weight: 600;
                        line-height: 1.25;
                        padding-bottom: 0.3em;
                        border-bottom: 1px solid #eaecef;
                    }}
                    
                    h1 {{ font-size: 2em; }}
                    h2 {{ font-size: 1.5em; }}
                    h3 {{ font-size: 1.25em; }}
                    h4 {{ font-size: 1em; }}
                    h5 {{ font-size: 0.875em; }}
                    h6 {{ font-size: 0.85em; color: #6a737d; }}
                    
                    /* 段落和文本 */
                    p {{
                        margin-top: 0;
                        margin-bottom: 16px;
                    }}
                    
                    /* 列表 */
                    ul, ol {{
                        padding-left: 2em;
                        margin-top: 0;
                        margin-bottom: 16px;
                    }}
                    
                    li + li {{
                        margin-top: 0.25em;
                    }}
                    
                    /* 代码 */
                    code {{
                        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
                        font-size: 85%;
                        padding: 0.2em 0.4em;
                        margin: 0;
                        background-color: rgba(27,31,35,0.05);
                        border-radius: 3px;
                    }}
                    
                    pre {{
                        background-color: #f6f8fa;
                        border-radius: 3px;
                        padding: 16px;
                        overflow: auto;
                        line-height: 1.45;
                    }}
                    
                    pre code {{
                        background-color: transparent;
                        padding: 0;
                        border-radius: 0;
                    }}
                    
                    /* 引用 */
                    blockquote {{
                        padding: 0 1em;
                        color: #6a737d;
                        border-left: 0.25em solid #dfe2e5;
                        margin: 0 0 16px 0;
                    }}
                    
                    blockquote > :first-child {{
                        margin-top: 0;
                    }}
                    
                    blockquote > :last-child {{
                        margin-bottom: 0;
                    }}
                    
                    /* 表格 */
                    table {{
                        border-spacing: 0;
                        border-collapse: collapse;
                        margin-bottom: 16px;
                        width: 100%;
                    }}
                    
                    th, td {{
                        padding: 6px 13px;
                        border: 1px solid #dfe2e5;
                    }}
                    
                    th {{
                        font-weight: 600;
                        background-color: #f6f8fa;
                    }}
                    
                    tr:nth-child(2n) {{
                        background-color: #f6f8fa;
                    }}
                    
                    /* 链接 */
                    a {{
                        color: #0366d6;
                        text-decoration: none;
                    }}
                    
                    a:hover {{
                        text-decoration: underline;
                    }}
                    
                    /* 图片 */
                    img {{
                        max-width: 100%;
                        box-sizing: initial;
                        background-color: #fff;
                        border-style: none;
                    }}
                    
                    /* 水平线 */
                    hr {{
                        height: 0.25em;
                        padding: 0;
                        margin: 24px 0;
                        background-color: #e1e4e8;
                        border: 0;
                    }}
                    
                    /* 任务列表 */
                    .task-list-item {{
                        list-style-type: none;
                    }}
                    
                    .task-list-item-checkbox {{
                        margin: 0 0.2em 0.25em -1.6em;
                        vertical-align: middle;
                    }}
                    
                    /* 换行标签样式 */
                    br {{
                        display: block;
                        content: "";
                        margin-top: 0.5em;
                    }}
                    
                    /* 代码高亮 */
                    .codehilite .hll {{ background-color: #ffffcc }}
                    .codehilite  {{ background: #f8f8f8; }}
                    .codehilite .c {{ color: #408080; font-style: italic }} /* Comment */
                    .codehilite .err {{ border: 1px solid #FF0000 }} /* Error */
                    .codehilite .k {{ color: #008000; font-weight: bold }} /* Keyword */
                    .codehilite .o {{ color: #666666 }} /* Operator */
                    .codehilite .ch {{ color: #408080; font-style: italic }} /* Comment.Hashbang */
                    .codehilite .cm {{ color: #408080; font-style: italic }} /* Comment.Multiline */
                    .codehilite .cp {{ color: #BC7A00 }} /* Comment.Preproc */
                    .codehilite .cpf {{ color: #408080; font-style: italic }} /* Comment.PreprocFile */
                    .codehilite .c1 {{ color: #408080; font-style: italic }} /* Comment.Single */
                    .codehilite .cs {{ color: #408080; font-style: italic }} /* Comment.Single */
                    .codehilite .gd {{ color: #A00000 }} /* Generic.Deleted */
                    .codehilite .ge {{ font-style: italic }} /* Generic.Emph */
                    .codehilite .gr {{ color: #FF0000 }} /* Generic.Error */
                    .codehilite .gh {{ color: #000080; font-weight: bold }} /* Generic.Heading */
                    .codehilite .gi {{ color: #00A000 }} /* Generic.Inserted */
                    .codehilite .go {{ color: #888888 }} /* Generic.Output */
                    .codehilite .gp {{ color: #000080; font-weight: bold }} /* Generic.Prompt */
                    .codehilite .gs {{ font-weight: bold }} /* Generic.Strong */
                    .codehilite .gu {{ color: #800080; font-weight: bold }} /* Generic.Subheading */
                    .codehilite .gt {{ color: #0044DD }} /* Generic.Traceback */
                    .codehilite .kc {{ color: #008000; font-weight: bold }} /* Keyword.Constant */
                    .codehilite .kd {{ color: #008000; font-weight: bold }} /* Keyword.Declaration */
                    .codehilite .kn {{ color: #008000; font-weight: bold }} /* Keyword.Namespace */
                    .codehilite .kp {{ color: #008000 }} /* Keyword.Pseudo */
                    .codehilite .kr {{ color: #008000; font-weight: bold }} /* Keyword.Reserved */
                    .codehilite .kt {{ color: #B00040 }} /* Keyword.Type */
                    .codehilite .m {{ color: #666666 }} /* Literal.Number */
                    .codehilite .s {{ color: #BA2121 }} /* Literal.String */
                    .codehilite .na {{ color: #7D9029 }} /* Name.Attribute */
                    .codehilite .nb {{ color: #008000 }} /* Name.Builtin */
                    .codehilite .nc {{ color: #0000FF; font-weight: bold }} /* Name.Class */
                    .codehilite .no {{ color: #880000 }} /* Name.Constant */
                    .codehilite .nd {{ color: #AA22FF }} /* Name.Decorator */
                    .codehilite .ni {{ color: #999999; font-weight: bold }} /* Name.Entity */
                    .codehilite .ne {{ color: #D2413A; font-weight: bold }} /* Name.Exception */
                    .codehilite .nf {{ color: #0000FF }} /* Name.Function */
                    .codehilite .nl {{ color: #A0A000 }} /* Name.Label */
                    .codehilite .nn {{ color: #0000FF; font-weight: bold }} /* Name.Namespace */
                    .codehilite .nt {{ color: #008000; font-weight: bold }} /* Name.Tag */
                    .codehilite .nv {{ color: #19177C }} /* Name.Variable */
                    .codehilite .ow {{ color: #AA22FF; font-weight: bold }} /* Operator.Word */
                    .codehilite .w {{ color: #bbbbbb }} /* Text.Whitespace */
                    .codehilite .mb {{ color: #666666 }} /* Literal.Number.Bin */
                    .codehilite .mf {{ color: #666666 }} /* Literal.Number.Float */
                    .codehilite .mh {{ color: #666666 }} /* Literal.Number.Hex */
                    .codehilite .mi {{ color: #666666 }} /* Literal.Number.Integer */
                    .codehilite .mo {{ color: #666666 }} /* Literal.Number.Oct */
                    .codehilite .sa {{ color: #BA2121 }} /* Literal.String.Affix */
                    .codehilite .sb {{ color: #BA2121 }} /* Literal.String.Backtick */
                    .codehilite .sc {{ color: #BA2121 }} /* Literal.String.Char */
                    .codehilite .dl {{ color: #BA2121 }} /* Literal.String.Delimiter */
                    .codehilite .sd {{ color: #BA2121; font-style: italic }} /* Literal.String.Doc */
                    .codehilite .s2 {{ color: #BA2121 }} /* Literal.String.Double */
                    .codehilite .se {{ color: #BB6622; font-weight: bold }} /* Literal.String.Escape */
                    .codehilite .sh {{ color: #BA2121 }} /* Literal.String.Heredoc */
                    .codehilite .si {{ color: #BB6688; font-weight: bold }} /* Literal.String.Interpol */
                    .codehilite .sx {{ color: #008000 }} /* Literal.String.Other */
                    .codehilite .sr {{ color: #BB6688 }} /* Literal.String.Regex */
                    .codehilite .s1 {{ color: #BA2121 }} /* Literal.String.Single */
                    .codehilite .ss {{ color: #19177C }} /* Literal.String.Symbol */
                    .codehilite .bp {{ color: #008000 }} /* Name.Builtin.Pseudo */
                    .codehilite .fm {{ color: #0000FF }} /* Name.Function.Magic */
                    .codehilite .vc {{ color: #19177C }} /* Name.Variable.Class */
                    .codehilite .vg {{ color: #19177C }} /* Name.Variable.Global */
                    .codehilite .vi {{ color: #19177C }} /* Name.Variable.Instance */
                    .codehilite .vm {{ color: #19177C }} /* Name.Variable.Magic */
                    .codehilite .il {{ color: #666666 }} /* Literal.Number.Integer.Long */
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            self.setHtml(html_template)
        except Exception as e:
            self.setHtml(f"<h1>预览错误</h1><p>{str(e)}</p>")

class MarkdownEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.split_mode = True  # 默认分屏模式
        self.editing_mode = True
        # 新增：设置AI API
        self.API_KEY = "e7509fc557394a619bc89d9bc44172ce.qY4uSyCofHoCfQSX"  # 用户提供的API密钥
        self.API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"  # 根据用户提供的URL基础补全
        self.init_ui()
        self.load_settings()
        
        # 启用拖放功能
        self.setAcceptDrops(True)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        """处理拖放进入事件，接受所有文件类型"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path:  # 只要文件路径有效就接受
                    event.acceptProposedAction()
                    return
        event.ignore()
        
    def dropEvent(self, event: QDropEvent):
        """处理拖放释放事件，加载文件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                # 只处理第一个文件
                file_path = urls[0].toLocalFile()
                
                if not file_path:
                    QMessageBox.warning(self, "拖放错误", 
                                      "无法获取有效的文件路径。")
                    return
                    
                if not os.path.exists(file_path):
                    QMessageBox.warning(self, "文件不存在", 
                                      f"文件不存在或无法访问:\n{file_path}")
                    return
                    
                if not os.path.isfile(file_path):
                    QMessageBox.warning(self, "不是文件", 
                                      f"拖放的不是一个文件:\n{file_path}")
                    return
                
                # 检查文件扩展名，如果是非Markdown文件则提示
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext not in ['.md', '.markdown', '.txt']:
                    reply = QMessageBox.question(
                        self, '打开文件',
                        f'您拖放的文件 "{os.path.basename(file_path)}" 不是标准的Markdown文件 (扩展名: {file_ext})。\n\n'
                        'Markdown文件通常以 .md、.markdown 或 .txt 结尾。\n\n'
                        '您仍然想要打开此文件吗？',
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        return
                
                # 检查是否有未保存的更改
                if self.check_save_changes():
                    try:
                        self.load_file(file_path)
                        self.status_bar.showMessage(f"已通过拖放打开: {os.path.basename(file_path)}", 3000)
                    except Exception as e:
                        QMessageBox.critical(self, "打开失败", 
                                           f"无法打开文件:\n{str(e)}")
                
                event.acceptProposedAction()
            
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle('MDPad - Markdown 编辑器')
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置图标
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建菜单栏
        self.create_menubar()
        
        # 创建工具栏
        self.create_toolbar()
        main_layout.addWidget(self.toolbar)
        
        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.cursor_position_label = QLabel("行: 1, 列: 1")
        self.status_bar.addPermanentWidget(self.cursor_position_label)
        
        # 创建主编辑器区域
        self.create_editor_area()
        main_layout.addWidget(self.editor_splitter, 1)
        
        # 设置初始状态为分屏模式
        self.set_split_mode(True)
        
    def create_menubar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        new_action = QAction('新建', self)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)
        
        open_action = QAction('打开', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        save_action = QAction('保存', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction('另存为', self)
        save_as_action.setShortcut('Ctrl+Shift+S')
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        export_html_action = QAction('导出为HTML', self)
        export_html_action.triggered.connect(self.export_html)
        file_menu.addAction(export_html_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu('编辑')
        
        undo_action = QAction('撤销', self)
        undo_action.setShortcut('Ctrl+Z')
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction('重做', self)
        redo_action.setShortcut('Ctrl+Y')
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        cut_action = QAction('剪切', self)
        cut_action.setShortcut('Ctrl+X')
        cut_action.triggered.connect(self.cut)
        edit_menu.addAction(cut_action)
        
        copy_action = QAction('复制', self)
        copy_action.setShortcut('Ctrl+C')
        copy_action.triggered.connect(self.copy)
        edit_menu.addAction(copy_action)
        
        paste_action = QAction('粘贴', self)
        paste_action.setShortcut('Ctrl+V')
        paste_action.triggered.connect(self.paste)
        edit_menu.addAction(paste_action)
        
        # 从菜单栏移除换行功能，移至工具栏
        # 注意：我们不再在菜单栏添加换行功能
        
        # 视图菜单
        view_menu = menubar.addMenu('视图')
        
        edit_mode_action = QAction('编辑模式', self)
        edit_mode_action.setShortcut('F2')
        edit_mode_action.triggered.connect(lambda: self.set_editing_mode(True))
        view_menu.addAction(edit_mode_action)
        
        preview_mode_action = QAction('预览模式', self)
        preview_mode_action.setShortcut('F3')
        preview_mode_action.triggered.connect(lambda: self.set_editing_mode(False))
        view_menu.addAction(preview_mode_action)
        
        split_mode_action = QAction('分屏模式', self)
        split_mode_action.setShortcut('F4')
        split_mode_action.triggered.connect(self.toggle_split_view)
        view_menu.addAction(split_mode_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
        
        shortcuts_action = QAction('快捷键', self)
        shortcuts_action.setShortcut('F1')
        shortcuts_action.triggered.connect(self.show_help)
        help_menu.addAction(shortcuts_action)
        
        help_menu.addSeparator()
        
        about_action = QAction('关于 MDPad', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_toolbar(self):
        """创建工具栏 - 包含格式按钮和换行按钮"""
        self.toolbar = QToolBar("主工具栏")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(20, 20))
        
        # 加粗
        bold_action = QAction("B", self)
        bold_action.setToolTip("加粗 (Ctrl+B)")
        bold_action.setShortcut("Ctrl+B")
        bold_action.triggered.connect(lambda: self.insert_formatting("**", "**"))
        self.toolbar.addAction(bold_action)
        
        # 斜体
        italic_action = QAction("I", self)
        italic_action.setToolTip("斜体 (Ctrl+I)")
        italic_action.setShortcut("Ctrl+I")
        italic_action.triggered.connect(lambda: self.insert_formatting("*", "*"))
        self.toolbar.addAction(italic_action)
        
        self.toolbar.addSeparator()
        
        # 标题
        header_action = QAction("H", self)
        header_action.setToolTip("插入标题")
        header_action.triggered.connect(self.insert_header)
        self.toolbar.addAction(header_action)
        
        # 链接
        link_action = QAction("🔗", self)
        link_action.setToolTip("插入链接 (Ctrl+L)")
        link_action.setShortcut("Ctrl+L")
        link_action.triggered.connect(self.insert_link)
        self.toolbar.addAction(link_action)
        
        # 代码块
        code_action = QAction("</>", self)
        code_action.setToolTip("插入代码块 (Ctrl+K)")
        code_action.setShortcut("Ctrl+K")
        code_action.triggered.connect(self.insert_code_block)
        self.toolbar.addAction(code_action)
        
        self.toolbar.addSeparator()
        
        # 单个换行标签按钮
        single_linebreak_action = QAction("↩", self)
        single_linebreak_action.setToolTip("插入单个换行标签<br> (Alt+Enter)")
        single_linebreak_action.setShortcut("Alt+Enter")
        single_linebreak_action.triggered.connect(self.insert_single_linebreak)
        self.toolbar.addAction(single_linebreak_action)
        
        # 全部添加换行标签按钮
        all_linebreaks_action = QAction("⏎⏎", self)
        all_linebreaks_action.setToolTip("为所有行添加换行标签<br> (Alt+Shift+Enter)")
        all_linebreaks_action.setShortcut("Alt+Shift+Enter")
        all_linebreaks_action.triggered.connect(self.insert_all_linebreaks)
        self.toolbar.addAction(all_linebreaks_action)
        
    def create_editor_area(self):
        """创建编辑器区域"""
        self.editor_splitter = QSplitter(Qt.Horizontal)
        
        # 创建编辑器
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Consolas", 11))
        self.text_edit.textChanged.connect(self.update_preview)
        self.text_edit.cursorPositionChanged.connect(self.update_cursor_position)
        # 关键修改1：禁止文本编辑框本身接受拖放，让事件传递给父窗口
        self.text_edit.setAcceptDrops(False)
        
        # 创建预览窗口
        self.preview = MarkdownPreview()
        # 关键修改2：禁止预览组件本身接受拖放，让事件传递给父窗口
        self.preview.setAcceptDrops(False)
        
        # 添加到分割器
        self.editor_splitter.addWidget(self.text_edit)
        self.editor_splitter.addWidget(self.preview)
        
        # 关键修改3：确保分割器本身也不会拦截拖放事件
        self.editor_splitter.setAcceptDrops(False)      
    
    def insert_single_linebreak(self):
        """在当前光标位置插入单个换行标签 <br>"""
        cursor = self.text_edit.textCursor()
        
        # 开始一个编辑操作，以便可以撤销
        cursor.beginEditBlock()
        
        # 在光标处插入HTML换行标签
        cursor.insertText("<br>")
        
        # 结束编辑操作
        cursor.endEditBlock()
        
        # 将新光标位置设置回编辑器
        self.text_edit.setTextCursor(cursor)
        # 触发预览更新
        self.update_preview()
        self.status_bar.showMessage("已在光标位置插入换行标签 <br> (可按 Ctrl+Z 撤销)", 2000)

    def insert_all_linebreaks(self):
        """在每一行末尾自动添加换行标签 <br>，并支持撤销/重做"""
        # 获取当前文档的全部文本
        current_text = self.text_edit.toPlainText()
        
        # 如果文本为空，直接返回
        if not current_text.strip():
            self.status_bar.showMessage("文档为空，无需添加换行标签", 2000)
            return
        
        # 获取文档和光标
        cursor = self.text_edit.textCursor()
        
        # 开始一个编辑块，这样整个操作可以一次性撤销/重做
        cursor.beginEditBlock()
        
        # 保存原始光标位置
        original_position = cursor.position()
        
        try:
            # 计算新文本
            lines = current_text.splitlines()
            new_lines = []
            
            for i, line in enumerate(lines):
                # 在每一行末尾添加 <br> 标签
                new_line = line + "<br>"
                new_lines.append(new_line)
            
            # 重新组合文本
            new_text = "\n".join(new_lines)
            
            # 替换整个文档内容
            cursor.select(QTextCursor.Document)
            cursor.removeSelectedText()
            cursor.insertText(new_text)
            
            # 恢复光标位置
            cursor.setPosition(min(original_position, len(new_text)))
            
        except Exception as e:
            QMessageBox.warning(self, "操作失败", f"添加换行标签时出错: {str(e)}")
            cursor.endEditBlock()  # 结束编辑块
            return
        
        # 结束编辑块
        cursor.endEditBlock()
        
        # 更新编辑器光标
        self.text_edit.setTextCursor(cursor)
        
        # 触发预览更新
        self.update_preview()
        self.status_bar.showMessage("已在每一行末尾添加了换行标签 <br> (可按 Ctrl+Z 撤销)", 3000)
    
    def generate_filename_with_ai(self, content):
        """
        调用AI API，根据文档内容生成10个字以内的默认文件名。
        
        参数:
            content: 文档的文本内容
            
        返回:
            成功: 生成的简短文件名 (不包含扩展名)
            失败: 返回 None
        """
        if not content or not content.strip():
            return None
            
        # 准备API请求
        prompt = f"""
        请将以下文本内容总结成一个10个中文字以内的短标题，用于作为文件名。不要包含任何标点符号、引号或文件扩展名。\n
        文本内容：\n{content[:2000]}  # 限制输入长度
        """
        
        headers = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "glm-4-flash",  # 使用一个通用模型，您可以根据需要修改
            "messages": [
                {"role": "system", "content": "你是一个文件命名助手，请根据内容生成简洁的标题，不超过10个字。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 20
        }
        
        try:
            self.status_bar.showMessage("正在通过AI生成文件名...", 3000)
            response = requests.post(self.API_URL, headers=headers, json=payload, timeout=10)
            response.raise_for_status()  # 检查HTTP错误
            
            data = response.json()
            ai_response = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            # 清理响应，移除引号、句号等，并确保长度
            cleaned_name = ai_response.replace('"', '').replace("'", "").replace("。", "").replace(".", "")
            # 如果AI返回了过长的内容，截取前10个字符
            if len(cleaned_name) > 10:
                cleaned_name = cleaned_name[:10]
                
            if cleaned_name:
                self.status_bar.showMessage(f"AI建议文件名: {cleaned_name}", 3000)
                return cleaned_name
            else:
                self.status_bar.showMessage("AI未返回有效的文件名", 2000)
                return None
                
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "AI调用超时", "请求AI服务超时，将使用默认文件名。")
            return None
        except requests.exceptions.RequestException as e:
            QMessageBox.warning(self, "AI调用失败", f"无法连接到AI服务: {str(e)}")
            return None
        except Exception as e:
            QMessageBox.warning(self, "AI处理错误", f"处理AI响应时出错: {str(e)}")
            return None
    
    def set_split_mode(self, enabled):
        """设置分屏模式"""
        self.split_mode = enabled
        if enabled:
            self.text_edit.show()
            self.preview.show()
            # 设置默认分割比例为1:1
            self.editor_splitter.setSizes([int(self.width()/2), int(self.width()/2)])
        else:
            if self.editing_mode:
                self.text_edit.show()
                self.preview.hide()
            else:
                self.text_edit.hide()
                self.preview.show()
                self.update_preview()
                
    def update_cursor_position(self):
        """更新光标位置显示"""
        cursor = self.text_edit.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self.cursor_position_label.setText(f"行: {line}, 列: {column}")
        
    def update_preview(self):
        """更新预览内容"""
        if self.preview.isVisible():
            markdown_text = self.text_edit.toPlainText()
            self.preview.update_preview(markdown_text)
            
    def set_editing_mode(self, editing):
        """设置编辑模式"""
        self.editing_mode = editing
        self.split_mode = False
        self.update_view_mode()
        
    def toggle_split_view(self):
        """切换分屏模式"""
        self.split_mode = not self.split_mode
        self.update_view_mode()
        
    def update_view_mode(self):
        """更新视图模式"""
        if self.split_mode:
            self.text_edit.show()
            self.preview.show()
            # 确保等分
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
                
    def new_file(self):
        """新建文件"""
        if self.check_save_changes():
            self.text_edit.clear()
            self.current_file = None
            self.setWindowTitle('MDPad - Markdown 编辑器')
            self.status_bar.showMessage("已创建新文件", 3000)
            
    def open_file(self):
        """打开文件 - 不限制文件类型"""
        if self.check_save_changes():
            file_path, selected_filter = QFileDialog.getOpenFileName(
                self, "打开文件", "", 
                "所有文件 (*.*);;Markdown文件 (*.md *.markdown *.txt)"
            )
            if file_path:
                # 检查文件扩展名，如果是非Markdown文件则提示
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext not in ['.md', '.markdown', '.txt']:
                    reply = QMessageBox.question(
                        self, '打开文件',
                        f'您选择的文件 "{os.path.basename(file_path)}" 不是标准的Markdown文件 (扩展名: {file_ext})。\n\n'
                        'Markdown文件通常以 .md、.markdown 或 .txt 结尾。\n\n'
                        '您仍然想要打开此文件吗？',
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        return
                
                self.load_file(file_path)
                
    def load_file(self, file_path):
        """加载文件"""
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'latin-1']
            content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        content = file.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                # 如果所有编码都失败，尝试二进制读取
                with open(file_path, 'rb') as file:
                    binary_data = file.read()
                    # 尝试解码为文本，忽略错误
                    content = binary_data.decode('utf-8', errors='ignore')
            
            self.text_edit.setPlainText(content)
            self.current_file = file_path
            self.setWindowTitle(f'MDPad - {os.path.basename(file_path)}')
            self.status_bar.showMessage(f"已打开: {file_path}", 3000)
            # 强制更新预览，无论其当前是否可见
            self.preview.update_preview(content)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开文件: {str(e)}")
            
    def save_file(self):
        """保存文件"""
        if self.current_file:
            self.save_to_file(self.current_file)
        else:
            self.save_file_as()  # 如果没有文件名，则调用另存为
            
    def save_file_as(self):
        """另存为文件"""
        # 新增：在打开对话框前，尝试调用AI生成默认文件名
        default_name = None
        content = self.text_edit.toPlainText()
        if content and content.strip():
            # 调用AI生成文件名建议
            default_name = self.generate_filename_with_ai(content)
        
        # 准备初始文件名
        initial_file = ""
        if default_name:
            initial_file = default_name + ".md"
        elif self.current_file:
            # 如果已有文件名，使用原文件名
            initial_file = os.path.basename(self.current_file)
        else:
            # 否则使用默认的"无标题"
            initial_file = "无标题.md"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存Markdown文件", initial_file,  # 使用AI生成的文件名作为初始建议
            "Markdown文件 (*.md *.markdown);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            if not any(file_path.endswith(ext) for ext in ['.md', '.markdown', '.txt']):
                file_path += '.md'
            # 关键修正：调用 save_to_file 来实际保存文件
            self.save_to_file(file_path)
            
    def save_to_file(self, file_path):
        """保存到指定文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(self.text_edit.toPlainText())
                self.current_file = file_path
                self.setWindowTitle(f'MDPad - {os.path.basename(file_path)}')
                self.status_bar.showMessage(f"已保存: {file_path}", 3000)
                self.text_edit.document().setModified(False)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法保存文件: {str(e)}")
            
    def export_html(self):
        """导出为HTML"""
        # 新增：在打开对话框前，尝试调用AI生成默认文件名
        default_name = None
        content = self.text_edit.toPlainText()
        if content and content.strip():
            # 调用AI生成文件名建议
            default_name = self.generate_filename_with_ai(content)
        
        # 准备初始文件名
        initial_file = ""
        if default_name:
            # 为HTML文件使用 .html 后缀
            initial_file = default_name + ".html"
        elif self.current_file:
            # 如果已有Markdown文件名，则在其基础上修改后缀
            base_name = os.path.splitext(os.path.basename(self.current_file))[0]
            initial_file = base_name + ".html"
        else:
            # 否则使用默认的“导出文档”
            initial_file = "导出文档.html"
        
        # 在文件对话框中应用初始文件名
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "导出为HTML", 
            initial_file,  # 使用AI生成或推导的文件名作为初始建议
            "HTML文件 (*.html *.htm);;所有文件 (*.*)"
        )
        if file_path:
            try:
                markdown_text = self.text_edit.toPlainText()
                html_content = markdown.markdown(markdown_text, extensions=['extra', 'codehilite', 'toc'])
                
                # 完整的HTML模板
                html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MDPad 导出</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            background-color: #ffffff;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}
        h1 {{ font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.25em; }}
        code {{
            background-color: rgba(27,31,35,0.05);
            border-radius: 3px;
            padding: 0.2em 0.4em;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
        }}
        pre {{
            background-color: #f6f8fa;
            border-radius: 3px;
            padding: 16px;
            overflow: auto;
        }}
        blockquote {{
            border-left: 4px solid #dfe2e5;
            padding-left: 16px;
            color: #6a737d;
            margin-left: 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
        }}
        th, td {{
            border: 1px solid #dfe2e5;
            padding: 6px 13px;
        }}
        th {{
            background-color: #f6f8fa;
        }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        img {{ max-width: 100%; }}
        br {{
            display: block;
            content: "";
            margin-top: 0.5em;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""
                
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(html_template)
                self.status_bar.showMessage(f"已导出: {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
            
    def check_save_changes(self):
        """检查是否需要保存更改"""
        if self.text_edit.document().isModified():
            reply = QMessageBox.question(
                self, '保存更改',
                '文件已修改，是否保存更改？',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self.save_file()
                return True
            elif reply == QMessageBox.No:
                return True
            else:
                return False
        return True
        
    def insert_formatting(self, prefix, suffix):
        """插入格式标记"""
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            cursor.insertText(f"{prefix}{selected_text}{suffix}")
        else:
            cursor.insertText(f"{prefix}{suffix}")
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(suffix))
            self.text_edit.setTextCursor(cursor)
            
    def insert_header(self):
        """插入标题"""
        cursor = self.text_edit.textCursor()
        cursor.insertText("# ")
        
    def insert_link(self):
        """插入链接"""
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
        """插入代码块"""
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            cursor.insertText(f"```\n{selected_text}\n```\n")
        else:
            cursor.insertText("```\n\n```")
            cursor.movePosition(QTextCursor.Up, QTextCursor.MoveAnchor, 1)
        self.text_edit.setTextCursor(cursor)
        
    def undo(self):
        """撤销操作"""
        self.text_edit.undo()
        
    def redo(self):
        """重做操作"""
        self.text_edit.redo()
        
    def cut(self):
        """剪切"""
        self.text_edit.cut()
        
    def copy(self):
        """复制"""
        self.text_edit.copy()
        
    def paste(self):
        """粘贴"""
        self.text_edit.paste()
        
    def show_help(self):
        """显示帮助对话框"""
        help_dialog = HelpDialog(self)
        help_dialog.exec_()
        
    def show_about(self):
        """显示关于对话框"""
        about_dialog = AboutDialog(self)
        about_dialog.exec_()
        
    def load_settings(self):
        """加载设置"""
        self.settings = QSettings("MDPad", "Editor")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        split_sizes = self.settings.value("split_sizes")
        if split_sizes:
            self.editor_splitter.setSizes([int(size) for size in split_sizes])
            
    def save_settings(self):
        """保存设置"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("split_sizes", self.editor_splitter.sizes())
        
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.check_save_changes():
            self.save_settings()
            event.accept()
        else:
            event.ignore()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MDPad")
    app.setOrganizationName("MDPad")
    app.setOrganizationDomain("mdpad.example.com")
    
    # 设置样式
    app.setStyle("Fusion")
    
    # 创建必要的图标文件
    icon_dir = os.path.dirname(__file__)
    icon_path = os.path.join(icon_dir, "icon.ico")
    
    # 如果没有图标，可以创建默认的应用程序图标
    if not os.path.exists(icon_path):
        # 这里可以添加创建默认图标的代码，但为了简单起见，我们只是跳过
        # 在实际应用中，您可以包含一个默认图标文件
        pass
    
    # 创建编辑器
    editor = MarkdownEditor()
    
    # 设置窗口图标
    if os.path.exists(icon_path):
        editor.setWindowIcon(QIcon(icon_path))
    
    # --- 处理命令行参数以支持关联打开 ---
    # 判断是否通过命令行参数指定了文件（例如通过右键"打开方式"）
    # sys.argv[0] 是脚本名，从 sys.argv[1] 开始是用户传入的参数
    if len(sys.argv) > 1:
        # 假设第一个参数是文件路径
        file_to_open = sys.argv[1]
        # 检查文件是否存在且是有效文件
        if os.path.isfile(file_to_open):
            # 检查文件扩展名，如果是非Markdown文件则提示
            file_ext = os.path.splitext(file_to_open)[1].lower()
            if file_ext not in ['.md', '.markdown', '.txt']:
                reply = QMessageBox.question(editor, '打开文件',
                                           f'文件"{os.path.basename(file_to_open)}"不是标准的Markdown文件 (扩展名: {file_ext})。\n\n'
                                           'Markdown文件通常以 .md、.markdown 或 .txt 结尾。\n\n'
                                           '您仍然想要打开此文件吗？',
                                           QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    sys.exit(0)
            # 通过现有的方法加载文件
            editor.load_file(file_to_open)
        else:
            QMessageBox.warning(editor, "文件未找到", f"无法找到文件：{file_to_open}")
    # --- 参数处理结束 ---
    
    editor.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()