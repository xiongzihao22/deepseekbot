@echo off
chcp 936 >nul
setlocal enabledelayedexpansion
title 深海小鲸 · 一键部署向导

echo.
echo  ==============================================
echo     深海小鲸 · 一键部署向导
echo     零基础 5 分钟，养一只 AI 大肥鱼
echo  ==============================================
echo.
echo   本脚本会自动完成：下载、解压、注入人设、安装好感度插件、生成配置卡片
echo   你只需要填两样东西：你的 QQ 号 + DeepSeek Key，其余全自动
echo.

REM ---------- 环境检查 ----------
where powershell >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 PowerShell，无法继续。
    pause
    exit /b 1
)

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

REM ---------- 可配置的下载地址（如失效，请替换为最新 Release 直链） ----------
REM NapCat OneKey 一键版（启动器，首次运行自动下载内置 QQ）
set "NAPCAT_URL=https://github.com/NapNeko/NapCatQQ/releases/download/v4.18.42/NapCat.Shell.Windows.OneKey.zip"
REM AstrBot 桌面便携版（解压即用，含 Python 后端）
set "ASTRBOT_URL=https://github.com/AstrBotDevs/AstrBot-desktop/releases/download/v4.29.4/AstrBot_4.29.4_windows_amd64_portable.zip"

echo.
echo [1/6] 收集信息（只问你这一次）
echo.
set /p OWNER_QQ=  你的 QQ 号（成为小鲸唯一的主人）: 
set /p DS_KEY=  你的 DeepSeek API Key（sk- 开头）: 
echo.

echo [2/6] 创建目录结构 ...
mkdir "%ROOT%\NapCat" >nul 2>nul
mkdir "%ROOT%\AstrBot" >nul 2>nul
mkdir "%ROOT%\人设" >nul 2>nul
echo   目录创建完成

echo.
echo [3/6] 下载组件（约几百 MB，请耐心等待）...
echo.
echo   提示：如果自动下载失败（网络/代理问题），请手动下载后放到对应文件夹，
echo   详见同目录下的《部署说明.md》。
echo.
curl -k -L -o "%ROOT%\NapCat\napcat.zip" "%NAPCAT_URL%" 2>nul && echo   NapCat 下载完成 || echo   [跳过] NapCat 自动下载失败，请手动下载
curl -k -L -o "%ROOT%\AstrBot\astrbot.zip" "%ASTRBOT_URL%" 2>nul && echo   AstrBot 下载完成 || echo   [跳过] AstrBot 自动下载失败，请手动下载

echo.
echo [4/6] 解压组件 ...
if exist "%ROOT%\NapCat\napcat.zip" (
    powershell -NoProfile -Command "Expand-Archive -Path '%ROOT%\NapCat\napcat.zip' -DestinationPath '%ROOT%\NapCat' -Force"
    echo   NapCat 解压完成
)
if exist "%ROOT%\AstrBot\astrbot.zip" (
    powershell -NoProfile -Command "Expand-Archive -Path '%ROOT%\AstrBot\astrbot.zip' -DestinationPath '%ROOT%\AstrBot' -Force"
    echo   AstrBot 解压完成
)

echo.
echo [5/6] 初始化并自动配置（首次启动 AstrBot → 装插件 → 配 DeepSeek + 人设）...
echo   这一步会自动完成，请耐心等待约 1 分钟。
"%ROOT%\AstrBot\AstrBot_4.29.4_windows_amd64_portable\backend\python\python.exe" "%ROOT%\setup_config.py" "%DS_KEY%" "%OWNER_QQ%" "%ROOT%"

echo.
echo [6/6] 部署完成！配置已全部自动完成，接下来只需两步：
echo.
echo   ① 双击《启动NapCat.bat》，扫码登录你的 QQ 小号；
echo   ② 双击《启动AstrBot.bat》，浏览器打开 http://127.0.0.1:6185 。
echo      无需再手动填任何东西。
echo.
echo   然后回到 QQ 小号，发一句 /好感度 试试，她活了！
echo.
echo ==============================================
echo   部署完成！快去养她吧～
echo ==============================================
echo.
pause
