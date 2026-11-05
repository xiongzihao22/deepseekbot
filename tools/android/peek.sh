#!/data/data/com.termux/files/usr/bin/bash
# 单次「看一眼」：等到有时间切到目标 App，再连拍拼图
#
# 用法： bash peek.sh [帧数] [延时秒数]
#   bash peek.sh          默认 6 帧、等 4 秒
#   bash peek.sh 9 3      9 帧（3×3）、等 3 秒
#
# 输出： /sdcard/Pictures/peek.jpg
#
# 与 live.sh 的区别：
#   live.sh 是常驻服务（持续刷新单帧，靠写文件触发多帧）；
#   peek.sh 是一次性命令，适合手动跑一次。

PREFIX=/data/data/com.termux/files/usr
ADB=$PREFIX/bin/adb
MONTAGE=$PREFIX/bin/montage
export ANDROID_SERIAL=127.0.0.1:5555
export PATH=$PREFIX/bin:$PATH

N=${1:-6}
DELAY=${2:-4}
OUT=/sdcard/Pictures/peek.jpg
TMP=/sdcard/Pictures/.peek_tmp
mkdir -p "$TMP" 2>/dev/null

echo "请切到要看的画面，${DELAY} 秒后开始..."
sleep "$DELAY"

# 临时降分辨率：截图从 2.9s/帧 提速到 0.5s/帧
$ADB shell wm size 720x1080 >/dev/null 2>&1
sleep 1

i=0
while [ "$i" -lt "$N" ]; do
  $ADB shell screencap -p "$TMP/f$i.png" >/dev/null 2>&1
  i=$((i + 1))
  sleep 0.3
done

# 立刻恢复，别让屏幕一直变形
$ADB shell wm size reset >/dev/null 2>&1

cols=3
rows=$(( (N + cols - 1) / cols ))
$MONTAGE "$TMP"/f*.png -tile "${cols}x${rows}" -geometry 360x540+2+2 \
         -background '#081524' -quality 88 "$OUT" 2>/dev/null

rm -rf "$TMP"
if [ -f "$OUT" ]; then
  echo "OK: $OUT (${N} frames)"
else
  echo "FAILED"
fi
