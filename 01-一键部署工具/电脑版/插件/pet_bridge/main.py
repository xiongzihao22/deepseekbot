# -*- coding: utf-8 -*-
"""
深海小鲸 · 桌宠联动插件（QQ 端回复 → dsh-pet 桌面气泡）

功能：
- 监听 LLM 回复（on_llm_response），把 DeepSeek 生成的回复实时推送给 dsh-pet 桌宠，
  让桌宠弹出气泡展示这条回复。
- dsh-pet 的 HTTP 服务端口是随机分配的、API 需要 x-dsh-pet-token 鉴权，
  因此本插件会自动：
    1) 从 ~/.dsh/dsh-pet/logs.txt 读取当前监听端口；
    2) 从 dsh-pet 进程环境变量 DSH_PET_SITE_URL 中提取 token。
- 桌宠未开启/接口不可用时静默降级，绝不影响 QQ 端正常回复。

部署：把本目录（pet_bridge）放到 AstrBot 的 data/plugins/ 下，重启 AstrBot。
"""

import ctypes
import os
import re
import subprocess

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api.provider import LLMResponse
from astrbot.api import logger

# ============ 可配置 ============
PET_ID = "main"                     # 桌宠 id（dsh-pet 配置里的 pets[].id）
SURFACE = "desktop"                 # desktop / web / both / any
BUBBLE_DURATION = 9000              # 气泡显示时长（毫秒）
MAX_TEXT_LEN = 240                  # 气泡文本截断长度
# ================================

DSH_PET_LOG = os.path.expanduser("~/.dsh/dsh-pet/logs.txt")
TAG_RE = re.compile(r"\[INTIMACY:[^\]]*\]")
TOKEN_RE = re.compile(r"#token=([A-Za-z0-9_-]{43})")

# 缓存（成功获取后复用，失败时重新探测）
_cache = {"port": None, "token": None}


def _get_port():
    """从 dsh-pet 日志读取本机服务端口。"""
    try:
        with open(DSH_PET_LOG, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        matches = re.findall(r"本机服务 http://127\.0\.0\.1:(\d+)", text)
        return int(matches[-1]) if matches else None
    except Exception:
        return None


def _list_pet_pids():
    """列出所有 dsh-pet.exe 的 PID。"""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq dsh-pet.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        pids = []
        for line in out.stdout.splitlines():
            parts = line.split('","')
            if len(parts) >= 2:
                try:
                    pids.append(int(parts[1].strip('"')))
                except ValueError:
                    pass
        return pids
    except Exception:
        return []


def _read_token_from_pid(pid):
    """读取指定进程环境变量 DSH_PET_SITE_URL，提取 token。"""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        h = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)  # QUERY_INFORMATION | VM_READ
        if not h:
            return None

        class PBI(ctypes.Structure):
            _fields_ = [
                ("R1", ctypes.c_void_p), ("Peb", ctypes.c_void_p),
                ("R2", ctypes.c_void_p * 2), ("Pid", ctypes.c_void_p),
                ("R3", ctypes.c_void_p),
            ]

        pbi = PBI()
        rl = ctypes.c_ulong()
        ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(rl))
        if not pbi.Peb:
            return None

        def rd(addr, size):
            buf = (ctypes.c_ubyte * size)()
            n = ctypes.c_size_t()
            if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n)):
                raise OSError("ReadProcessMemory failed")
            return bytes(buf)

        pp = int.from_bytes(rd(pbi.Peb + 0x20, 8), "little")       # PEB.ProcessParameters
        env_ptr = int.from_bytes(rd(pp + 0x80, 8), "little")        # Environment 指针
        env_size = int.from_bytes(rd(pp + 0x3F0, 8), "little")      # EnvironmentSize
        text = rd(env_ptr, min(env_size or 0, 131072)).decode("utf-16-le", "ignore")
        kernel32.CloseHandle(h)
        for line in text.split("\x00"):
            if "DSH_PET_SITE_URL=" in line:
                m = TOKEN_RE.search(line)
                if m:
                    return m.group(1)
    except Exception:
        return None
    return None


def _resolve_endpoint():
    """解析 (port, token)，带缓存与自动重探。"""
    if _cache["port"] and _cache["token"]:
        return _cache["port"], _cache["token"]
    port = _get_port()
    token = None
    for pid in _list_pet_pids():
        token = _read_token_from_pid(pid)
        if token:
            break
    if port and token:
        _cache["port"], _cache["token"] = port, token
    return port, token


class PetBridgePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.on_llm_response()
    async def on_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
        text = resp.completion_text or ""
        text = TAG_RE.sub("", text).strip()
        if not text:
            return
        if len(text) > MAX_TEXT_LEN:
            text = text[:MAX_TEXT_LEN].rstrip() + "…"
        await self._broadcast(text)

    async def _broadcast(self, text: str):
        """把回复文本写进桌宠气泡。任何异常都静默，不影响 QQ 端。"""
        try:
            port, token = _resolve_endpoint()
            if not port or not token:
                logger.debug("[pet_bridge] 未找到 dsh-pet（未开启或未就绪），跳过")
                return
            url = f"http://127.0.0.1:{port}/dsh-pet-7340/broadcast"
            params = {"pet": PET_ID, "surface": SURFACE}
            headers = {"x-dsh-pet-token": token}
            payload = {"text": text, "duration": BUBBLE_DURATION, "anim": True}
            timeout = aiohttp.ClientTimeout(total=3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, params=params, headers=headers, json=payload) as r:
                    data = await r.json()
                    if not data.get("ok"):
                        # 失败时清空缓存，下次重新探测（端口/token 可能已变）
                        _cache["port"] = _cache["token"] = None
                        logger.debug(f"[pet_bridge] 桌宠未响应: {data.get('reason')}")
        except Exception as e:  # noqa: BLE001
            _cache["port"] = _cache["token"] = None
            logger.debug(f"[pet_bridge] 推送桌宠失败（桌宠未开启时属正常）: {e}")
