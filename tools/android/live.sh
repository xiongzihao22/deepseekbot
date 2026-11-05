#!/data/data/com.termux/files/usr/bin/bash
# 屏幕看板服务（常驻，由 runit 守护）
#
# 做两件事：
#   1) 持续把当前屏幕缩成 /sdcard/Pictures/live.jpg（每 3 秒左右刷新一次）
#      —— bot 随时读这个文件，拿到的是最新画面
#   2) 监听 /sdcard/Pictures/peek_request
#      —— bot 写这个文件，就拍 6 帧拼成 /sdcard/Pictures/peek.jpg，并留下 peek_ready 标记
#
# ⚠️ 关键：所有命令必须用绝对路径。
#    runit 启动的进程环境非常干净，PATH 里没有 Termux 的 bin 目录，
#    用相对命令会静默失败（服务在跑但图片永远不更新）。

PREFIX=/data/data/com.termux/files/usr
ADB=$PREFIX/bin/adb
CONVERT=$PREFIX/bin/convert
MONTAGE=$PREFIX/bin/montage
export ANDROID_SERIAL=127.0.0.1:5555
export PATH=$PREFIX/bin:$PATH
export HOME=/data/data/com.termux/files/home
export TMPDIR=$PREFIX/tmp

RAW=/sdcard/Pictures/.live_raw.png
LIVE=/sdcard/Pictures/live.jpg
REQ=/sdcard/Pictures/peek_request
READY=/sdcard/Pictures/peek_ready
PEEK=/sdcard/Pictures/peek.jpg
TMP=/sdcard/Pictures/.peek_tmp
LOG=$HOME/live.log

log() { echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }

$PREFIX/bin/termux-wake-lock 2>/dev/null
log "服务启动 PATH_OK=$([ -x $ADB ] && echo yes || echo no)"

# 确保 adb server 在跑并连上自己
$ADB start-server >/dev/null 2>&1
sleep 2
$ADB connect 127.0.0.1:5555 >/dev/null 2>&1
sleep 1
log "adb: $($ADB devices 2>&1 | tr '\n' ' ')"

shot() {
  $ADB shell screencap -p "$1" >/dev/null 2>&1
  [ -s "$1" ]
}

fail_count=0
while true; do
  # ---------- A. 常规刷新 ----------
  if shot "$RAW"; then
    $CONVERT "$RAW" -resize 720x -quality 85 "$LIVE" 2>/dev/null
    rm -f "$RAW"
    fail_count=0
  else
    fail_count=$((fail_count + 1))
    if [ $((fail_count % 10)) -eq 1 ]; then
      log "截图失败 x$fail_count，尝试重连"
      $ADB connect 127.0.0.1:5555 >/dev/null 2>&1
    fi
  fi

  # ---------- B. 多帧请求 ----------
  if [ -f "$REQ" ]; then
    rm -f "$REQ" "$READY"
    log "收到 peek 请求"
    mkdir -p "$TMP"
    i=0
    while [ "$i" -lt 6 ]; do
      shot "$TMP/f$i.png"
      i=$((i + 1))
      sleep 0.35
    done
    $MONTAGE "$TMP"/f*.png -tile 3x2 -geometry 360x540+2+2 \
             -background '#081524' -quality 88 "$PEEK" 2>/dev/null
    rm -rf "$TMP"
    touch "$READY"
    log "peek 完成"
  fi

  sleep 1
done
