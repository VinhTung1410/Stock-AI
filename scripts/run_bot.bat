@echo off
chcp 65001 > nul
title Trading Bot Canh Thi Truong Chung Khoan 24/7
echo =====================================================================
echo [*] DANG KHOI DONG TRADING BOT CANH THI TRUONG VA BAN CANH BAO DISCORD...
echo =====================================================================
set PYTHONUTF8=1
cd /d "%~dp0\.."
if exist "%USERPROFILE%\.venv\Scripts\activate.bat" (
    call "%USERPROFILE%\.venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)
python trading_bot.py
pause
