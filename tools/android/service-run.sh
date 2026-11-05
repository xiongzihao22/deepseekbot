#!/data/data/com.termux/files/usr/bin/sh
# runit 服务的启动脚本
# 安装位置： $PREFIX/var/service/livepeek/run
#
# 必须显式设置 PATH / HOME / TMPDIR：
# runit 启动的进程环境是干净的，不设置的话 adb、convert 全都找不到。

export PATH=/data/data/com.termux/files/usr/bin:$PATH
export HOME=/data/data/com.termux/files/home
export TMPDIR=/data/data/com.termux/files/usr/tmp

exec bash /data/data/com.termux/files/home/live.sh
