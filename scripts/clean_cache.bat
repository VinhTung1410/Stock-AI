@echo off
chcp 65001 > nul
echo ===================================================
echo   DANG DON DEP SACH CACHE __pycache__ VA BYTECODE
echo ===================================================
cd /d "%~dp0\.."
powershell -Command "Get-ChildItem -Path . -Filter '__pycache__' -Recurse | Remove-Item -Recurse -Force"
echo Hoan tat don dep sach se!
pause
