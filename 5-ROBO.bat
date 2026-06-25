@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   ROBO TRADE IA  (conta DEMO)
echo   Para PARAR: feche esta janela ou Ctrl+C
echo ============================================
echo.
py tools\bot.py
echo.
echo ============================================
pause
