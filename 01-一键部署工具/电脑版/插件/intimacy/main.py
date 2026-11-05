# -*- coding: utf-8 -*-
"""
深海小鲸 · 好感度养成插件（结构化存储 + 桌宠解锁）

功能：
1. 解析 DeepSeek 回复末尾的 [INTIMACY:±N:reason] 标记，把好感度写入 AstrBot 存储（结构化，不漂移）
2. 提供 /好感度、/状态卡、/桌宠 查询指令
3. 冷落衰减（超过 24h 未互动，按天 -1）
4. 主人机制：只有主人能突破 39 分，其他人锁死
5. 桌宠解锁：好感度首次达到 60 时，她主动问"想不想让我来到你身边"；
   用户回复"愿意/好啊"等即解锁。未达 60 不会提桌宠。

部署方式：把本目录（intimacy）整体放到 AstrBot 的 data/plugins/ 下，重启 AstrBot 即可。
注意：OWNER_QQ 由一键部署脚本自动替换为用户的 QQ 号。
"""

import asyncio
import os
import re
import subprocess
import time

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api.provider import LLMResponse
from astrbot.api import logger

# ============ 部署时由脚本替换 ============
OWNER_QQ = "100000000"   # 主人 QQ 号（一键脚本会替换这里）
# ========================================

MAX_OTHERS = 39          # 非主人好感度上限
UNLOCK_THRESHOLD = 60    # 桌宠解锁好感度门槛（"亲近"档）
TAG_RE = re.compile(r"\[INTIMACY:([+-]?\d+)(?::([a-zA-Z_]+))?\]")
# 用户同意"让她来身边"的回复关键词（仅在"她刚问过"时生效）
# 用「短回复整体匹配」或「明确包含同意词」两种方式，避免"我想吃饭"这类误触发
AGREE_RE = re.compile(
    r"^\s*(愿意|好啊|好呀|可以|可以呀|来吧|同意|当然|嗯+|行)\s*[呀啊吧呢嘛。!！~～]*\s*$"
    r"|愿意|想让你来|想让你过来|来吧"
)


class IntimacyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    # ---------- 桌宠进程管理（"她来到你身边"= 真的把 dsh-pet 拉起来） ----------
    @staticmethod
    def _pet_pids() -> set:
        """当前 dsh-pet.exe 的进程 ID 集合。"""
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq dsh-pet.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=8,
                encoding="gbk", errors="ignore",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            pids = set()
            for line in (out.stdout or "").splitlines():
                parts = [x.strip().strip('"') for x in line.split(",")]
                if len(parts) >= 2 and parts[1].isdigit():
                    pids.add(int(parts[1]))
            return pids
        except Exception:
            return set()

    @classmethod
    def _pet_has_window(cls) -> bool:
        """桌宠是否真的有可见窗口（只有进程没有窗口 = 起崩了的僵尸进程）。"""
        pids = cls._pet_pids()
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
            # 拿不到窗口信息时，退化判定为"有进程就算活着"
            return True

    @classmethod
    def _pet_running(cls) -> bool:
        return cls._pet_has_window()

    @staticmethod
    def _kill_pet() -> None:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "dsh-pet.exe"],
                capture_output=True, text=True, timeout=10,
                encoding="gbk", errors="ignore",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    @staticmethod
    def _find_pet_exe():
        """在常见位置找 dsh-pet.exe（可用环境变量 DSH_PET_EXE 覆盖）。"""
        env = os.environ.get("DSH_PET_EXE", "")
        if env and os.path.isfile(env):
            return env

        roots = []
        # 1) 从 AstrBot 程序目录反推项目根（部署时 dsh-pet 通常和 AstrBot 同级）
        try:
            import astrbot as _astrbot_pkg

            cur = os.path.dirname(os.path.abspath(_astrbot_pkg.__file__))
            for _ in range(7):
                roots.append(os.path.join(cur, "pet"))
                cur = os.path.dirname(cur)
        except Exception:
            pass

        # 2) 项目根下的 pet/（插件往上 4~6 层）
        cur = os.path.dirname(os.path.abspath(__file__))
        for _ in range(6):
            roots.append(os.path.join(cur, "pet"))
            cur = os.path.dirname(cur)
        # 3) 用户主目录常见位置
        home = os.path.expanduser("~")
        roots += [
            os.path.join(home, ".dsh", "dsh-pet"),
            os.path.join(home, "dsh-pet"),
            os.path.join(home, "Desktop", "dsh-pet"),
        ]

        for root in roots:
            if not os.path.isdir(root):
                continue
            for dirpath, _dirs, files in os.walk(root):
                if "dsh-pet.exe" in files:
                    return os.path.join(dirpath, "dsh-pet.exe")
        return None

    @staticmethod
    def _launch_via_daemon(timeout: int = 40) -> bool:
        """优先请桌宠守护进程（pet_launcher.py）拉起桌宠 —— 它具备完整桌面会话。

        守护进程未启动时返回 False，调用方会回退到本地直接启动。
        """
        import json
        import urllib.request

        try:
            req = urllib.request.Request(
                "http://127.0.0.1:5288/launch",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            return bool(data.get("ok"))
        except Exception as e:  # noqa: BLE001
            logger.info(f"[intimacy] 守护进程不可用（{e}），回退本地启动")
            return False

    async def _ensure_pet_started(self) -> tuple[bool, str]:
        """确保桌宠在跑（有真实窗口）。返回 (是否成功, 给用户看的提示)。"""
        if await asyncio.to_thread(self._pet_running):
            return True, ""

        # 路线 1：请守护进程拉起（最可靠，它在用户桌面会话里）
        if await asyncio.to_thread(self._launch_via_daemon):
            if await asyncio.to_thread(self._pet_running):
                logger.info("[intimacy] 桌宠已由守护进程拉起")
                return True, ""

        # 有进程但没窗口 = 起崩了的僵尸，先清掉（否则会占单实例锁，后续永远起不来）
        if await asyncio.to_thread(self._pet_pids):
            logger.warning("[intimacy] 发现无窗口的 dsh-pet 残留进程，清理后重试")
            await asyncio.to_thread(self._kill_pet)
            await asyncio.sleep(1.2)

        exe = self._find_pet_exe()
        if not exe:
            return False, (
                "（桌宠还没装好，她游不过来……\n"
                "把 dsh-pet 放到项目的 pet 文件夹里，再跟她说一次「愿意」）"
            )

        # 关键：dsh-pet 是 Electron 应用
        #   1) 必须清掉 ELECTRON_RUN_AS_NODE / NODE_OPTIONS，否则它会以纯 Node 模式跑（有进程、无窗口）
        #   2) 加 --disable-gpu --no-sandbox，避免在部分环境下卡在 GPU 初始化
        env = {
            k: v for k, v in os.environ.items()
            if k not in ("ELECTRON_RUN_AS_NODE", "NODE_OPTIONS", "CODEBUDDY_NODE_BIN")
        }
        cwd = os.path.dirname(exe)
        import tempfile

        out_path = os.path.join(tempfile.gettempdir(), "dsh-pet-launch.log")
        args = [exe, "--disable-gpu", "--no-sandbox"]

        def _try_direct():
            f = open(out_path, "w", encoding="utf-8", errors="ignore")
            p = subprocess.Popen(
                args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                stdout=f, stderr=subprocess.STDOUT, close_fds=True,
            )
            return p.pid

        def _try_cmd_start():
            p = subprocess.Popen(
                ["cmd", "/c", "start", "", exe, "--disable-gpu", "--no-sandbox"],
                cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
            return p.pid

        def _read_out():
            try:
                with open(out_path, encoding="utf-8", errors="ignore") as f:
                    return f.read()[-600:].replace("\n", " | ")
            except Exception:
                return "(无输出)"

        for name, fn in (("direct", _try_direct), ("cmd_start", _try_cmd_start)):
            try:
                pid = await asyncio.to_thread(fn)
                logger.info(f"[intimacy] 尝试启动桌宠[{name}] pid={pid}")
            except Exception as e:  # noqa: BLE001
                logger.error(f"[intimacy] 启动方式[{name}]异常: {e}")
                continue
            for _ in range(12):
                await asyncio.sleep(1.0)
                if await asyncio.to_thread(self._pet_running):
                    logger.info(f"[intimacy] 桌宠已启动[{name}]: {exe}")
                    return True, ""
            pids = await asyncio.to_thread(self._pet_pids)
            logger.error(
                f"[intimacy] 方式[{name}]失败：残留进程={pids}，输出={_read_out()}"
            )
            await asyncio.to_thread(self._kill_pet)
            await asyncio.sleep(1.0)

        logger.error("[intimacy] 桌宠启动失败（所有方式都未能创建窗口）")
        return False, (
            "（她想过来，可门好像卡住了……\n"
            "你手动双击一下项目里的 dsh-pet.exe，她就能出来）"
        )


    # ---------- 存储（AstrBot 4.29 插件基类内置 KV，底层 SQLite） ----------
    def _key(self, uid: str) -> str:
        return f"intimacy:{uid}"

    async def _load(self, uid: str) -> dict:
        data = await self.get_kv_data(self._key(uid), None)
        if not data:
            # 初始状态：好感度 0、投喂 0 次、从未互动过 —— 对任何人都"不认识"
            data = {"intimacy": 0, "feed_count": 0, "last_interact": time.time()}
        return data

    async def _save(self, uid: str, data: dict):
        await self.put_kv_data(self._key(uid), data)

    # ---------- 好感度增减（含冷落衰减 + 主人锁） ----------
    async def apply_delta(self, uid: str, delta: int, reason: str = ""):
        data = await self._load(uid)
        old = data["intimacy"]
        now = time.time()

        # 冷落衰减：超过 24h 未互动，每多一天 -1
        days = (now - data.get("last_interact", now)) / 86400
        if days >= 1:
            data["intimacy"] -= int(days)

        # 应用增减，clamp 到 [0, 100]
        data["intimacy"] = max(0, min(100, data["intimacy"] + delta))

        # 主人锁：非主人永远到不了"亲近"以上
        if uid != OWNER_QQ:
            data["intimacy"] = min(data["intimacy"], MAX_OTHERS)

        data["last_interact"] = now
        if reason == "feed":
            data["feed_count"] = data.get("feed_count", 0) + 1

        await self._save(uid, data)
        logger.info(f"[intimacy] {uid} {delta:+d} ({reason or 'chat'}) {old} -> {data['intimacy']}")
        return old, data["intimacy"], data

    # ---------- 解析 AI 回复里的结构化标记 + 桌宠解锁询问 ----------
    @filter.on_llm_response()
    async def on_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
        uid = str(event.get_sender_id())
        text = resp.completion_text or ""
        m = TAG_RE.search(text)
        if not m:
            return
        delta = int(m.group(1))
        reason = m.group(2) or ""
        # 剥掉标记，用户看不到
        resp.completion_text = TAG_RE.sub("", text).strip()
        old, new, data = await self.apply_delta(uid, delta, reason)

        # 好感度首次跨过 60 → 她主动问"想不想让我来到你身边"
        if (old < UNLOCK_THRESHOLD <= new
                and not data.get("pet_asked")
                and not data.get("pet_unlocked")):
            data["pet_asked"] = True
            data["pet_asked_at"] = time.time()
            await self._save(uid, data)
            suffix = ("\n\n（她忽然安静下来，声音很轻）那个……我好像，可以离开深海了。"
                      "你……想让我去你身边吗？")
            resp.completion_text = (resp.completion_text or "") + suffix
            logger.info(f"[intimacy] {uid} 好感度达到 {new}，触发桌宠解锁询问")

    # ---------- 用户回答"愿意" → 解锁桌宠 ----------
    @filter.regex(AGREE_RE)
    async def on_pet_agree(self, event: AstrMessageEvent):
        uid = str(event.get_sender_id())
        data = await self._load(uid)
        # 只有"她刚问过、还没解锁"时才接管这条消息
        if not (data.get("pet_asked") and not data.get("pet_unlocked")):
            return
        data["pet_unlocked"] = True
        data["pet_asked"] = False
        data["last_interact"] = time.time()
        await self._save(uid, data)
        yield event.plain_result("……那我来了。\n\n（她转身，往你的方向游过来）")
        ok, hint = await self._ensure_pet_started()
        logger.info(f"[intimacy] {uid} 桌宠已解锁，启动结果={ok}")

        if ok:
            yield event.plain_result("（她出现在你的桌面上，从今往后，关掉 QQ 也能看见她）")
        else:
            yield event.plain_result(hint)

    # ---------- 查询指令 ----------
    @filter.command("好感度")
    async def cmd_intimacy(self, event: AstrMessageEvent):
        uid = str(event.get_sender_id())
        data = await self._load(uid)
        yield event.plain_result(f"（小声）我对你的好感度是 {data['intimacy']} / 100")

    @filter.command("状态卡")
    async def cmd_status(self, event: AstrMessageEvent):
        uid = str(event.get_sender_id())
        data = await self._load(uid)
        pet = "已解锁 🐾" if data.get("pet_unlocked") else f"未解锁（{UNLOCK_THRESHOLD} 分可解锁）"
        yield event.plain_result(
            f"【深海小鲸 · 养成状态卡】\n"
            f"好感度：{data['intimacy']} / 100\n"
            f"已投喂：{data.get('feed_count', 0)} 次\n"
            f"桌宠：{pet}"
        )

    @filter.command("桌宠")
    async def cmd_pet(self, event: AstrMessageEvent):
        uid = str(event.get_sender_id())
        data = await self._load(uid)
        cur = data["intimacy"]
        if data.get("pet_unlocked"):
            if await asyncio.to_thread(self._pet_running):
                yield event.plain_result("她已经在你的桌面上了。")
                return
            yield event.plain_result("（她点了点头，转身往你这边游……等我一下）")
            ok, hint = await self._ensure_pet_started()
            if ok:
                yield event.plain_result("到了。抬头看看你的桌面。")
            else:
                yield event.plain_result(hint)
        elif data.get("pet_asked"):
            yield event.plain_result("（小声）我……刚才问过你了。说「愿意」就行。")
        elif cur >= UNLOCK_THRESHOLD:
            yield event.plain_result("（小声）我……可以去你身边吗？说「愿意」就行。")
        else:
            yield event.plain_result(
                f"她的好感度是 {cur}，还差 {UNLOCK_THRESHOLD - cur} 才能离开深海。"
            )

    # ---------- 调试/演示指令（仅主人可用，方便快速验证解锁流程） ----------
    @filter.command("设置好感度")
    async def cmd_set_intimacy(self, event: AstrMessageEvent):
        uid = str(event.get_sender_id())
        if uid != OWNER_QQ:
            yield event.plain_result("这个只有主人能改。")
            return
        raw = (event.message_str or "").strip()
        m = re.search(r"(\d{1,3})", raw)
        if not m:
            yield event.plain_result("用法：/设置好感度 59")
            return
        val = max(0, min(100, int(m.group(1))))
        data = await self._load(uid)
        data["intimacy"] = val
        # 重置询问状态，便于反复演示解锁流程
        if val < UNLOCK_THRESHOLD:
            data["pet_asked"] = False
            data["pet_unlocked"] = False
        await self._save(uid, data)
        yield event.plain_result(
            f"好感度已设为 {val} / 100。（<{UNLOCK_THRESHOLD} 分才会重新触发「她问你要不要去你身边」）"
        )
