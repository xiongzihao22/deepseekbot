@echo off
chcp 936 >nul
title 启动 AstrBot
setlocal enabledelayedexpansion

set "AST_ROOT=%~dp0..\..\astrbot"

REM 动态查找 AstrBot 便携版目录（不写死版本号）
set "ASTDIR="
for /d %%d in ("%AST_ROOT%\AstrBot_*_windows_amd64_portable") do set "ASTDIR=%%d"
if not defined ASTDIR (
    if exist "%AST_ROOT%\AstrBot.exe" set "ASTDIR=%AST_ROOT%"
)
if not defined ASTDIR (
    if exist "%AST_ROOT%\backend\launch_backend.py" set "ASTDIR=%AST_ROOT%"
)

if not defined ASTDIR (
    echo.
    echo   [错误] 没找到 AstrBot。
    echo   预期位置: %AST_ROOT%\AstrBot_*_windows_amd64_portable
    echo.
    echo   请先运行《一键部署.bat》。
    pause
    exit /b 1
)

cd /d "%ASTDIR%"

REM ---- 先带起桌宠守护进程（最小化运行，好感度到 60 后她才能到桌面） ----
set "PY=%ASTDIR%\backend\python\python.exe"
if not exist "%PY%" set "PY=python"
if exist "%~dp0pet_launcher.py" (
    start "桌宠守护" /min "%PY%" "%~dp0pet_launcher.py"
    echo   桌宠守护进程已启动（最小化窗口，别关它）
)

if exist "AstrBot.exe" (
    start "" "AstrBot.exe"
    echo.
    echo   AstrBot 已启动，稍等几秒后浏览器打开：http://localhost:6185
) else (
    echo.
    echo   启动后端（无桌面壳）...
    "%PY%" "backend\launch_backend.py"
)
echo.
pause
