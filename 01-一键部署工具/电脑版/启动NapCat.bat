@echo off
chcp 936 >nul
title 启动 NapCat
echo.
echo   正在启动 NapCat（带 hook 注入）...
echo.
cd /d "%~dp0..\..\napcat\NapCat.52230.Shell"
if not exist "NapCatWinBootMain.exe" (
  echo   [错误] 找不到 NapCat，请确认 D:\Studying\deepseekbot\napcat\NapCat.52230.Shell 存在
  pause
  exit /b 1
)
if not exist "QQ.exe" (
  echo   [错误] 找不到 QQ.exe
  pause
  exit /b 1
)
echo   启动参数: QQ.exe + NapCatWinBootHook.dll
echo.
NapCatWinBootMain.exe QQ.exe NapCatWinBootHook.dll
echo.
echo   NapCat 已退出
pause
