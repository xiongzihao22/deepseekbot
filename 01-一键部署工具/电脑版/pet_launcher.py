# -*- coding: utf-8 -*-
"""
深海小鲸 · 桌宠守护进程（pet_launcher）

为什么需要它：
    dsh-pet 是 Electron 应用，若由 AstrBot 的 Python 进程直接拉起，
    子进程拿不到可用的桌面环境，会出现"有进程、无窗口"的情况。
    本守护进程由桌面（双击 .bat / 随 AstrBot 启动）拉起，具备完整桌面会话，
    因此能正常把桌宠窗口创建出来。

用法：
    双击「启动桌宠守护.bat」（或由 启动AstrBot.bat 自动带起，窗口最小化）
    之后 QQ 里让好感度到 60 说"愿意"，或发 /桌宠，
    intimacy 插件会 POST http://127.0.0.1:5288/launch 让它把桌宠拉起来。

接口：
    POST /launch   -> 启动桌宠（已在运行则直接返回 ok）
    GET  /status   -> {"running": true/false, "exe": "..."}
"""

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 5288
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))  # ...\deepseekbot

_LOG_LOCK = threading.Lock()
_LOG_PATH = os.path.join(os.environ.get("TEMP", HERE), "pet_launcher.log")


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with _LOG_LOCK:
            with open(_LOG_PATH, "a", encoding="utf-8", errors="ignore") as f:
                f.write(line + "\n")
    except Exception:
        pass


def find_pet_exe() -> str | None:
    env = os.environ.get("DSH_PET_EXE", "")
    if env and os.path.isfile(env):
        return env

    roots = [
        os.path.join(PROJECT_ROOT, "pet"),
        os.path.join(HERE, "pet"),
        os.path.join(os.path.expanduser("~"), ".dsh", "dsh-pet"),
        os.path.join(os.path.expanduser("~"), "dsh-pet"),
    ]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if "dsh-pet.exe" in files:
                return os.path.join(dirpath, "dsh-pet.exe")
    return None


def pet_pids() -> set:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq dsh-pet.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="gbk", errors="ignore",
            timeout=8, creationflags=0x08000000,
        )
        pids = set()
        for line in (out.stdout or "").splitlines():
            parts = [x.strip().strip('"') for x in line.split(",")]
            if len(parts) >= 2 and parts[1].isdigit():
                pids.add(int(parts[1]))
        return pids
    except Exception:
        return set()


def pet_has_window() -> bool:
    pids = pet_pids()
    if not pids:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        hit = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _cb(hwnd, _lparam):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and user32.IsWindowVisible(hwnd):
                hit.append(hwnd)
            return True

        user32.EnumWindows(_cb, 0)
        return bool(hit)
    except Exception:
        return True


def kill_pet() -> None:
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "dsh-pet.exe"],
            capture_output=True, text=True, encoding="gbk", errors="ignore",
            timeout=10, creationflags=0x08000000,
        )
    except Exception:
        pass


def launch() -> tuple[bool, str]:
    if pet_has_window():
        return True, "already-running"

    if pet_pids():
        log("发现无窗口的残留进程，清理后重试")
        kill_pet()
        time.sleep(1.2)

    exe = find_pet_exe()
    if not exe:
        log("未找到 dsh-pet.exe")
        return False, "dsh-pet.exe not found"

    env = {k: v for k, v in os.environ.items()
           if k not in ("ELECTRON_RUN_AS_NODE", "NODE_OPTIONS", "CODEBUDDY_NODE_BIN")}
    cwd = os.path.dirname(exe)

    try:
        p = subprocess.Popen(
            [exe, "--disable-gpu", "--no-sandbox"],
            cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        log(f"已拉起桌宠 pid={p.pid} exe={exe}")
    except Exception as e:  # noqa: BLE001
        log(f"启动异常: {e}")
        return False, str(e)

    for _ in range(25):
        time.sleep(1)
        if pet_has_window():
            log("桌宠窗口已出现")
            return True, "started"

    log("启动超时：未能创建窗口")
    return False, "no-window"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/status"):
            self._send(200, {"running": pet_has_window(), "exe": find_pet_exe()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/launch"):
            ok, msg = launch()
            self._send(200 if ok else 500, {"ok": ok, "msg": msg})
        elif self.path.startswith("/stop"):
            kill_pet()
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, *_args):  # 静默访问日志
        pass


def main() -> None:
    os.environ.pop("ELECTRON_RUN_AS_NODE", None)
    os.environ.pop("NODE_OPTIONS", None)
    log(f"守护进程启动，端口 {PORT}，项目根 {PROJECT_ROOT}")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("收到中断，退出")


if __name__ == "__main__":
    main()
