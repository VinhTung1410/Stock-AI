@echo off
chcp 65001 > nul
title Trading Bot Canh Thị Trường Chứng Khoán 24/7
echo =====================================================================
echo 🤖 ĐANG KHỞI ĐỘNG TRADING BOT CANH THỊ TRƯỜNG & BẮN CẢNH BÁO DISCORD...
echo =====================================================================
set PYTHONUTF8=1
call "%USERPROFILE%\.venv\Scripts\activate.bat"
python trading_bot.py
pause
