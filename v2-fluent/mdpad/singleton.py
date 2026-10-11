"""单例：同一个文件只留一个窗口（不同文件仍然各开各的窗口）。

判定键与草稿日志同一口径（归一化绝对路径；未命名文档自成一类）。仲裁方式是
本地回环 socket：主实例监听一个随机端口并把端口号写进 %APPDATA%\\MDPad\\
instance-<键哈希>.json，第二个实例读文件、连上去发一条唤醒请求就退出——
被挡下的那次**不建窗口、也不新建进程内的任何 Qt 窗口**。

不用 QLocalServer 的原因：那条路要先 import QtWebEngine（Qt 要求 WebEngine 必须
早于 QApplication），第二实例为此白等近 2 秒；这里客户端侧只用标准库 socket。
"""
import hashlib
import json
import os
import socket
import threading
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal

_ACTIVATE = b"MDPad-activate"


def _state_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "MDPad"


def _state_file(key):
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return _state_dir() / f"instance-{digest}.json"


def notify_existing(key, timeout=0.4):
    """已有窗口在编辑这个文件时唤醒它并返回 True；否则返回 False。"""
    try:
        port = int(json.loads(_state_file(key).read_text(encoding="utf-8"))["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
            sock.sendall(_ACTIVATE)
            sock.settimeout(timeout)
            return sock.recv(2) == b"ok"
    except OSError:
        # 端口文件是上次崩溃留下的陈旧记录：当作没有实例
        return False


class InstanceServer(QObject):
    """主实例的仲裁端：后台线程收唤醒请求，经 Qt 信号送回主线程。"""

    activated = pyqtSignal()

    def __init__(self, key):
        super().__init__()
        self._key = key
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(4)
        self._port = self._sock.getsockname()[1]
        self._closed = False
        self._write_state()
        threading.Thread(target=self._serve, daemon=True).start()

    def _write_state(self):
        path = _state_file(self._key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"port": self._port}), encoding="utf-8")

    def _serve(self):
        while not self._closed:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            with conn:
                try:
                    data = conn.recv(64)
                except OSError:
                    continue
                if data.startswith(_ACTIVATE):
                    conn.sendall(b"ok")
                    self.activated.emit()

    def close(self):
        self._closed = True
        try:
            self._sock.close()
        except OSError:
            pass
        try:
            _state_file(self._key).unlink()
        except OSError:
            pass
