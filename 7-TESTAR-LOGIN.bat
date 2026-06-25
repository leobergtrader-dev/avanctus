@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   TESTE DE LOGIN AUTOMATICO
echo ============================================
echo.
py tools\test_login.py
echo.
echo ============================================
pause
