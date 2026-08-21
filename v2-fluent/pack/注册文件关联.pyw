"""注册 .md / .markdown / .txt 文件关联到 MDPad.exe（用户级，无需管理员）。

用法：
    双击运行（推荐），或命令行：python 注册文件关联.pyw

说明：
    在 HKCU\\Software\\Classes 下注册，只影响当前用户，不写系统注册表。
    注册后双击 .md 文件会直接用 MDPad 打开，不再弹"打开方式"。
"""
import ctypes
import os
import sys
import winreg

EXTS = (".md", ".markdown", ".txt")
PROG_ID = "MDPad.md"


def _set_value(key, name, value):
    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def register(exe_path):
    root = winreg.HKEY_CURRENT_USER
    base = r"Software\Classes"

    # 1) 扩展名 → ProgID
    for ext in EXTS:
        with winreg.CreateKey(root, rf"{base}\{ext}") as k:
            _set_value(k, "", PROG_ID)
        # 若系统已有默认关联，覆盖为用户级（HKCU 优先级高于 HKLM）
        with winreg.CreateKey(root, rf"{base}\{ext}\OpenWithProgids") as k:
            _set_value(k, PROG_ID, "")

    # 2) ProgID 定义
    with winreg.CreateKey(root, rf"{base}\{PROG_ID}") as k:
        _set_value(k, "", "MDPad Markdown 文档")
    with winreg.CreateKey(root, rf"{base}\{PROG_ID}\DefaultIcon") as k:
        _set_value(k, "", f'"{exe_path}",0')
    with winreg.CreateKey(root, rf"{base}\{PROG_ID}\shell\open\command") as k:
        _set_value(k, "", f'"{exe_path}" "%1"')

    # 3) 通知 Shell 刷新关联
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)


def main():
    exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "MDPad.exe")
    if len(sys.argv) > 1:
        exe = sys.argv[1]
    if not os.path.exists(exe):
        ctypes.windll.user32.MessageBoxW(
            0,
            f"找不到 MDPad.exe：\n{exe}\n\n请确认打包目录 dist 存在，或把 exe 路径作为参数传入。",
            "注册文件关联失败", 0x10,
        )
        return 1
    register(os.path.abspath(exe))
    ctypes.windll.user32.MessageBoxW(
        0,
        f"已注册文件关联：\n{', '.join(EXTS)} → MDPad.exe\n\n"
        f"exe 路径：{os.path.abspath(exe)}\n\n"
        "现在双击 .md 文件即可用 MDPad 打开。",
        "注册完成", 0x40,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
