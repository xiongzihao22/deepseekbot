@echo off
chcp 936 >nul
title 启动 NapCat
setlocal enabledelayedexpansion

set "NAP_ROOT=%~dp0..\..\napcat"

REM 动态查找 NapCat.*.Shell（QQ 升级后目录名会变，不能写死版本号）
set "NAPDIR="
for /d %%d in ("%NAP_ROOT%\NapCat.*.Shell") do set "NAPDIR=%%d"
if not defined NAPDIR (
    if exist "%NAP_ROOT%\NapCatWinBootMain.exe" set "NAPDIR=%NAP_ROOT%"
)

if not defined NAPDIR (
    echo.
    echo   [错误] 没找到 NapCat。
    echo   预期位置: %NAP_ROOT%\NapCat.*.Shell
    echo.
    echo   请先运行《一键部署.bat》，或在 NapCat 安装器里完成安装。
    pause
    exit /b 1
)

cd /d "%NAPDIR%"
if not exist "NapCatWinBootMain.exe" (
    echo   [错误] %NAPDIR% 里没有 NapCatWinBootMain.exe
    pause
    exit /b 1
)
if not exist "QQ.exe" (
    echo   [错误] %NAPDIR% 里没有 QQ.exe
    pause
    exit /b 1
)

echo.
echo   正在启动 NapCat（带 hook 注入）...
echo   目录: %NAPDIR%
echo   启动参数: QQ.exe + NapCatWinBootHook.dll
echo.
NapCatWinBootMain.exe QQ.exe NapCatWinBootHook.dll
echo.
echo   NapCat 已退出
pause
