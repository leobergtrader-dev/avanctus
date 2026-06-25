@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   RELATORIO DE ESTATISTICAS
echo ============================================
echo.
py tools\analisar.py
echo.
echo ============================================
pause
