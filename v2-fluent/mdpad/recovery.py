"""自动恢复日志：把未保存的草稿按文件写进 %APPDATA%\\MDPad\\recovery.json。

强杀、断电、崩溃都杀不死未保存的修改：编辑停顿后写一次草稿，下次打开同一个
文件时弹恢复框（恢复 / 丢弃 / 稍后）。按文件分条（未命名文档自成一类），
保存或改回与磁盘一致时只清自己那条——别的文件的草稿不动。
"""
import json
import os
import tempfile
from pathlib import Path

UNTITLED_KEY = "<untitled>"


def recovery_file_path():
    """草稿文件路径（%APPDATA%\\MDPad\\recovery.json）。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "MDPad" / "recovery.json"


def file_key(file_path):
    """草稿键：绝对路径归一化（大小写、斜杠差异视为同一个文件）；无路径 = 未命名。"""
    if not file_path:
        return UNTITLED_KEY
    return os.path.normcase(os.path.abspath(file_path))


def _read_all():
    """读整份草稿表；文件缺失或损坏（写到一半被强杀）都当作空表。"""
    path = recovery_file_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_all(data):
    """整份重写（先写临时文件再替换，断电最多丢这一次写入，不会把文件写坏）。"""
    path = recovery_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not data:
        try:
            path.unlink()
        except OSError:
            pass
        return
    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix="recovery.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp_name, path)
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def get_text(key):
    """取某个文件的草稿内容；没有返回 None。"""
    entry = _read_all().get(key)
    return entry.get("text") if isinstance(entry, dict) else None


def put_text(key, text):
    """写入/更新草稿。"""
    data = _read_all()
    data[key] = {"text": text}
    _write_all(data)


def drop(key):
    """清掉某个文件的草稿（保存成功、或用户明确丢弃时）。"""
    data = _read_all()
    if key in data:
        del data[key]
        _write_all(data)
