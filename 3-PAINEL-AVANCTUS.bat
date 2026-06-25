@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   PAINEL AVANCTUS (somente leitura)
echo   Abrindo http://localhost:3000 no navegador
echo   (Feche esta janela para parar o painel)
echo ============================================
echo.
start "" http://localhost:3000
call npm start
echo.
pause
