@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   OUVINDO SINAIS DO CANAL (Ctrl+C para sair)
echo ============================================
echo.
py tools\telegram_listen.py
echo.
echo ============================================
pause
