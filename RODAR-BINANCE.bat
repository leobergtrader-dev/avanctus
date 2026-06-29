@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TRADE IA - Executor Binance
echo Iniciando executor Binance... (deixe esta janela aberta)
py tools\run_binance.py
pause
