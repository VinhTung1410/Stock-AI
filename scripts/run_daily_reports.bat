@echo off
chcp 65001 > nul
title Chay Bao Cao Nguyen Ngay va Dong Bo Watchlist
echo =====================================================================
echo [*] DANG CHAY BAO CAO NGUYEN NGAY (TRUA, CHIEU, AUDIT) VA SYNC WATCHLIST...
echo =====================================================================
set PYTHONUTF8=1
cd /d "%~dp0\.."
if exist "%USERPROFILE%\.venv\Scripts\activate.bat" (
    call "%USERPROFILE%\.venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)
python scripts\run_daily_reports_and_sync.py
pause
