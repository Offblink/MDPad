"""MDPad TUI 入口 — 终端版 Markdown 编辑器。

用法:
    python mdtui.py [文档.md]

复用 v2-fluent 里零 Qt 依赖的纯逻辑模块 (mdpad.io / mdpad.links)。
"""
import sys
from pathlib import Path

# 把 v2-fluent 加进导入路径，复用 mdpad 包里的纯逻辑模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2-fluent"))  # noqa: E402

from mdpad_tui.app import MDPadApp  # noqa: E402


def main() -> None:
    app = MDPadApp(path=sys.argv[1] if len(sys.argv) > 1 else None)
    app.run()
    # 所有退出路径的文件锁兜底释放（进程退出时 OS 也会释放，这里显式收尾）
    app.file_guard.release()


if __name__ == "__main__":
    main()
