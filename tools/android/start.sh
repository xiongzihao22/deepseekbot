#!/data/data/com.termux/files/usr/bin/bash
# 启动 / 重启看板服务
#
# 用法： bash start.sh
#
# 做三件事：
#   1. 申请 wake lock（防止 Termux 休眠）
#   2. 拉起 runsvdir（Termux 的服务守护，会管理系统服务）
#   3. 报告服务状态
#
# 装过一次之后，日常只需要跑这一个。

PREFIX=/data/data/com.termux/files/usr
export SVDIR=$PREFIX/var/service
export PATH=$PREFIX/bin:$PATH

$PREFIX/bin/termux-wake-lock 2>/dev/null

echo "启动 runsvdir ..."
pkill -f runsvdir 2>/dev/null
sleep 1
nohup runsvdir $SVDIR > /dev/null 2>&1 &
sleep 3

echo "--- 服务状态 ---"
sv status livepeek 2>/dev/null || echo "服务未注册，请先执行 README 里的注册步骤"

echo "--- 进程 ---"
ps -ef | grep live.sh | grep -v grep | head -2

echo ""
echo "提示：如果 live.jpg 不更新，查看日志"
echo "  cat ~/live.log"
