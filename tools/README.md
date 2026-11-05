# tools/ · 看视频助手

## 它解决什么问题

平板上的 bot（DSHA / DeepSeek 客户端）看视频时，靠的是**无障碍截图**（`AccessibilityService.takeScreenshot`）。

Android 11 起，这个 API **每秒只能调用 1 次**，超了直接失败。视频画面每帧都在变，bot 想连续抓帧，就会一直报「无法截图」。

> 这不是 DSHA 的保护机制，是 Android 系统的限流。

## 怎么解决

**不再逐帧截图，改成「一次拍多张、拼成一张静态图」**：

```
临时降到 720x1080  →  每 0.5 秒拍一张（PNG 编码量降到 1/6，从 2.9s 提速到 0.49s）
                   →  拼成九宫格
                   →  恢复分辨率
                   →  推回平板 /sdcard/Pictures/peek.jpg
```

bot 只需要看 **1 张图**，就能理解这 6 秒发生了什么，不受限流、不受画面变化影响。

## 用法

```bash
python video_peek.py                # 6 帧，间隔 0.6 秒
python video_peek.py 9 0.5          # 9 帧（3x3），间隔 0.5 秒
python video_peek.py 6 0.6 --push   # 顺便推到平板，让 bot 直接读文件
```

输出：`tools/peek.jpg`

## 前置条件

1. 电脑装了 adb，平板开启 USB 调试并授权
   - 没装 adb：下载 [platform-tools](https://developer.android.com/tools/releases/platform-tools)，解压后设置环境变量 `ADB_PATH`
2. 只用标准库 + Pillow（`pip install pillow`）

## 实测数据（小米平板 6S Pro / Android 16）

| 方式 | 单帧耗时 | 说明 |
|------|---------|------|
| 原始分辨率 2032×3048 截图 | **2.9 秒** | PNG 编码太重，不可用 |
| raw 格式截图 | **7.5 秒** | 24MB 传输，更慢 |
| 降到 720×1080 截图 | **0.49 秒** | ✅ 采用 |

6 帧总耗时约 6 秒（含降分辨率、连拍、恢复、拼图）。

## 已知限制

- **截图期间屏幕会临时变成 720×1080**（界面会重排），结束后自动恢复。如果中途异常，可手动执行 `adb shell wm size reset`。
- 如果某个 App 开了 **FLAG_SECURE**（支付宝、部分视频 App 的付费内容），截图会全黑——这是系统级保护，任何截图/录屏方案都绕不过，只能用字幕、标题等文字信息代替。
- 只适用于「平板上运行 bot，电脑用 adb 连平板」的场景。

## 另一个更省事的办法

如果只是偶尔看一次，也可以直接告诉 bot：

> 「截图间隔至少 1.5 秒，失败就等 2 秒再试；别在视频播放时连续截图。」

Android 的限流是 1 秒 1 次，**降到 1.5 秒间隔就不会撞墙**。这不用改代码，改 prompt 就行。
