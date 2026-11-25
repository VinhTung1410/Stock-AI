@echo off
chcp 65001 > nul
title Tao Bao Cao Daily Research Digest Cho Claude
echo =====================================================================
echo [*] DANG CHAY PIPELINE TAO BAO CAO RESEARCH BRIEFING CHO CLAUDE...
echo [*] Tu dong cap nhat loi nhuan da ky va dong bo Supabase DB.
echo =====================================================================
set PYTHONUTF8=1
cd /d "%~dp0\.."
if exist "%USERPROFILE%\.venv\Scripts\activate.bat" (
    call "%USERPROFILE%\.venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)
python scripts\generate_daily_digest.py %*
pause
