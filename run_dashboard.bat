@echo off
set PYTHONUTF8=1
echo ===================================================
echo     DANG KHOI DONG AI STOCK COPILOT DASHBOARD
echo ===================================================
echo Vui long doi trong giay lat...
"%USERPROFILE%\.venv\Scripts\streamlit.exe" run app.py
pause
