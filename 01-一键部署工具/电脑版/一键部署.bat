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
echo   本脚本会自动完成：下载、解压、安装插件、注入人设
echo   你只需要填两样：QQ 号 + DeepSeek API Key
echo.

REM ================= 路径 =================
REM 工具目录：插件、配置脚本都在这里
set "TOOLS=%~dp0"
set "TOOLS=%TOOLS:~0,-1%"
REM 组件目录：astrbot / napcat 装在这里（项目根，和启动脚本保持一致）
for %%i in ("%TOOLS%\..\..") do set "COMP=%%~fi"

echo   工具目录: %TOOLS%
echo   组件目录: %COMP%
echo.

REM ================= 环境检查 =================
where powershell >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 PowerShell，无法继续。
    pause
    exit /b 1
)

set "HAS_CURL=0"
where curl >nul 2>nul
if not errorlevel 1 set "HAS_CURL=1"

REM ================= 下载地址 =================
REM 如失效，可替换为最新 Release 直链
set "NAPCAT_URL=https://github.com/NapNeko/NapCatQQ/releases/download/v4.18.42/NapCat.Shell.Windows.OneKey.zip"
set "ASTRBOT_URL=https://github.com/AstrBotDevs/AstrBot-desktop/releases/download/v4.29.4/AstrBot_4.29.4_windows_amd64_portable.zip"

echo [1/6] 收集信息（只问你这一次）
echo.
set /p OWNER_QQ=  你的 QQ 号（成为小鲸唯一的主人）:
set /p DS_KEY=  你的 DeepSeek API Key（sk- 开头）:
echo.

if "%OWNER_QQ%"=="" (
    echo [错误] QQ 号不能为空。
    pause
    exit /b 1
)
if "%DS_KEY%"=="" (
    echo [错误] DeepSeek Key 不能为空。
    pause
    exit /b 1
)

echo [2/6] 创建目录 ...
if not exist "%COMP%\napcat" mkdir "%COMP%\napcat" >nul 2>nul
if not exist "%COMP%\astrbot" mkdir "%COMP%\astrbot" >nul 2>nul
echo   完成

echo.
echo [3/6] 下载组件（约 200MB，请耐心等待）...
echo.
set "NAP_ZIP=%TEMP%\napcat_onekey.zip"
set "AST_ZIP=%TEMP%\astrbot_portable.zip"

call :download "%NAPCAT_URL%" "%NAP_ZIP%"
call :download "%ASTRBOT_URL%" "%AST_ZIP%"

if not exist "%NAP_ZIP%" (
    echo   [跳过] NapCat 未下载成功，请手动下载后解压到 %COMP%\napcat\
) else (
    echo   解压 NapCat ...
    powershell -NoProfile -Command "Expand-Archive -Path '%NAP_ZIP%' -DestinationPath '%COMP%\napcat' -Force" >nul 2>nul
)
if not exist "%AST_ZIP%" (
    echo   [跳过] AstrBot 未下载成功，请手动下载后解压到 %COMP%\astrbot\
) else (
    echo   解压 AstrBot ...
    powershell -NoProfile -Command "Expand-Archive -Path '%AST_ZIP%' -DestinationPath '%COMP%\astrbot' -Force" >nul 2>nul
)

echo.
echo [4/6] 准备 NapCat（首次需下载内置 QQ，约 300MB）
set "NAP_INSTALLED=0"
dir /b /ad "%COMP%\napcat\NapCat.*.Shell" >nul 2>nul && set "NAP_INSTALLED=1"
if "%NAP_INSTALLED%"=="1" (
    echo   已安装过，跳过
) else (
    if exist "%COMP%\napcat\NapCatInstaller.exe" (
        echo   即将打开 NapCat 安装器，请在弹出的窗口里按提示完成安装
        echo   （安装完成后回到这里按任意键继续）
        pause
        start /wait "" "%COMP%\napcat\NapCatInstaller.exe"
    ) else (
        echo   [提示] 未找到 NapCatInstaller.exe，请手动运行一次
    )
)

echo.
echo [5/6] 首次启动 AstrBot 并自动配置（约 1 分钟）...
set "PY=%COMP%\astrbot\AstrBot_4.29.4_windows_amd64_portable\backend\python\python.exe"
if not exist "%PY%" (
    echo.
    echo   [错误] 找不到 AstrBot 的 python：
    echo          %PY%
    echo   请确认已解压到 %COMP%\astrbot\
    pause
    exit /b 1
)
"%PY%" "%TOOLS%\setup_config.py" "%DS_KEY%" "%OWNER_QQ%" "%TOOLS%" "%COMP%"
if errorlevel 1 (
    echo.
    echo   [警告] 自动配置过程中有报错，请查看上面的输出。
    pause
)

echo.
echo [6/6] 部署完成！接下来两步：
echo.
echo   ① 双击《启动NapCat.bat》，扫码登录你的 QQ 小号
echo   ② 双击《启动AstrBot.bat》，浏览器打开 http://127.0.0.1:6185
echo.
echo   然后回 QQ 发一句 /好感度 试试，她活了。
echo.
echo  ==============================================
echo   部署完成！快去养她吧～
echo  ==============================================
echo.
pause
exit /b 0

REM ================= 下载子过程 =================
:download
if exist "%~2" (
    for %%A in ("%~2") do (
        if %%~zA GTR 1000000 (
            echo   已存在，跳过：%~nx2
            exit /b 0
        )
    )
)
echo   下载 %~nx2 ...
if "%HAS_CURL%"=="1" (
    curl -k -L --connect-timeout 20 -o "%~2" "%~1" 2>nul
) else (
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%~1' -OutFile '%~2' -UseBasicParsing } catch { exit 1 }" >nul 2>nul
)
if exist "%~2" (
    for %%A in ("%~2") do echo     完成 %%~zA 字节
) else (
    echo     [失败] %~nx2 下载失败，请检查网络或代理
)
exit /b 0
