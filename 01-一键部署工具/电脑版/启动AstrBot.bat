@echo off
chcp 936 >nul
title 启动 AstrBot
echo.
echo   正在启动 AstrBot ...
echo.

cd /d "%~dp0..\..strbot\AstrBot_4.29.4_windows_amd64_portable"
if not exist "AstrBot.exe" (
  echo   [错误] 找不到 AstrBot，请确认 astrbot 文件夹存在
  pause
  exit /b 1
)

REM ---- 先带起桌宠守护进程（最小化运行，好感度到 60 后她才能到桌面） ----
set "PY=%~dp0..\..strbot\AstrBot_4.29.4_windows_amd64_portableackend\python\python.exe"
if not exist "%PY%" set "PY=python"
start "桌宠守护" /min "%PY%" "%~dp0pet_launcher.py"
echo   桌宠守护进程已启动（最小化）

start "" "AstrBot.exe"
echo   AstrBot 已启动，稍等几秒后浏览器打开：http://localhost:6185
echo.
pause
