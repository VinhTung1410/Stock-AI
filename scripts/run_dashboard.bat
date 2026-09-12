@echo off
chcp 65001 > nul
set PYTHONUTF8=1
echo ===================================================
echo     DANG KHOI DONG AI STOCK COPILOT DASHBOARD
echo ===================================================
echo Vui long doi trong giay lat...
cd /d "%~dp0\.."
"%USERPROFILE%\.venv\Scripts\streamlit.exe" run app.py
pause
