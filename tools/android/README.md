# 平板端 · 屏幕看板（Termux + 自连 adb）

> 让**跑在安卓平板上的 bot** 能看清屏幕（包括正在播放的视频），
> 而且**完全不依赖电脑**。

---

## 为什么需要它

平板上的 AI 应用（如 DSHA / DeepSeek 客户端）看屏幕，用的是**无障碍截图**
（`AccessibilityService.takeScreenshot`）。

Android 11 起这个 API **每秒只能调用 1 次**，超出直接失败。视频画面每帧都在变，
bot 想连续抓帧就会一直报「无法截图」。

**这不是应用的保护机制，是 Android 系统的限流。**

| 方式 | 谁在用 | 速率 |
|---|---|---|
| 无障碍截图 | 平板上的 App | ❌ 1 次/秒 |
| `adb shell screencap` | 有 shell 权限的进程 | ✅ 无限制 |

电host 通过 USB 连平板时有 shell 权限，所以电脑端方案（见上级目录 `video_peek.py`）能跑。
但平板上的 App 拿不到这个权限——除非**平板用 adb 连自己**。

这就是本方案：

```
Termux 装 adb → adb connect 127.0.0.1:5555 → Termux 获得 shell 权限
                ↓
        每 3 秒截一帧 → 缩成 720 宽 → 写 /sdcard/Pictures/live.jpg
        bot 写 peek_request → 拍 6 帧拼成 peek.jpg
```

bot 只需要**读文件**，不需要执行任何命令。

---

## 前置条件

- 安卓平板 / 手机（本文测试于小米平板 6S Pro，HyperOS 3.0 / Android 16）
- 电脑上装有 [platform-tools](https://developer.android.com/tools/releases/platform-tools)（只在**首次配置**时需要）
- 平板开启：开发者选项 → **USB 调试** → **USB 调试（安全设置）**
  - 小米必须登录账号才能开「USB 调试（安全设置）」，不开会导致 adb 授权后仍认证失败

---

## 安装步骤

### 1. 装 Termux

从 [Termux Releases](https://github.com/termux/termux-app/releases) 下载 **arm64-v8a** 版。

> 小米/HyperOS 直接用 `adb install` 会报 `INSTALL_FAILED_USER_RESTRICTED`。
> 绕过办法：把 APK 推到 `/data/local/tmp/`，再用 PackageInstaller 会话安装：
>
> ```bash
> adb push termux.apk /data/local/tmp/termux.apk
> ADB_SHELL="adb shell"
> SIZE=$($ADB_SHELL "stat -c %s /data/local/tmp/termux.apk" | tr -d '\r')
> SID=$($ADB_SHELL "pm install-create -r -t -S $SIZE" | grep -o '\[[0-9]*\]' | tr -d '[]')
> $ADB_SHELL "pm install-write $SID base /data/local/tmp/termux.apk"
> $ADB_SHELL "pm install-commit $SID"
> ```

### 2. 装依赖

打开 Termux，依次执行：

```bash
pkg update
pkg install -y android-tools imagemagick termux-services
pkg upgrade -y          # ← 关键！见踩坑 2
```

`pkg upgrade` 过程中会弹若干配置文件冲突提示（openssl.cnf、sources.list），
一律选 **N**（保留当前版本）。

### 3. 让平板连自己

电脑上执行一次（USB 已连接）：

```bash
adb tcpip 5555
```

平板上（Termux 里）：

```bash
adb connect 127.0.0.1:5555
```

第一次会弹「允许 USB 调试吗」，勾选**一律允许**后点确定。

验证：

```bash
adb devices
# 应该看到 127.0.0.1:5555   device
```

> 如果出现 `failed to authenticate`，说明「USB 调试（安全设置）」没开，
> 或者授权被拒过——删掉 `~/.android` 重新触发票据：
> `rm -rf ~/.android && adb kill-server && adb connect 127.0.0.1:5555`

### 4. 部署脚本

把本目录的 `live.sh`、`peek.sh`、`start.sh` 放到 Termux 的 home：

```bash
# 方法一：平板能访问 /sdcard 时
cp /sdcard/Download/live.sh ~/ && chmod +x ~/live.sh

# 方法二：从电脑推（不需要平板存储权限）
adb push live.sh /data/local/tmp/live.sh
# 然后 Termux 里 cp（Termux 对自己的 home 有权限）
```

### 5. 注册成系统服务

`termux-services` 用 runit 管理守护进程，进程被杀会自动重启。

```bash
export SVDIR=$PREFIX/var/service
mkdir -p $SVDIR/livepeek
cp ~/service-run.sh $SVDIR/livepeek/run
chmod +x $SVDIR/livepeek/run
ln -sfn $PREFIX/share/termux-services/svlogger $SVDIR/livepeek/log

sv-enable livepeek
```

> `sv` 命令找不到服务时，先 `export SVDIR=$PREFIX/var/service`（踩坑 4）。

### 6. 启动

```bash
bash ~/start.sh
```

看到 `run: livepeek: (pid xxxxx) xxs; run: log: (pid xxxxx)` 就成功了。

---

## 怎么用

### 给 bot 的指令（复制进它的设定）

```
【看屏幕的方式】
- 想知道我现在在干什么：读 /sdcard/Pictures/live.jpg
  这个文件每 3 秒自动更新，永远是最新画面。
- 想看一段动态变化：写一个空文件到 /sdcard/Pictures/peek_request，
  等 20 秒，然后读 /sdcard/Pictures/peek.jpg（6 帧拼图，3×2）。
  看到 /sdcard/Pictures/peek_ready 出现，说明已经生成好了。
- 绝对不要用无障碍连续截图看视频：Android 限制每秒只能截 1 次，
  动态画面必然失败并报"无法截图"。用上面两个文件代替。
```

### 产出文件

| 文件 | 说明 |
|---|---|
| `/sdcard/Pictures/live.jpg` | 单帧，720×1080，约 160KB，每 3 秒刷新 |
| `/sdcard/Pictures/peek.jpg` | 6 帧拼图，3×2，约 300KB |
| `/sdcard/Pictures/peek_request` | bot 写的触发文件 |
| `/sdcard/Pictures/peek_ready` | 生成完成的标记 |

### 手动看一眼（不用等服务）

```bash
bash ~/peek.sh 6 4     # 6 帧，等 4 秒（留时间切 App）
```

---

## 踩坑记录

| # | 现象 | 原因 | 解决 |
|---|---|---|---|
| 1 | `adb install` 报 `INSTALL_FAILED_USER_RESTRICTED` | 小米「USB 安装」未开，且 PackageInstaller 不接受 `/sdcard` 路径 | APK 放 `/data/local/tmp/` + `pm install-create/write/commit` |
| 2 | Termux 里 `adb` 报 `cannot locate symbol _ZNSt6__ndk1...` | android-tools 的二进制与 Termux 的 libc++ ABI 不匹配 | `pkg upgrade -y` 全量升级后恢复 |
| 3 | `adb connect` 报 `failed to authenticate`，点确定也没用 | 「USB 调试（安全设置）」未开；或旧密钥被拒 | 开该开关；或 `rm -rf ~/.android` 重新触发授权 |
| 4 | `sv-enable` 报 `unable to change to service directory` | 没设 `SVDIR` | `export SVDIR=$PREFIX/var/service` |
| 5 | **服务在跑但 live.jpg 永不更新** | runit 启动的进程 PATH 干净，`adb`/`convert` 找不到，且错误被 `2>/dev/null` 吞掉 | 脚本内全部使用绝对路径（`$PREFIX/bin/adb` 等） |
| 6 | `adb` 报 `more than one device/emulator` | 系统自带 `emulator-5554` | `export ANDROID_SERIAL=127.0.0.1:5555` |

---

## 重启后怎么恢复

`adb tcpip 5555` 是**临时的**，平板重启后失效。恢复方式：

**办法 A（需要电脑一次）**

```bash
adb tcpip 5555          # 电脑 USB 连着平板时执行
# 然后平板 Termux 里
bash ~/start.sh
```

**办法 B（彻底摆脱电脑）**

用 Android 11+ 的**无线调试**配对（开发者选项 → 无线调试 → 使用配对码配对），
配对一次后 `adb connect` 可以长期使用。这个方式重启后需要重新配对，
但不依赖 USB。

---

## 性能实测（小米平板 6S Pro / Android 16）

| 操作 | 耗时 |
|---|---|
| 原始分辨率截图（2032×3048） | 2.9 秒 |
| 降到 720×1080 截图 | **0.49 秒** |
| 单帧刷新（截图 + 缩放） | 约 3 秒/轮 |
| 6 帧拼图 | 约 16 秒 |
| 服务被杀后自动重启 | 5 秒内 |

---

## 已知限制

- **FLAG_SECURE 无法绕过**：付费视频、部分直播的截图会是全黑，这是系统级保护。
  这种情况下只能读字幕、标题等文字信息。
- **耗电**：持续截图约每小时 3~5% 电量（平板）。
- **MIUI 会杀后台**：建议设置「省电策略：无限制」+ 允许自启动 + 最近任务里锁定。
