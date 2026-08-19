"""MDPad - Fluent 版 Markdown 编辑器入口。

运行: python MDPad.pyw [文件路径]
"""
import os
import sys

# 入口位于 v2-fluent/：把本目录加入搜索路径，使 `import mdpad` 可用
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mdpad.app import run

if __name__ == "__main__":
    sys.exit(run(sys.argv))
