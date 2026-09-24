@echo off
chcp 65001 > nul
set PYTHONUTF8=1
title AI Stock Copilot Dashboard
echo ===================================================
echo     DANG KHOI DONG AI STOCK COPILOT DASHBOARD
echo ===================================================
echo Vui long doi trong giay lat...
cd /d "%~dp0\.."
if exist "%USERPROFILE%\.venv\Scripts\activate.bat" (
    call "%USERPROFILE%\.venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)
python -m streamlit run app.py
pause
