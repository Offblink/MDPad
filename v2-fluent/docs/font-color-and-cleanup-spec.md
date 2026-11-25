# 设计 & 规格：字体颜色、替换快捷键、去 AI 命名、应用说明简化（v1.8.0）

## Problem

1. **字体颜色**：编辑器没有给文字上色的入口。需求：工具栏点开出现下拉菜单（红 / 绿 / 蓝），并可展开选色面板自定义颜色。
2. **替换快捷键**：查找已有 Ctrl+F / Ctrl+G / Ctrl+Shift+G，替换与全部替换只有按钮，且必须先打开窗口。
3. **去掉 AI 命名**：另存为 / 导出前会异步请求 AI 生成文件名（依赖 `%APPDATA%\MDPad\ai_key.txt`），属于外部依赖，移除以收敛应用职责。
4. **简化应用说明**：帮助页「应用说明」目前是完整版本历史，需求是只介绍应用本身，不追踪版本。

## Decisions（用户已定）

| 决策 | 结论 |
|---|---|
| 字体颜色作用面 | **选区上色**：写入 Markdown HTML 标记，预览与导出 HTML 可见；不改编辑器全局主题 |
| 替换快捷键 | 现有基础上增加**不打开窗口**的替换当前；键位由实现方定 |
| AI 命名范围 | 只删 `v2-fluent`；`v1-pyqt` 冻结版原样保留 |
| 应用说明范围 | 只改应用内帮助页；README 更新记录保留 |

## Options Considered

### 颜色标记语法

| 方案 | 预览/导出 | 源码可读性 | 结论 |
|---|---|---|---|
| `<span style="color:#RRGGBB">…</span>` | `markdown` 默认直通原始 HTML，生效 | 中 | **采用**：标准 HTML、颜色无损、未来可扩展其它样式 |
| `<font color="#RRGGBB">` | 生效 | 高 | 弃用：HTML4 过时标签 |
| 自定义 Markdown 扩展（如 `{red:文字}`） | 需自写扩展 + 导出同步 | 最高 | 弃用：超出本期范围，非标准语法 |

### 自定义颜色面板

| 方案 | 结论 |
|---|---|
| `qfluentwidgets.ColorDialog` | **采用**：与编辑器 Fluent 主题一致，自带取色板 / 色相滑杆 / 数值输入；在 `create_app` 装包内 `zh_CN` 翻译，避免面板文案是英文（确认/取消/编辑颜色/红绿蓝） |
| `QColorDialog` | 弃用：系统原生旧样式，与 Fluent 界面割裂 |

### 替换快捷键

| 方案 | 结论 |
|---|---|
| Ctrl+H / Ctrl+Alt+Enter（Word / VS Code 口径） | 弃用：用户明确觉得 H 别扭 |
| **Ctrl+T / Ctrl+Shift+T（替 = T）** | **采用**：中文助记，主窗口与查找窗均空闲 |
| 仅对话框内生效 | 弃用：用户要「不打开窗口的替换当前」 |

## 交互规格

### 1. 字体颜色

**入口**：工具栏格式组新增下拉按钮（`FluentIcon.PALETTE` + 下拉箭头），提示「字体颜色」。

**菜单项**（自上而下）：

| 项 | 行为 |
|---|---|
| ● 红色 `#E81123` | 给选区包上颜色标记 |
| ● 绿色 `#107C10` | 同上 |
| ● 蓝色 `#0078D4` | 同上 |
| 自定义颜色… | 打开 `ColorDialog`，取色后应用；初始值 = 上次自定义色（持久化到 QSettings `font_color`） |
| 移除颜色 | 剥掉包住选区的颜色标记，恢复纯文本 |

**应用规则**：

| 场景 | 行为 |
|---|---|
| 选区匹配 `<span style="color:#XXXXXX">…</span>`（整段被选中） | 只替换开标签里的颜色值（改变颜色，不嵌套） |
| 选区位于一个颜色标记内部（前后紧邻开/闭标签） | 改该外层标记的颜色；移除颜色时同时删掉前后标签 |
| 选区是普通文本 | 包成 `<span style="color:#RRGGBB">选中文字</span>` |
| 无选区 | InfoBar 提示「请先选中要上色的文字」，不改文档 |
| 选区跨多个段落 | 直接包裹（不做外层识别/剥离），预览按 HTML 块处理 |
| 移除颜色但选区没有颜色标记 | InfoBar 提示「选区没有颜色标记」，文档不变 |

**持久化**：仅记住上次自定义颜色（`QSettings` 键 `font_color`）；预设色固定。

**预览/导出**：无需改动。`markdown` 的 `extra` 扩展默认直通 inline HTML，`<span style>` 原样进入预览与导出的 HTML。

### 2. 替换快捷键

| 快捷键 | 作用域 | 行为 |
|---|---|---|
| `Ctrl+T` | 主窗口 + 查找窗 | 替换当前：查询为空 → 提示先查找；当前选区不是匹配项 → 先定位到下一个匹配再替换它；替换后自动跳到下一个匹配 |
| `Ctrl+Shift+T` | 主窗口 + 查找窗 | 全部替换：查询为空 → 提示；复用现有反向位置替换，InfoBar 报告数量 |
| `Ctrl+F` | 主窗口 | 打开（或聚焦）查找窗（不变） |
| `Ctrl+G` / `Ctrl+Shift+G` | 主窗口 + 查找窗 | 下一个 / 上一个（不变） |

- 查找词与替换词来自查找窗内的输入框；窗口隐藏时状态保留，因此主窗口快捷键可"不打开窗口"直接工作。
- **实现口径（实测修订）**：这四个键在主窗口以 `Qt.ApplicationShortcut` 注册，查找窗内**不注册同名副本**。
  WindowShortcut 在主窗口与查找窗各注册一份时，同一序列两处可匹配 → Qt 判为歧义、**两边都不触发**
  （原 Ctrl+G 也有此问题）。ApplicationShortcut 让一个注册点在查找窗获得焦点时照样生效。
- 遮罩对话框（帮助 / 保存确认 / 选色）期间 `_run_modal` 按原状态快照禁用并还原这些快捷键。
- 按钮 tooltip 与帮助页快捷键表同步补键位。

### 3. 去掉 AI 命名

删除：

- `mdpad/ai_naming.py`（整个文件）
- `main_window.py`：`_AiWorker`、`_ai_worker/_ai_busy/_ai_callback/_ai_tip`、`_ai_suggested_name`、`_on_ai_done`
- `save_file_as` / `export_html` 恢复为同步弹文件对话框（默认名：当前文件名 / 「无标题.md」/「导出文档.html」）
- 无用导入：`threading`、`QObject`、`pyqtSignal`、`StateToolTip`
- README 目录树中的 `ai_naming.py` 行、介绍语中的「AI 智能文件名生成」、AI key 配置段落

保留：`v1-pyqt/MDPad.pyw` 不动；`%APPDATA%\MDPad\ai_key.txt` 不删（用户文件，应用不再读取）。

### 4. 应用说明简化

- `dialogs.py` 的 `RELEASE_NOTES` → 更名 `USAGE_TEXT`，删除「版本历史」「本次更新」「v1.5.6 API key」等版本追踪内容。
- 保留结构：**MDPad 是什么** → **主要功能** → **使用提示** → **关于**（不写版本号，只写技术栈）。
- 帮助页仍为「快捷键 / 应用说明」两个标签。
- 快捷键表新增：替换当前 `Ctrl + T`、全部替换 `Ctrl + Shift + T`。
- README 的「更新记录」保留（用户选择），仅追加本次 v1.8.0 一条。

## Implementation Plan（增量切片）

1. **`mdpad/colors.py`（新）**
   - `PRESET_COLORS`、`wrap_colored(text, color)`、`unwrap_colored(text)`、`recolor_wrapped(text, color)`
   - `span_context(block_text, start, end)` → 返回外层颜色标记范围（纯函数，便于离线测试）
   - `swatch_icon(color, size=16)`：`QPainter` 画圆角色块，供菜单项图标
2. **`mdpad/main_window.py`**
   - 工具栏 `DropDownToolButton`（PALETTE）+ `RoundMenu`：三个预设色（色块图标）+ 分隔线 + 自定义 + 移除
   - `apply_font_color(color)` / `remove_font_color()`：单段落用上面的纯函数；跨段落直接包裹
   - 自定义色用 `ColorDialog`，结果写入 `QSettings("font_color")`
   - 新增主窗口 `QShortcut`：`Ctrl+T` → `replace_current_windowless`、`Ctrl+Shift+T` → `replace_all_windowless`
3. **`mdpad/search.py`**
   - `_find` 返回是否命中；`replace_current` 改为「无匹配选中项时先定位下一个匹配再替换」，按钮与快捷键同语义
   - 对话框加 `Ctrl+T` / `Ctrl+Shift+T` QShortcut；按钮 tooltip 补键位
4. **删 AI**：删模块、清主窗口、README 对应段落
5. **`mdpad/dialogs.py`**：`USAGE_TEXT` 重写、快捷键表补两项、去掉 `__version__` 依赖
6. **版本**：`__version__` → `1.8.0`；README 更新记录追加一条
7. **验证**：见下

## Edge Cases

| 场景 | 行为 |
|---|---|
| 选中文本含换行 | 允许包裹；预览按 HTML 块渲染（可能不再解析内部 Markdown），不阻断 |
| 选区含未闭合的 HTML 标签 | 原样包裹，不尝试修复 |
| 自定义颜色后取消对话框 | 不改颜色，不写持久化 |
| 颜色菜单在预览模式下点击 | 仍以编辑器选区为准；无选区给提示 |
| 查找窗从未打开过，按 Ctrl+T | 查找词为空 → InfoBar 提示「请先用 Ctrl+F 输入查找内容」 |
| 全部替换时替换词为空 | 视为删除匹配，与对话框按钮一致 |
| Ctrl+T 替换到文档末尾 | 替换后 find_next 循环回开头（现有循环语义） |

## Verification / Acceptance

**纯逻辑（offscreen / 无 GUI）**

- `wrap_colored("abc", "#E81123")` → `<span style="color:#E81123">abc</span>`
- 已包裹文本 `wrap_colored` 只改颜色值，不嵌套
- `unwrap_colored` 对包裹文本返回原文；对普通文本返回 `None`
- `span_context`：选区在标记内、整段选中、普通选区三种判定正确

**真实窗口（本机真平台，QTimer 自动关闭）**

- 工具栏按钮存在、菜单 3 色 + 自定义 + 移除齐全
- 选中「hello」→ 触发红色动作 → 文档变为 `<span style="color:#E81123">hello</span>`
- 再选中内部文本 → 触发蓝色 → 外层颜色值变为 `#0078D4`（不嵌套）
- 移除颜色 → 恢复 `hello`
- `Ctrl+T`：填好查找/替换词 → 选中匹配 → 按键 → 替换并跳到下一个
- `Ctrl+Shift+T`：全部替换数量与文档内容正确
- 帮助页「应用说明」不含「版本历史 / 本次更新」，快捷键表含两项新键
- 另存为 / 导出不再出现转圈提示，直接弹文件对话框（用函数级断言或人工确认）
- `python -m compileall mdpad` 通过；应用可启动
