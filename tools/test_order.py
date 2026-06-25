"""
test_order.py — Dispara UMA ordem DEMO e captura resposta + resultado.

Objetivo: aprender o formato real da resposta (id do trade, campos de win/loss)
para construir a deteccao de resultado e o gale com seguranca. SOMENTE DEMO.

Roda: py tools/test_order.py
"""

import os
import sys
import json
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import avanctus_client as ac

TMP = os.path.join(os.path.dirname(__file__), "..", ".tmp")
os.makedirs(TMP, exist_ok=True)

SYMBOL = "SOLUSDT.OTC"   # OTC = 24/7; se der "symbol not active", troco depois
AMOUNT = 25
DIRECTION = "BUY"        # CALL (so um teste; nao segue sinal)

def dump(nome, obj):
    open(os.path.join(TMP, nome), "w", encoding="utf-8").write(json.dumps(obj, ensure_ascii=False, indent=2, default=str))

print("Saldo DEMO antes:", ac.demo_balance())

print(f"\nAbrindo ordem DEMO: {SYMBOL} {DIRECTION} ${AMOUNT} (1min, candle close)...")
res = ac.open_trade(SYMBOL, AMOUNT, DIRECTION, is_demo=True, close_type="01:00")
dump("order_open.json", res)
print("Status:", res["status"], "| ok:", res["ok"])
print("Resposta:", json.dumps(res["body"], ensure_ascii=False)[:500])

if not res["ok"]:
    print("\nOrdem NAO foi aceita. Veja .tmp/order_open.json. (Pode ser JWT expirado ou simbolo inativo.)")
    sys.exit(0)

print("\nAcompanhando o resultado (~100s)...")
last = None
for i in range(11):
    time.sleep(10)
    try:
        trades = ac.recent_trades(limit=5)
        last = trades
        dump("trades_snapshot.json", trades)
        # tenta mostrar o trade mais recente de forma resumida
        arr = trades if isinstance(trades, list) else (trades.get("data") or trades.get("items") or [])
        if arr:
            t0 = arr[0]
            resumo = {k: t0.get(k) for k in ("id", "symbol", "amount", "direction", "status", "result", "pnl", "isDemo", "closePrice", "openPrice") if isinstance(t0, dict) and k in t0}
            print(f"  [{(i+1)*10}s]", json.dumps(resumo, ensure_ascii=False, default=str))
    except Exception as e:
        print("  erro ao consultar:", e)

print("\nSaldo DEMO depois:", ac.demo_balance())
print("\nArquivos salvos em .tmp/: order_open.json, trades_snapshot.json")
