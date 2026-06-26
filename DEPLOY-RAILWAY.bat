@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   DEPLOY TRADE IA NO RAILWAY (sem GitHub)
echo ============================================
echo.
echo PASSO 1/3 - LOGIN
echo   Vai abrir o navegador. Confirme o acesso e volte aqui.
echo.
railway login
echo.
echo PASSO 2/3 - CRIAR O PROJETO
echo   Quando pedir o nome, digite por exemplo:  trade-ia
echo.
railway init
echo.
echo PASSO 3/3 - ENVIAR O CODIGO (build pode levar 1-2 min)
echo.
railway up
echo.
echo ============================================
echo   Concluido o envio!
echo   Agora va ao painel do Railway para:
echo     1) Variables  -> Raw Editor -> colar o .tmp\railway_env.txt
echo     2) Settings   -> Volumes -> Mount path  /app/.tmp
echo     3) Settings   -> Networking -> Generate Domain
echo ============================================
pause
