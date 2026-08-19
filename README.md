# MDPad

Fluent 风格的 Markdown 编辑器，基于 PyQt5 + PyQt-Fluent-Widgets + Python-Markdown。

支持实时预览、分屏编辑、图片嵌入、链接跳转（文件/网址分流）、AI 智能文件名生成。

## 目录结构

```
MDPad/
├── v1-pyqt/       旧版（PyQt5 单文件）
│   ├── MDPad.pyw
│   ├── icon.ico
│   ├── requirements.txt
│   └── README.md
├── v2-fluent/     当前版（Fluent 组件，多文件模块化）
│   ├── MDPad.pyw          入口
│   ├── icon.ico
│   ├── requirements.txt
│   └── mdpad/
│       ├── __init__.py    版本信息
│       ├── app.py         启动辅助
│       ├── main_window.py 主窗口（工具栏/文件操作/拖放/格式）
│       ├── preview.py     预览（链接拦截/图片基准目录）
│       ├── links.py       链接与路径纯逻辑
│       ├── io.py          文件读写/HTML 导出
│       ├── ai_naming.py   AI 文件名生成
│       └── dialogs.py     帮助窗口（快捷键/应用说明）
└── README.md
```

## 安装与运行

```bash
pip install -r v2-fluent/requirements.txt
python v2-fluent/MDPad.pyw            # 启动
python v2-fluent/MDPad.pyw 文档.md    # 启动并打开文件
```

双击 `v2-fluent/MDPad.pyw` 也可直接运行。

## 功能特性

- 实时 Markdown 预览（GitHub 风格）
- 三种视图模式：编辑（F2）/ 预览（F3）/ 分屏（F4）
- 图片嵌入：相对路径以当前文件目录为基准，支持 Windows 盘符路径、远程图片
- 链接跳转：文件链接用系统默认程序打开；网址在浏览器打开；锚点页内跳转；mailto 调用系统程序
- AI 智能文件名生成（异步，不卡界面；调用智谱 GLM）
- 拖放打开文件，多编码自动识别（UTF-8/GBK 等）
- 导出 HTML
- 跟随系统明暗主题；对话框尺寸与字体随主窗口缩放

## 快捷键

| 分类 | 操作 | 快捷键 |
|---|---|---|
| 文件 | 新建 / 打开 / 保存 / 另存为 | Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S |
| 编辑 | 撤销 / 重做 / 剪切 / 复制 / 粘贴 | Ctrl+Z / Ctrl+Y / Ctrl+X / Ctrl+C / Ctrl+V |
| 格式 | 加粗 / 斜体 / 代码块 / 插入链接 | Ctrl+B / Ctrl+I / Ctrl+K / Ctrl+L |
| 视图 | 编辑 / 预览 / 分屏 | F2 / F3 / F4 |
| 帮助 | 帮助窗口 | F1 |

## 使用提示

- 相对路径的图片和链接依赖当前文件目录：新建文档需先保存（Ctrl+S）后，预览中的相对路径图片才能正常显示
- AI 命名：点击"另存为/导出"后右上角转圈，完成后自动弹出保存对话框；无网络时自动回退默认文件名

## 更新记录

- **v1.2.0**：Fluent 组件重写（v2-fluent）；移除换行/空格快捷键；修复链接跳转与图片嵌入；AI 命名异步化；对话框自适应
- **v1.1.0**：PyQt5 单文件版（v1-pyqt）
