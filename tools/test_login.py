"""
test_login.py — Valida o login automatico (email+senha do .env). Nao opera nada.
Roda: py tools/test_login.py
"""
import os, sys
from datetime import datetime
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import avanctus_client as ac

print("Testando login automatico (email + senha do .env)...\n")
try:
    token = ac.get_bearer(force=True)   # forca um login novo
    exp, tn = ac._decode(token)
    print("LOGIN OK ✔")
    print("Tenant:", tn)
    if exp:
        print("JWT valido ate:", datetime.fromtimestamp(exp).strftime("%d/%m/%Y %H:%M"))
    print("Saldo DEMO:", ac.demo_balance())
    print("\nTudo certo! O robo (5-ROBO.bat) ja vai logar e renovar sozinho.")
except Exception as e:
    print("FALHOU:", e)
    print("\nVerifique AVANCTUS_EMAIL e AVANCTUS_PASSWORD no .env.")
    print("Se sua conta tem 2FA por app, preencha AVANCTUS_2FA_SECRET.")
