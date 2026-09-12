@echo off
chcp 65001 > nul
title Test Hệ Thống Cảnh Báo Bot Mua/Bán Discord
echo =====================================================================
echo 🧪 ĐANG MỞ MENU KIỂM THỬ BOT CẢNH BÁO MUA / BÁN DISCORD...
echo =====================================================================
set PYTHONUTF8=1
cd /d "%~dp0\.."
call "%USERPROFILE%\.venv\Scripts\activate.bat"
python scripts\test_bot_alerts.py
pause
