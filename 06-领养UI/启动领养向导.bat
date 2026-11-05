@echo off
chcp 936 >nul
title 深海小鲸 · 领养向导
cd /d "%~dp0"

echo.
echo   ==============================================
echo     深海小鲸 · 领养向导
echo   ==============================================
echo.
echo   正在唤醒领养向导...

set "PY=%~dp0..\astrbot\AstrBot_4.29.4_windows_amd64_portable\backend\python\python.exe"
if not exist "%PY%" (
  echo   [错误] 未找到 AstrBot 内置 Python，请确认 astrbot 目录已解压完整
  pause
  exit /b 1
)

start "领养向导-后端" "%PY%" "%~dp0app.py"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5199

echo   浏览器应已打开：http://127.0.0.1:5199
echo   若没打开，等几秒手动访问；仍不行请把本窗口内容截图。
echo.
pause
