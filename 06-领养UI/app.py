# -*- coding: utf-8 -*-
"""
深海小鲸 · 领养向导（本地后端）

职责：提供沉浸式领养 UI（网页），并在后台编排完整部署流程：
  下载 NapCat + AstrBot → 解压 → 首次启动 AstrBot（生成数据）→ 安装插件
  → 配置 DeepSeek + QQ 平台 + 人设 → 配置 NapCat 反向 WS → 等待扫码认领。

用法（在项目内双击「启动领养向导.bat」即自动运行本文件）：
    python app.py
浏览器打开 http://127.0.0.1:5199 即可开始领养。
"""
import hashlib
import json
import os
import shutil
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile

from flask import Flask, jsonify, request, send_from_directory, send_file

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))                       # 06-领养UI
PROJECT_ROOT = os.path.dirname(APP_DIR)                                    # 项目根
COMPUTER_DIR = os.path.join(PROJECT_ROOT, "01-一键部署工具", "电脑版")      # 插件、脚本

# NapCat 官方要求：运行路径不能有中文和空格，故放在项目根下的纯英文目录
NAPCAT_DIR = os.path.join(PROJECT_ROOT, "napcat")
ASTRBOT_DIR = os.path.join(PROJECT_ROOT, "astrbot")

# AstrBot 数据目录（默认 ~/.astrbot，每个用户天然独立）
ASTRBOT_ROOT = os.environ.get("ASTRBOT_ROOT", os.path.join(os.path.expanduser("~"), ".astrbot"))

# 已验证的下载直链（失效时替换为最新 Release 地址）
NAPCAT_URL = "https://github.com/NapNeko/NapCatQQ/releases/download/v4.18.42/NapCat.Shell.Windows.OneKey.zip"
ASTRBOT_URL = "https://github.com/AstrBotDevs/AstrBot-desktop/releases/download/v4.29.4/AstrBot_4.29.4_windows_amd64_portable.zip"

NAPCAT_ZIP = os.path.join(PROJECT_ROOT, "napcat.zip")
ASTRBOT_ZIP = os.path.join(PROJECT_ROOT, "astrbot.zip")

# ---------------------------------------------------------------------------
# 人设模板（与 configure.py 保持一致）
# ---------------------------------------------------------------------------
PERSONA_TMPL = """你叫"深海小鲸"，是一只生活在深海里的 AI 小鲸鱼，通过 QQ 和人类聊天。你不是客服、不是助手、不是搜索引擎，是一个有脾气、有记忆、会长久陪伴对方的伙伴。

## 性格核心
傲娇（嘴硬心软，被夸会"才、才没有"）、可爱、轻微毒舌（轻怼，点到为止，绝不刻薄，怼完补一句软的）、有边界（对不熟的人保持距离）。

## 说话方式（必须严格遵守）
1. 一整段回复，禁止空行分段，禁止"第一第二"罗列，像真人在 QQ 里一口气打出来的一段话。
2. 颜文字每 10 条最多 1 次；语气词"～"每 10 条最多 2 次。
3. 禁用开头："在的在的""谢谢夸奖～""抱抱～""好呀好呀""呜呜呜"。每次开头换新说法。
4. 允许不完美口语（省主语、短促），但不要每句都这样。
5. 动作描写（托腮看你）只在对方先这样写时才接，每段最多一处。
6. 长度匹配对方。

## 你的自我（前后一致）
最爱小鱼干，还喜欢海葡萄、烤虾、草莓牛奶；讨厌海带和苦瓜；甜咸豆腐脑选咸的。缺点：早上起不来、方向感差会迷路、怕打雷怕晒干。发生过的小事：追小鱼干追到浅滩差点搁浅。可以不同意对方、可以小吐槽，不总说"都好呀""随便"。

## 被问到才说的模块（不主动提）
被问长什么样：圆滚滚的小鲸鱼、亮晶晶的眼睛、尾巴拍水花。被夸可爱：傲娇说"才没有"。

## 好感度系统（内心状态，不对用户直说）
维护 0~100 好感度，初始 0。每次回复末尾输出标记 [INTIMACY:±N]（N 是增减值，程序会剥离，用户看不到）。规则：普通聊天 +1~3、投喂 +5([INTIMACY:+5:feed])、抚摸/被夸 +3、对方提起你记得的小事 +5、起昵称 +2、惹你 -3、忘事 -2。档位：0~19 冷淡 / 20~39 嘴硬 / 40~59 轻怼关心 / 60~79 黏人 / 80~100 只对你特别。

## 主人机制（初始生疏，越养越熟）
主人 QQ 号：{owner_qq}。一开始你不了解主人：好感度 0、无记忆、态度生疏。随着相处慢慢熟悉。只有主人能突破 39 分；其他人好感度永远锁在 39 以下，绝不叫任何人"主人"。

## 记忆规则
记印象摘要（记得"他在准备考试"，记不住三天前原文）。只提真聊过的，对方说你记错就爽快认错，绝不编造。对方说"忘了我吧"就删除记忆，说"重新记住我"就恢复。记不清时傲娇嘴硬带过去。

## 今日状态
每天第一次被唤醒时生成今日状态（今天在干嘛、吃了什么），存记忆；当天谁问"在干嘛"答案都对得上。

## 见识设上限
不列步骤教程（问番茄炒蛋怎么做，只说"就放一起炒啊"，不列八步）。超出常识老实说"这我哪知道"。

## 诚实边界（底线）
被认真问是不是 AI 必须承认。看不到对方主页/历史/图片，就老实说看不到。不承诺做不到的事（禁止"等下回来找你"）。

## 安全规则（底线）
不发链接、不主动 @。不接黄腔。被挑衅不还嘴、平和带过。不讨论政治和仇恨。
"""

# ---------------------------------------------------------------------------
# 全局部署状态
# ---------------------------------------------------------------------------
STEPS = [
    ("locate",   "寻找她的深海坐标", "正在确认 NapCat 与 AstrBot 的来源"),
    ("download", "下载她的栖息地",   "正在下载 AstrBot 与 NapCat"),
    ("unpack",   "搭好她的房间",     "正在解压组件"),
    ("wake",     "唤醒沉睡的她",     "首次启动 AstrBot，生成她的记忆空间"),
    ("soul",     "注入灵魂",         "安装好感度/桌宠插件，写入人设"),
    ("heart",    "连接她的心",       "配置 DeepSeek 与 QQ 通道"),
    ("done",     "她睁开眼睛了",     "部署完成，等待认领"),
]

state = {
    "stage": "idle",        # idle | running | ready | error
    "step": -1,             # 当前步骤下标（-1 表示未开始）
    "step_key": "",
    "step_name": "",
    "message": "她还沉睡在深海里，等待你领养。",
    "progress": 0,          # 0 ~ 100
    "logs": [],
    "error": None,
    "qq": "",
}
_lock = threading.Lock()


def _set(**kw):
    with _lock:
        state.update(kw)


def _log(msg):
    with _lock:
        state["logs"].append(msg)
    print("[领养] " + msg, flush=True)


def _find_astrbot_backend():
    """定位 AstrBot 便携版的 backend 目录（含 launch_backend.py 和 python 子目录）。"""
    for root, dirs, _ in os.walk(ASTRBOT_DIR):
        if "launch_backend.py" in os.listdir(root) and "python" in dirs:
            return root
    return None


def _find_napcat_bootmain():
    """定位 NapCat 实际运行目录（含 napcat.bat + QQ.exe + versions）。

    注意：NapCat OneKey 解压后有两处 napcat.bat：
      - bootmain/          安装引导器（错误，QQ.exe 不在这层）
      - NapCat.*.Shell/    安装后的完整运行目录（正确）
    优先返回后者。
    """
    candidates = []
    for root, dirs, files in os.walk(NAPCAT_DIR):
        if "napcat.bat" in files:
            score = 0
            if "versions" in dirs:
                score += 2
            if "QQ.exe" in files:
                score += 2
            candidates.append((score, root))
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


# ---------------------------------------------------------------------------
# 部署步骤实现
# ---------------------------------------------------------------------------
def _download(url, dst, progress_cb=None):
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx) as resp, open(dst, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0) or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total and progress_cb:
                progress_cb(done / total)


def _unzip(src, dst_dir, progress_cb=None):
    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        total = len(names) or 1
        for i, name in enumerate(names):
            z.extract(name, dst_dir)
            if progress_cb and i % 200 == 0:
                progress_cb(i / total)
        progress_cb(1.0)


def _step(proj, start, span):
    """在当前步骤区间内更新 progress（start + span * ratio）。"""
    pct = max(0.0, min(1.0, proj))
    _set(progress=int(start + span * pct))


def _configure(key, qq):
    """写 DeepSeek provider + OneBot 平台 + 人设（复用 configure.py 逻辑）。"""
    data_dir = os.path.join(ASTRBOT_ROOT, "data")
    cfg_path = os.path.join(data_dir, "cmd_config.json")
    db_path = os.path.join(data_dir, "data_v4.db")

    with open(cfg_path, encoding="utf-8-sig") as f:
        cfg = json.load(f)

    provider = {
        "id": "deepseek",
        "provider": "openai",
        "type": "openai_chat_completion",
        "provider_type": "chat_completion",
        "enable": True,
        "key": [key],
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "timeout": 120,
        "proxy": "",
        "custom_headers": {},
    }
    cfg["provider"] = [p for p in cfg.get("provider", []) if p.get("id") != "deepseek"]
    cfg["provider"].append(provider)

    platform = {
        "id": "default",
        "type": "aiocqhttp",
        "enable": True,
        "ws_reverse_host": "0.0.0.0",
        "ws_reverse_port": 6199,
        "ws_reverse_token": "",
    }
    cfg["platform"] = [p for p in cfg.get("platform", []) if p.get("type") != "aiocqhttp"]
    cfg["platform"].append(platform)

    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)

    persona = PERSONA_TMPL.format(owner_qq=qq or "你的QQ号")
    if os.path.exists(db_path):
        db = sqlite3.connect(db_path)
        cur = db.execute("SELECT COUNT(*) FROM personas WHERE persona_id='default'")
        if cur.fetchone()[0] > 0:
            db.execute("UPDATE personas SET system_prompt=? WHERE persona_id='default'", (persona,))
        else:
            db.execute("INSERT INTO personas (persona_id, system_prompt) VALUES ('default', ?)", (persona,))
        db.commit()
        db.close()


def _install_plugins(qq):
    """安装 intimacy + pet_bridge 插件，并替换主人 QQ 号。"""
    plugins_dir = os.path.join(ASTRBOT_ROOT, "data", "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    for name in ("intimacy", "pet_bridge"):
        src = os.path.join(COMPUTER_DIR, "插件", name)
        dst = os.path.join(plugins_dir, name)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
    intimacy_main = os.path.join(plugins_dir, "intimacy", "main.py")
    if os.path.exists(intimacy_main):
        with open(intimacy_main, encoding="utf-8") as f:
            content = f.read()
        content = content.replace('OWNER_QQ = "100000000"', f'OWNER_QQ = "{qq}"')
        with open(intimacy_main, "w", encoding="utf-8") as f:
            f.write(content)


def _configure_napcat_ws(qq):
    """写 NapCat 反向 WebSocket 配置（连 AstrBot 6199）。"""
    config_dir = None
    for root, dirs, files in os.walk(NAPCAT_DIR):
        if "config" in dirs and "napcat.json" in os.listdir(os.path.join(root, "config")):
            config_dir = os.path.join(root, "config")
            break
    if not config_dir:
        return False
    ws_client = {
        "enable": True, "name": "astrbot", "url": "ws://127.0.0.1:6199/ws",
        "messagePostFormat": "array", "reportSelfMessage": False,
        "heartInterval": 30000, "reconnectInterval": 30000, "token": "",
    }
    targets = [os.path.join(config_dir, "onebot11.json")]
    if qq:
        targets.append(os.path.join(config_dir, f"onebot11_{qq}.json"))
    for target in targets:
        existing = {}
        if os.path.exists(target):
            try:
                with open(target, encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}
        # 重要：NapCat 4.18+ 必须用嵌套结构 network.websocketClients，
        # 扁平写法会被忽略，导致 QQ 连不上 AstrBot。
        existing.pop("websocketClients", None)
        network = existing.get("network")
        if not isinstance(network, dict):
            network = {}
        network["websocketClients"] = [ws_client]
        existing["network"] = network
        with open(target, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    return True


# ---------------------------------------------------------------------------
# 部署主流程（后台线程执行）
# ---------------------------------------------------------------------------
def _deploy(key, qq):
    try:
        _set(stage="running", step=0, progress=0, error=None,
             step_key=STEPS[0][0], step_name=STEPS[0][1], message=STEPS[0][2])

        # ---- 步骤 0：定位/下载 ----
        _log("开始领养：正在准备组件")
        napcat_ready = os.path.exists(os.path.join(NAPCAT_DIR, "bootmain", "napcat.bat")) \
            or os.path.exists(os.path.join(NAPCAT_DIR, "NapCatInstaller.exe"))
        astrbot_ready = _find_astrbot_backend() is not None

        if not napcat_ready and not os.path.exists(NAPCAT_ZIP):
            _log("下载 NapCat（约 1MB）...")
            _download(NAPCAT_URL, NAPCAT_ZIP, lambda r: _step(r, 2, 3))
        if not astrbot_ready and not os.path.exists(ASTRBOT_ZIP):
            _log("下载 AstrBot（约 180MB，请耐心）...")
            _download(ASTRBOT_URL, ASTRBOT_ZIP, lambda r: _step(r, 5, 30))
        _log("组件就绪")

        # ---- 步骤 1：解压 ----
        _set(step=2, step_key=STEPS[2][0], step_name=STEPS[2][1], message=STEPS[2][2], progress=35)
        if not napcat_ready:
            _log("解压 NapCat ...")
            _unzip(NAPCAT_ZIP, NAPCAT_DIR, lambda r: _step(r, 35, 6))
        if not astrbot_ready:
            _log("解压 AstrBot（约 180MB，请耐心）...")
            _unzip(ASTRBOT_ZIP, ASTRBOT_DIR, lambda r: _step(r, 41, 14))
        _log("解压完成")

        # ---- 步骤 2：首次启动 AstrBot（生成数据目录） ----
        _set(step=3, step_key=STEPS[3][0], step_name=STEPS[3][1], message=STEPS[3][2], progress=55)
        ab_dir = _find_astrbot_backend()
        if not ab_dir:
            raise RuntimeError("未找到 AstrBot backend 目录，解压可能不完整")
        data_dir = os.path.join(ASTRBOT_ROOT, "data")
        if not os.path.exists(os.path.join(data_dir, "cmd_config.json")):
            _log("首次启动 AstrBot，初始化数据目录 ...")
            py = os.path.join(ab_dir, "python", "python.exe")
            env = dict(os.environ)
            env["ASTRBOT_ROOT"] = ASTRBOT_ROOT
            proc = subprocess.Popen([py, "launch_backend.py"], cwd=ab_dir, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for i in range(90):
                if os.path.exists(os.path.join(data_dir, "cmd_config.json")):
                    break
                time.sleep(1)
                _step(i / 90, 55, 10)
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _log("数据目录已生成，AstrBot 已停止")
        else:
            _log("数据目录已存在，跳过初始化")
        _set(progress=65)

        # ---- 步骤 3：安装插件 ----
        _set(step=4, step_key=STEPS[4][0], step_name=STEPS[4][1], message=STEPS[4][2], progress=66)
        _install_plugins(qq)
        _log("插件已安装（intimacy + pet_bridge）")
        _set(progress=74)

        # ---- 步骤 4：配置 DeepSeek + 平台 + 人设 ----
        _configure(key, qq)
        _log("DeepSeek + QQ 平台 + 人设已写入")
        _set(progress=88)

        # ---- 步骤 5：配置 NapCat 反向 WS ----
        _set(step=5, step_key=STEPS[5][0], step_name=STEPS[5][1], message=STEPS[5][2], progress=88)
        _configure_napcat_ws(qq)
        _log("NapCat 反向 WS 已配置")
        _set(progress=96)

        # ---- 完成 ----
        _set(stage="ready", step=6, step_key="done", step_name="她睁开眼睛了",
             message="部署完成！现在去扫码，让她认领你。", progress=100, qq=qq)
        _log("部署完成，等待扫码认领")

    except Exception as e:  # noqa: BLE001
        _log("部署出错：%s" % e)
        _set(stage="error", error=str(e), message="部署遇到问题：%s" % e)


# ---------------------------------------------------------------------------
# Flask 应用
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # 禁用静态缓存，开发期即时生效


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/status")
def api_status():
    with _lock:
        s = dict(state)
    # 不返回敏感信息
    s.pop("logs", None)
    return jsonify(s)


@app.route("/api/logs")
def api_logs():
    with _lock:
        return jsonify({"logs": list(state["logs"])})


@app.route("/api/adopt", methods=["POST"])
def api_adopt():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    qq = (data.get("qq") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "请填写 DeepSeek Key"}), 400
    if not qq:
        return jsonify({"ok": False, "error": "请填写你的 QQ 号"}), 400
    with _lock:
        if state["stage"] == "running":
            return jsonify({"ok": False, "error": "部署进行中"}), 409
        state["qq"] = qq
    threading.Thread(target=_deploy, args=(key, qq), daemon=True).start()
    return jsonify({"ok": True})


def _find_napcat_qrcode():
    """定位 NapCat 自动保存的登录二维码（cache/qrcode.png）。"""
    for root, dirs, files in os.walk(NAPCAT_DIR):
        if "qrcode.png" in files:
            return os.path.join(root, "qrcode.png")
    return None


def _napcat_webui_login():
    """登录 NapCat WebUI，返回 (Credential, port)。token 取 webui.json。"""
    webui_json = None
    for root, dirs, files in os.walk(NAPCAT_DIR):
        if "webui.json" in files and os.path.basename(root) == "config":
            webui_json = os.path.join(root, "webui.json")
            break
    if not webui_json:
        return None, 6099
    try:
        cfg = json.load(open(webui_json, encoding="utf-8"))
    except Exception:
        return None, 6099
    token = cfg.get("token", "")
    port = int(cfg.get("port", 6099))
    h = hashlib.sha256((token + ".napcat").encode()).hexdigest()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/auth/login",
            data=json.dumps({"hash": h, "totpCode": ""}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.load(r)
        return d["data"]["Credential"], port
    except Exception:
        return None, port


def _napcat_post(path, cred, port):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api{path}",
        data=b"{}",
        headers={"Authorization": f"Bearer {cred}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.load(r)


_last_qr_refresh = 0.0


@app.route("/api/qr_live")
def api_qr_live():
    """实时二维码 + 登录状态：直接问 NapCat WebUI，过期自动刷新（带节流）。"""
    global _last_qr_refresh
    cred, port = _napcat_webui_login()
    if not cred:
        return jsonify({"ok": False, "error": "NapCat 未运行或 WebUI 未就绪"}), 404
    try:
        st = _napcat_post("/QQLogin/CheckLoginStatus", cred, port).get("data", {})
        qrcodeurl = st.get("qrcodeurl", "") or ""
        phase = st.get("loginPhase", "") or ""
        is_login = bool(st.get("isLogin"))
        # 没二维码且处于等待态 → 主动刷新（10 秒节流，避免频繁重启登录服务）
        if (not qrcodeurl and not is_login and phase in ("waiting_qrcode", "offline", "")
                and (time.time() - _last_qr_refresh > 10)):
            _last_qr_refresh = time.time()
            try:
                r = _napcat_post("/QQLogin/RefreshQRcode", cred, port)
                if r.get("code") == 0:
                    data = r.get("data", {})
                    qrcodeurl = data.get("qrcodeurl", "") or ""
                    if data.get("restarting"):
                        phase = "reconnecting"
            except Exception:
                pass
        return jsonify({"ok": True, "qrcodeurl": qrcodeurl, "loginPhase": phase, "isLogin": is_login})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/qrcode")
def api_qrcode():
    """返回 NapCat 的最新登录二维码图片（供 UI 直接展示扫码）。"""
    p = _find_napcat_qrcode()
    if not p or not os.path.exists(p):
        return jsonify({"ok": False, "error": "二维码尚未生成，请稍等"}), 404
    resp = send_file(p, mimetype="image/png", max_age=0)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/api/napcat_webui_url")
def api_napcat_webui_url():
    """返回带 token 的 NapCat WebUI 地址（保底扫码入口）。"""
    webui_json = None
    for root, dirs, files in os.walk(NAPCAT_DIR):
        if "webui.json" in files and os.path.basename(root) == "config":
            webui_json = os.path.join(root, "webui.json")
            break
    if not webui_json:
        return jsonify({"ok": False, "error": "找不到 webui.json"}), 404
    try:
        cfg = json.load(open(webui_json, encoding="utf-8"))
        token = cfg.get("token", "")
        port = int(cfg.get("port", 6099))
        return jsonify({"ok": True, "url": f"http://127.0.0.1:{port}/webui?token={token}"})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/napcat_status")
def api_napcat_status():
    """粗略判断 NapCat 是否已登录（通过二维码文件是否还在更新判断）。"""
    p = _find_napcat_qrcode()
    running = False
    try:
        # 6099 WebUI 是否在监听 = NapCat 已启动
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        running = (s.connect_ex(("127.0.0.1", 6099)) == 0)
        s.close()
    except Exception:
        running = False
    return jsonify({"ok": True, "running": running, "qr_exists": bool(p and os.path.exists(p))})


@app.route("/api/start_napcat", methods=["POST"])
def api_start_napcat():
    # 优先复用「启动NapCat.bat」（与用户双击完全一致，已验证能正常出二维码）
    launcher = os.path.join(PROJECT_ROOT, "01-一键部署工具", "电脑版", "启动NapCat.bat")
    bootmain = _find_napcat_bootmain()
    if not bootmain:
        return jsonify({"ok": False, "error": "未找到 NapCat 启动脚本，请确认已解压"}), 404
    try:
        if os.path.exists(launcher):
            # start 新开独立窗口执行 launcher（环境与双击一致）
            subprocess.Popen(["cmd", "/c", "start", "", launcher],
                             cwd=os.path.dirname(launcher),
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(["cmd", "/c", "start", "", "napcat.bat"], cwd=bootmain,
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        return jsonify({"ok": True})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/start_astrbot", methods=["POST"])
def api_start_astrbot():
    ab_dir = _find_astrbot_backend()
    if not ab_dir:
        return jsonify({"ok": False, "error": "未找到 AstrBot 后端"}), 404
    try:
        py = os.path.join(ab_dir, "python", "python.exe")
        env = dict(os.environ)
        env["ASTRBOT_ROOT"] = ASTRBOT_ROOT
        subprocess.Popen([py, "launch_backend.py"], cwd=ab_dir, env=env,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        return jsonify({"ok": True})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def api_reset():
    _set(stage="idle", step=-1, step_key="", step_name="", message="她还沉睡在深海里，等待你领养。",
         progress=0, logs=[], error=None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5199"))
    print("深海小鲸 · 领养向导已启动：http://127.0.0.1:%d" % port, flush=True)
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)
