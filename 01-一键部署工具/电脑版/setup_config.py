# -*- coding: utf-8 -*-
"""
深海小鲸 · 一键部署编排脚本
流程：首次启动 AstrBot(生成数据目录) → 安装插件 → 自动配置(DeepSeek+平台+人设)

用法：
    python setup_config.py <DeepSeek-Key> <主人QQ号> <项目根目录>
"""
import json
import os
import shutil
import subprocess
import sys
import time

# 让 setup_config.py 能 import 同目录的 configure.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import configure


def setup_napcat_ws(comp_root: str, owner_qq: str) -> bool:
    """配置 NapCat 反向 WebSocket（连 AstrBot 6199）。"""
    # 目录名统一小写；Windows 不区分大小写，兼容旧的 NapCat/
    napcat_dir = os.path.join(comp_root, "napcat")
    if not os.path.isdir(napcat_dir):
        napcat_dir = os.path.join(comp_root, "NapCat")
    config_dir = None
    if os.path.isdir(napcat_dir):
        for root, dirs, _ in os.walk(napcat_dir):
            if "config" in dirs and "napcat.json" in os.listdir(os.path.join(root, "config")):
                config_dir = os.path.join(root, "config")
                break
    if not config_dir:
        print("   [提示] 未找到 NapCat config 目录，跳过（首次登录后可在 WebUI 配置）")
        return False

    ws_client = {
        "enable": True,
        "name": "astrbot",
        "url": "ws://127.0.0.1:6199/ws",
        "messagePostFormat": "array",
        "reportSelfMessage": False,
        "heartInterval": 30000,
        "reconnectInterval": 30000,
        "token": "",
    }
    targets = [os.path.join(config_dir, "onebot11.json")]
    if owner_qq:
        targets.append(os.path.join(config_dir, f"onebot11_{owner_qq}.json"))
    for target in targets:
        existing = {}
        if os.path.exists(target):
            try:
                with open(target, encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}
        # 重要：NapCat 4.18+ 要求嵌套结构 network.websocketClients
        # （扁平写法 websocketClients 会被忽略，导致 QQ 连不上 AstrBot）
        existing.pop("websocketClients", None)
        network = existing.get("network")
        if not isinstance(network, dict):
            network = {}
        network["websocketClients"] = [ws_client]
        existing["network"] = network
        with open(target, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"   NapCat 反向 WS 已写入 {target}（network.websocketClients）")
    return True


def main() -> None:
    if len(sys.argv) < 4:
        print("用法: python setup_config.py <DeepSeek-Key> <主人QQ号> <工具目录> [组件目录]")
        print("  工具目录：本脚本所在目录（插件在这里）")
        print("  组件目录：astrbot/ 和 napcat/ 所在目录；不填则同工具目录")
        sys.exit(1)

    ds_key = sys.argv[1]
    owner_qq = sys.argv[2]
    proj_root = sys.argv[3].rstrip("\\/")
    # 组件（astrbot / napcat）可能在项目根，与工具目录不同
    comp_root = sys.argv[4].rstrip("\\/") if len(sys.argv) > 4 else proj_root

    # 定位 AstrBot 便携版目录（兼容大小写）
    ab_dir = None
    for base in (os.path.join(comp_root, "astrbot"), os.path.join(comp_root, "AstrBot")):
        if not os.path.isdir(base):
            continue
        for root, dirs, _ in os.walk(base):
            if "launch_backend.py" in os.listdir(root) and "python" in dirs:
                ab_dir = root
                break
        if ab_dir:
            break
    if not ab_dir:
        print(f"[错误] 在 {comp_root} 下未找到 AstrBot 的 backend 目录，请确认已解压。")
        sys.exit(1)

    py = os.path.join(ab_dir, "python", "python.exe")
    astrbot_root = os.environ.get(
        "ASTRBOT_ROOT", os.path.join(os.path.expanduser("~"), ".astrbot")
    )
    data_dir = os.path.join(astrbot_root, "data")

    # ---- 1. 首次启动 AstrBot 生成数据目录和数据库 ----
    # 注意：data_v4.db 比 cmd_config.json 晚创建很多（首次启动要先下载 WebUI，约 50~60 秒），
    # 原实现只等 cmd_config.json 就杀进程，导致 db 从未生成、人设写不进去。
    db_file = os.path.join(data_dir, "data_v4.db")
    if not os.path.exists(db_file):
        print("[1/4] 首次启动 AstrBot 初始化数据目录（首次需下载 WebUI，约 1 分钟）...")
        env = dict(os.environ)
        env["ASTRBOT_ROOT"] = astrbot_root
        proc = subprocess.Popen(
            [py, "launch_backend.py"],
            cwd=ab_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ready = False
        for _ in range(180):
            if os.path.exists(db_file):
                ready = True
                break
            time.sleep(1)
        # 停止
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if ready:
            print("   数据目录与数据库已生成，AstrBot 已停止。")
        else:
            print("   [警告] 等待超时，data_v4.db 未生成。")
            print("          人设将稍后写入；如失败，启动一次 AstrBot 后重跑本脚本即可。")
    else:
        print("[1/4] 数据目录已存在，跳过初始化。")

    # ---- 2. 安装插件 ----
    print("[2/4] 安装插件（intimacy + pet_bridge）...")
    plugins_dir = os.path.join(data_dir, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    for name in ("intimacy", "pet_bridge"):
        src = os.path.join(proj_root, "插件", name)
        dst = os.path.join(plugins_dir, name)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
    # 替换 intimacy 插件里的主人 QQ 号
    intimacy_main = os.path.join(plugins_dir, "intimacy", "main.py")
    if os.path.exists(intimacy_main):
        with open(intimacy_main, encoding="utf-8") as f:
            content = f.read()
        content = content.replace('OWNER_QQ = "100000000"', f'OWNER_QQ = "{owner_qq}"')
        with open(intimacy_main, "w", encoding="utf-8") as f:
            f.write(content)
    print("   插件安装完成。")

    # ---- 3. 自动配置 ----
    print("[3/5] 自动配置 DeepSeek + OneBot 平台 + 人设 ...")
    sys.argv = ["configure.py", ds_key, owner_qq]
    configure.main()

    # ---- 4. 配置 NapCat 反向 WebSocket ----
    print("[4/5] 配置 NapCat 反向 WebSocket ...")
    setup_napcat_ws(comp_root, owner_qq)

    print("[5/5] 一键部署完成！接下来只需：启动 NapCat 扫码 + 启动 AstrBot。")


if __name__ == "__main__":
    main()
