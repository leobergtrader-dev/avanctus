@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   TESTE DE ORDEM (1 ordem DEMO de $25)
echo   Somente conta DEMO. Aguarde ~2 minutos.
echo ============================================
echo.
py tools\test_order.py
echo.
echo ============================================
pause
