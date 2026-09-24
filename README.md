# MDPad

Fluent 风格的 Markdown 编辑器，基于 PyQt5 + PyQt-Fluent-Widgets + Python-Markdown。

支持实时预览、分屏编辑、图片嵌入、链接跳转（文件/网址分流）、AI 智能文件名生成。另有终端版 **v3-tui**（基于 Textual，纯键盘操作）。

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
│   ├── docs/              设计与规格文档
│   └── mdpad/
│       ├── __init__.py    版本信息
│       ├── app.py         启动辅助
│       ├── main_window.py 主窗口（工具栏/文件操作/拖放/格式）
│       ├── preview.py     预览（链接拦截/图片基准目录）
│       ├── links.py       链接与路径纯逻辑
│       ├── io.py          文件读写/HTML 导出
│       ├── ai_naming.py   AI 文件名生成
│       ├── dialogs.py     帮助窗口（快捷键/应用说明）
│       └── search.py      查找与替换（非模态卡片窗口）
├── v3-tui/        终端版（Textual TUI）
│   ├── mdtui.py           入口
│   ├── requirements.txt
│   └── mdpad_tui/
│       ├── app.py         应用主体（三视图/状态栏/文件生命周期）
│       ├── editor.py      编辑区（TextArea 封装）
│       ├── preview.py     预览（Markdown + 链接/图片分发）
│       ├── findbar.py     查找替换底条
│       └── dialogs.py     帮助 / 路径输入 / 退出确认
└── README.md
```

## 安装与运行

```bash
pip install -r v2-fluent/requirements.txt
python v2-fluent/MDPad.pyw            # 启动
python v2-fluent/MDPad.pyw 文档.md    # 启动并打开文件
```

双击 `v2-fluent/MDPad.pyw` 也可直接运行。

```bash
# 终端版（TUI）
pip install -r v3-tui/requirements.txt
python v3-tui/mdtui.py 文档.md         # 启动并打开文件
```

> 依赖注意：`qfluentwidgets` 对应 PyQt5 版的 PyPI 包名是 `PyQt-Fluent-Widgets`（requirements.txt 已锁定）。
> 若再安装 `PyQt6-Fluent-Widgets`，两者共用 `qfluentwidgets` 包名会互相覆盖，启动时报错
> `TypeError: QToolButton(...): argument 1 has unexpected type 'QWidget'`；重装 `pip install "PyQt-Fluent-Widgets>=1.11"` 即可恢复。

## 功能特性

- 实时 Markdown 预览（GitHub 风格）
- 三种视图模式：编辑（F2）/ 预览（F3）/ 分屏（F4），模式与分栏比例会在下次启动时还原
- 打开期间锁定文件：编辑中的文档无法被外部移动 / 删除 / 重命名，自己的保存不受影响
- 图片嵌入：相对路径以当前文件目录为基准，支持 Windows 盘符路径、远程图片
- 链接跳转：文件链接用系统默认程序打开；网址在浏览器打开；锚点页内跳转；mailto 调用系统程序
- AI 智能文件名生成（异步，不卡界面；调用智谱 GLM）
- 拖放打开文件，多编码自动识别（UTF-8/GBK 等）
- 导出 HTML
- 查找与替换：Ctrl+F 弹出卡片窗口（与帮助/保存确认同风格）；查找下一个/上一个（自动循环）、区分大小写、匹配计数；替换当前 / 全部替换
- 跟随系统明暗主题；对话框尺寸与字体随主窗口缩放
- **终端版（v3-tui）**：Textual 实现，编辑/预览/分屏三视图（首启默认分屏、模式持久化）、实时预览防抖、查找替换居中弹窗（关窗后 Ctrl+G 继续跳转、F6 区分大小写）、格式快捷键 Ctrl+B 加粗 / Alt+I 斜体 / Ctrl+K 代码块 / Ctrl+L 链接 / Ctrl+Shift+L 内嵌图片、打开与另存为弹系统文件对话框（不可用时回退内置输入）、文件锁与多编码打开复用 v2 纯逻辑模块、状态栏（文件名/脏标记/行列）、退出未保存确认；应用内 F1 查看快捷键

## 快捷键

| 分类 | 操作 | 快捷键 |
|---|---|---|
| 文件 | 新建 / 打开 / 保存 / 另存为 | Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S |
| 编辑 | 撤销 / 重做 / 剪切 / 复制 / 粘贴 | Ctrl+Z / Ctrl+Y / Ctrl+X / Ctrl+C / Ctrl+V |
| 格式 | 加粗 / 斜体 / 代码块 / 插入链接 | Ctrl+B / Ctrl+I / Ctrl+K / Ctrl+L |
| 查找 | 查找与替换 / 下一个 / 上一个 | Ctrl+F / Ctrl+G / Ctrl+Shift+G |
| 视图 | 编辑 / 预览 / 分屏 | F2 / F3 / F4 |
| 帮助 | 帮助窗口 | F1 |

## 使用提示

- **AI 命名需要本机 key（仓库里不存密钥）**：把智谱 API key 写进 `%APPDATA%\MDPad\ai_key.txt`（一行一个 key，`#` 开头的行忽略；v1 / v2 共用这一份）。没配 key 时点"另存为 / 导出"会在右上角提示该路径，其余流程照常走默认文件名
- 相对路径的图片和链接依赖当前文件目录：新建文档需先保存（Ctrl+S）后，预览中的相对路径图片才能正常显示
- AI 命名：点击"另存为/导出"后右上角转圈，完成后自动弹出保存对话框；无网络时自动回退默认文件名

## 更新记录

- **v1.5.5**：光标动画整块回退——编辑器改回原生 `QTextEdit`（删除 `mdpad/editor.py`）。自绘光标要长期接管 Qt 的光标绘制，会连带影响输入法的候选框定位（`ImCursorRectangle` 宽度 0、Windows 层无光标）；定位正确优先，动画先不要了。其余修复保留
- **v1.5.4**：输入法候选框定位调整——平时保留原生光标（静止/组词/打字全走 Qt 原生路径），只在滑行动画那 ~100ms 临时关掉它由自绘接管；`setCursorWidth(0)` 长期关闭会把 `ImCursorRectangle` 变成宽度 0、Windows 层 `hwndCaret=None`，输入法据此定位就会贴到角落/上一行
- **v1.5.3**：试错版（自建隐形系统光标，非根因）——`setCursorWidth(0)` 后 Windows 层面没有光标（`hwndCaret=None`、`rcCaret=(0,0,0,0)`），输入法拿不到光标位置就把候选框贴到角落/上一行；现在自建一个"有尺寸但位图全 0 = 不可见"的系统光标并持续摆到真实光标处（v1.5.2 只补了 Qt 的 `ImCursorRectangle`，不够）
- **v1.5.2**：补 Qt 的 `ImCursorRectangle` 查询（只修了一半）（自绘光标把原生光标宽度设成 0 后，Qt 的 `ImCursorRectangle` 查询返回宽度 0 的矩形，系统据此把候选框/组字框丢到窗口角落；现在重写 `inputMethodQuery` 补回正常宽度）
- **v1.5.1**：光标动画回到"就一个滑行"（删掉尾迹与落点脉冲，只保留滑行 + 运动期间的强调色）；修掉退格/删除时的抖动，三处根因：① 起点算错（拿旧位置在新文本里重算，删字后常落到别的行甚至文档末尾之外，光标会从很远处飞进来）② 终点算早（光标信号里立刻取矩形拿到的是"还没重排"的旧坐标，会回弹 5~8px）③ 连打时滑行变成"追"（打字/退格间隔 <90ms 直接落位，单发仍滑行）
- **v1.5.0**：打开期间锁定文件（外部不可移动/删除/重命名）；光标平滑移动（滑行 + 尾迹 + 落点脉冲）；修复 F1 重复打开帮助框与保存确认框叠加（遮罩对话框期间禁用主窗口快捷键）；修复视图模式继承后与右上角滑块不一致（模式与分栏比例显式持久化）
- **v1.4.0**：新增查找与替换——Ctrl+F 卡片窗口（与帮助/保存确认对话框同风格，非模态）；查找下一个/上一个（自动循环）、区分大小写单选框、匹配计数；替换当前 / 全部替换；窗口始终居中并随主窗口实时缩放
- **v1.3.0**：修复编辑区退格/大段删除卡顿（预览更新防抖：连续输入合并为一次渲染，不再逐字符全量渲染）
- **v1.2.0**：Fluent 组件重写（v2-fluent）；移除换行/空格快捷键；修复链接跳转与图片嵌入；AI 命名异步化；对话框自适应
- **v1.1.0**：PyQt5 单文件版（v1-pyqt）
