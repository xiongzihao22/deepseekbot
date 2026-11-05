#!/usr/bin/env bash
# 深海小鲸 · 手机版 NapCat 安装脚本
# 在 DSHA（Ubuntu 24.04 arm64）终端里运行：bash install-napcat.sh

set -e

echo "=============================================="
echo "  深海小鲸 · NapCat(QQ协议端) 安装脚本"
echo "=============================================="

# 1. 环境检查
if ! command -v curl >/dev/null 2>&1; then
    echo "[错误] 缺少 curl，请先安装：sudo apt install curl"
    exit 1
fi

# 2. 安装 NapCat（优先官方一键脚本，失败则提示手动）
echo "[1/4] 下载 NapCat ..."
if curl -fsSL -o /tmp/napcat-install.sh "https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.sh"; then
    echo "      已获取官方安装脚本，开始安装 ..."
    sudo bash /tmp/napcat-install.sh
else
    echo "      官方脚本下载失败，请手动安装："
    echo "      参考 https://github.com/NapNeko/NapCatQQ 的 Linux 部署说明"
fi

# 3. 配置 OneBot WebSocket（Array 格式，与 AstrBot/DSH 对接）
echo "[2/4] 配置 OneBot WebSocket ..."
CONFIG_DIR="${HOME}/.config/napcat"
mkdir -p "${CONFIG_DIR}"

cat > "${CONFIG_DIR}/onebot11_ws.json" <<'EOF'
{
  "wsReverse": [
    {
      "enable": true,
      "url": "ws://127.0.0.1:6199/ws",
      "messagePostFormat": "array"
    }
  ]
}
EOF
echo "      已写入 ${CONFIG_DIR}/onebot11_ws.json"

# 4. 启动说明
echo "[3/4] 启动 NapCat ..."
echo "      首次启动会生成二维码，请用 QQ 小号扫码登录。"
echo "      启动命令："
echo "        sudo systemctl start napcat   （systemd 方式）"
echo "        或 cd ~/NapCat && ./NapCat.sh （手动方式）"

echo "[4/4] 完成。"
echo ""
echo "  下一步："
echo "   1) 启动 NapCat 并扫码登录 QQ 小号；"
echo "   2) 确认 WebSocket 地址 ws://127.0.0.1:6199/ws 已生效（Array 格式）；"
echo "   3) 回到 DSH/AstrBot 后台填 DeepSeek Key + 人设。"
echo ""
echo "=============================================="
echo "  安装脚本执行完毕"
echo "=============================================="
