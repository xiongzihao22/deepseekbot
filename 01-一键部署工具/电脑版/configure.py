# -*- coding: utf-8 -*-
"""
深海小鲸 · 一键配置脚本（AstrBot）
自动完成三件事：
1. 配置 DeepSeek 服务商（填 API Key）
2. 配置 OneBot v11 平台（QQ 连接，反向 WS 端口 6199）
3. 写入人设（persona，自动替换主人 QQ 号）

用法（在 AstrBot backend 目录下用其自带 Python 运行）：
    python.exe configure.py <DeepSeek-Key> <主人QQ号>
"""
import json
import os
import sqlite3
import sys

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


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python configure.py <DeepSeek-Key> [主人QQ号]")
        sys.exit(1)

    ds_key = sys.argv[1].strip()
    owner_qq = sys.argv[2].strip() if len(sys.argv) > 2 else ""

    root = os.environ.get("ASTRBOT_ROOT", os.path.expanduser("~/.astrbot"))
    data_dir = os.path.join(root, "data")
    cfg_path = os.path.join(data_dir, "cmd_config.json")
    db_path = os.path.join(data_dir, "data_v4.db")

    # ---- 1. 配置 DeepSeek provider ----
    with open(cfg_path, encoding="utf-8-sig") as f:
        cfg = json.load(f)

    provider = {
        "id": "deepseek",
        "provider": "openai",
        "type": "openai_chat_completion",
        "provider_type": "chat_completion",
        "enable": True,
        "key": [ds_key],
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "timeout": 120,
        "proxy": "",
        "custom_headers": {},
    }
    cfg["provider"] = [p for p in cfg.get("provider", []) if p.get("id") != "deepseek"]
    cfg["provider"].append(provider)

    # ---- 2. 配置 OneBot v11 平台（反向 WS） ----
    platform = {
        "id": "default",
        "type": "aiocqhttp",
        "enable": True,
        "ws_reverse_host": "0.0.0.0",
        "ws_reverse_port": 6199,
        "ws_reverse_token": "",
    }
    cfg["platform"] = [
        p for p in cfg.get("platform", []) if p.get("type") != "aiocqhttp"
    ]
    cfg["platform"].append(platform)

    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)
    print("[1/3] DeepSeek provider + OneBot 平台已写入 cmd_config.json")

    # ---- 3. 写入人设（persona） ----
    persona = PERSONA_TMPL.format(owner_qq=owner_qq or "你的QQ号")
    if os.path.exists(db_path):
        db = sqlite3.connect(db_path)
        cur = db.execute(
            "SELECT COUNT(*) FROM personas WHERE persona_id='default'"
        )
        if cur.fetchone()[0] > 0:
            db.execute(
                "UPDATE personas SET system_prompt=? WHERE persona_id='default'",
                (persona,),
            )
        else:
            db.execute(
                "INSERT INTO personas (persona_id, system_prompt) VALUES ('default', ?)",
                (persona,),
            )
        db.commit()
        db.close()
        print("[2/3] 人设已写入 data_v4.db（主人 QQ 号: %s）" % (owner_qq or "未填"))
    else:
        print("[2/3] 未找到 data_v4.db，跳过人设写入")

    print("[3/3] 一键配置完成！重启 AstrBot 后生效。")


if __name__ == "__main__":
    main()
