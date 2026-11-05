# -*- coding: utf-8 -*-
"""
看视频助手 video_peek

解决什么问题：
    平板上的 bot 靠无障碍截图看画面，Android 限制每秒最多 1 次；
    视频一直在变，连续截图必然失败（报"无法截图"）。

怎么解决：
    1. 临时把屏幕分辨率降到 720x1080（PNG 编码量降到 1/6，截图从 2.9s 提速到 0.5s）
    2. 高速连拍多帧（每帧约 0.5 秒）
    3. 拼成一张九宫格静态图
    4. 恢复分辨率，并把成品推回平板，让 bot 直接读文件

用法：
    python video_peek.py                  # 默认 6 帧
    python video_peek.py 9 0.5            # 9 帧，间隔 0.5 秒
    python video_peek.py 6 0.6 --push     # 顺便推到平板 /sdcard/Pictures/

输出：
    tools/peek.jpg（同时 --push 时在平板上 /sdcard/Pictures/peek.jpg）

注意：
    截图期间屏幕会临时变成 720x1080（界面会重新排版），结束后自动恢复。
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JPG = os.path.join(OUT_DIR, "peek.jpg")

SMALL_W, SMALL_H = 720, 1080
TILE_W = 360          # 每格宽度（输出图）
TILE_H = 540          # 每格高度（3:4，贴合平板比例）


def find_adb() -> str:
    """依次从环境变量、PATH、常见安装位置找 adb。"""
    env = os.environ.get("ADB_PATH", "")
    if env and os.path.isfile(env):
        return env
    p = shutil.which("adb")
    if p:
        return p
    for cand in (
        os.path.expanduser(r"~\platform-tools\adb.exe"),
        r"C:\platform-tools\adb.exe",
        r"D:\platform-tools\adb.exe",
        os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
        r"C:\Android\Sdk\platform-tools\adb.exe",
    ):
        if os.path.isfile(cand):
            return cand
    return ""


ADB = find_adb()


def sh(cmd: str, timeout: int = 30) -> str:
    r = subprocess.run([ADB] + cmd.split(), capture_output=True, text=True,
                       encoding="gbk", errors="ignore", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def get_size() -> tuple:
    out = sh("shell wm size")
    for line in out.splitlines():
        if "Physical size" in line or "Override size" in line:
            try:
                wh = line.split(":")[1].strip()
                w, h = wh.split("x")
                return int(w), int(h)
            except Exception:
                pass
    return 0, 0


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    gap = float(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 0.6
    do_push = "--push" in sys.argv

    if not ADB:
        print("[错误] 找不到 adb.exe，请设置环境变量 ADB_PATH 指向 adb")
        return 1

    dev = sh("devices")
    if "\tdevice" not in dev:
        print("[错误] 没有检测到设备，请检查 USB 连接与授权")
        print(dev.strip())
        return 1

    orig = get_size()
    print(f"设备原始分辨率: {orig[0]}x{orig[1]}")

    tmp = tempfile.mkdtemp(prefix="peek_")
    files = []
    restored = False

    try:
        # 1. 降分辨率
        print(f"[1/4] 临时降分辨率到 {SMALL_W}x{SMALL_H} ...")
        sh(f"shell wm size {SMALL_W}x{SMALL_H}")
        time.sleep(1.2)

        # 2. 连拍
        print(f"[2/4] 连拍 {n} 帧（间隔 {gap}s）...")
        t0 = time.time()
        for i in range(n):
            remote = f"/sdcard/_pk{i}.png"
            sh(f"shell screencap -p {remote}")
            local = os.path.join(tmp, f"f{i}.png")
            subprocess.run([ADB, "pull", remote, local], capture_output=True, timeout=30)
            sh(f"shell rm {remote}")
            if os.path.exists(local) and os.path.getsize(local) > 1000:
                files.append(local)
            if i < n - 1:
                time.sleep(gap)
        print(f"      抓到 {len(files)} 帧，用时 {time.time()-t0:.1f}s")

        # 3. 立刻恢复分辨率（别让用户屏幕一直变形）
        sh("shell wm size reset")
        restored = True
        print("[3/4] 分辨率已恢复")

        if not files:
            print("[错误] 一张都没抓到")
            return 2

        # 4. 拼图
        print("[4/4] 拼成九宫格 ...")
        from PIL import Image, ImageDraw

        cols = 3 if len(files) >= 3 else len(files)
        rows = (len(files) + cols - 1) // cols
        canvas = Image.new("RGB", (cols * TILE_W, rows * TILE_H), (8, 21, 36))

        for idx, f in enumerate(files):
            im = Image.open(f).convert("RGB")
            # 等比裁剪填充格子
            scale = max(TILE_W / im.width, TILE_H / im.height)
            im = im.resize((int(im.width * scale) + 1, int(im.height * scale) + 1), Image.LANCZOS)
            left = (im.width - TILE_W) // 2
            top = (im.height - TILE_H) // 2
            im = im.crop((left, top, left + TILE_W, top + TILE_H))
            x = (idx % cols) * TILE_W
            y = (idx // cols) * TILE_H
            canvas.paste(im, (x, y))
            # 序号角标
            d = ImageDraw.Draw(canvas)
            d.rectangle([x + 8, y + 8, x + 46, y + 34], fill=(8, 21, 36))
            d.text((x + 16, y + 12), f"#{idx+1}", fill=(127, 240, 224))
            # 细边框
            d.rectangle([x, y, x + TILE_W - 1, y + TILE_H - 1], outline=(15, 40, 60))

        canvas.save(OUT_JPG, "JPEG", quality=88, optimize=True)
        print(f"\n✅ 已生成: {OUT_JPG}")
        print(f"   {canvas.size[0]}x{canvas.size[1]}，{os.path.getsize(OUT_JPG)//1024} KB，{len(files)} 帧")

        # 5. 推回平板（可选）
        if do_push:
            remote = "/sdcard/Pictures/peek.jpg"
            r = subprocess.run([ADB, "push", OUT_JPG, remote], capture_output=True, text=True)
            if r.returncode == 0:
                print(f"   已推送到平板: {remote}（bot 可直接读这个文件）")
            else:
                print(f"   [提示] 推送失败: {r.stderr.strip()[:120]}")

        print("\n把这张图发给 bot，或让它读上面的路径，就能一次看到整段画面。")
        return 0
    finally:
        if not restored:
            sh("shell wm size reset")
            print("[已自动恢复分辨率]")
        for f in files:
            try:
                os.remove(f)
            except Exception:
                pass
        try:
            os.rmdir(tmp)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
