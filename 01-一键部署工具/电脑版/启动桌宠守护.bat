@echo off
chcp 936 >nul
title 桌宠守护进程
echo.
echo   深海小鲸 · 桌宠守护进程
echo   保持这个窗口开着，她才能随时来到你的桌面。
echo.
cd /d "%~dp0"

set "PY=%~dp0..\..strbot\AstrBot_4.29.4_windows_amd64_portableackend\python\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0pet_launcher.py"
echo.
echo   [已停止] 守护进程退出，桌宠将无法自动出现。
pause
