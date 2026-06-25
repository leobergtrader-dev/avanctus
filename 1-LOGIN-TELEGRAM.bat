@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   LOGIN NO TELEGRAM (rodar uma vez so)
echo ============================================
echo.
py tools\telegram_login.py
echo.
echo ============================================
pause
