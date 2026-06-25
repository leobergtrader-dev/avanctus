@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   TRADE IA - PAINEL
echo   Abrindo http://localhost:3000
echo   (Feche esta janela para encerrar o painel)
echo ============================================
echo.
start "" http://localhost:3000
py tools\painel.py
echo.
pause
