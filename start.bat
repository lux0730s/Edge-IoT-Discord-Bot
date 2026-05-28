@echo off
title Edge IoT System Launcher
echo ═══════════════════════════════════════════
echo   Edge IoT Device Monitoring System
echo   一鍵啟動腳本
echo ═══════════════════════════════════════════
echo.

REM 啟動 bridge.py（新視窗）
echo [1/2] 啟動網關層 bridge.py ...
start "Bridge - Edge IoT Gateway" cmd /c python bridge.py

REM 等待 2 秒確保 bridge 先連線
timeout /t 2 /nobreak >nul

REM 啟動 bot.py（新視窗）
echo [2/2] 啟動 Discord Bot bot.py ...
start "Bot - Discord Bot" cmd /c python bot.py

echo.
echo ✅ 兩個服務已啟動！
echo    - 網關層窗口標題: Bridge - Edge IoT Gateway
echo    - Bot 窗口標題: Bot - Discord Bot
echo.
echo 若要關閉，直接關閉兩個視窗即可。
echo ═══════════════════════════════════════════
pause