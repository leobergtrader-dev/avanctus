"""
avanctus_client.py — Cliente da API da Avanctus (Layer 3).

Autentica como o site: Bearer JWT + x-tenant-id (lidos de .tmp/captura.txt ou .env).
Funcoes: saldo, abrir ordem, listar trades recentes, achar resultado de um trade.

SEGURANCA (invariante): abrir ordem REAL (isDemo=False) exige REAL_TRADING_ENABLED=yes no .env.
Por padrao tudo e DEMO.
"""

import os
import re
import json
import requests

BASE_URL = "https://broker-api.mybrokerdev.com"
ORIGIN = "https://app.avanctus.com"
_ROOT = os.path.dirname(os.path.dirname(__file__))
_CAPTURE = os.path.join(_ROOT, ".tmp", "captura.txt")


def load_auth():
    """Retorna (bearer, tenant) de .env ou da captura do navegador."""
    bearer = os.environ.get("AUTH_BEARER", "").strip()
    tenant = os.environ.get("TENANT_ID", "").strip()
    if (not bearer or not tenant) and os.path.exists(_CAPTURE):
        txt = open(_CAPTURE, encoding="utf-8").read()
        b = re.search(r"authorization:\s*Bearer\s+([A-Za-z0-9._\-]+)", txt, re.I)
        t = re.search(r"x-tenant-id:\s*([A-Za-z0-9]+)", txt, re.I)
        if not bearer and b:
            bearer = b.group(1)
        if not tenant and t:
            tenant = t.group(1)
    return bearer, tenant


def _headers():
    bearer, tenant = load_auth()
    if not bearer or not tenant:
        raise RuntimeError("Sem autenticacao: gere .tmp/captura.txt (Copy as cURL) ou .env.")
    return {
        "Authorization": f"Bearer {bearer}",
        "x-tenant-id": tenant,
        "Origin": ORIGIN,
        "Referer": ORIGIN + "/",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }


def get_wallets():
    r = requests.get(f"{BASE_URL}/auth/me", headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("wallets", [])


def demo_balance():
    for w in get_wallets():
        if w.get("type") == "DEMO":
            return w.get("balance")
    return None


def open_trade(symbol, amount, direction, is_demo=True,
               close_type="01:00", expiration_type="CANDLE_CLOSE", nitro=False):
    """Abre uma ordem. direction: 'BUY' (CALL) ou 'SELL' (PUT)."""
    if not is_demo and os.environ.get("REAL_TRADING_ENABLED", "").lower() != "yes":
        raise RuntimeError("BLOQUEIO: ordem REAL desativada. Defina REAL_TRADING_ENABLED=yes no .env para liberar.")
    body = {
        "symbol": symbol,
        "amount": amount,
        "direction": direction,
        "isDemo": is_demo,
        "expirationType": expiration_type,
        "closeType": close_type,
        "nitro": nitro,
    }
    r = requests.post(f"{BASE_URL}/trades/open-async", headers=_headers(), json=body, timeout=15)
    ok = r.status_code < 300
    try:
        data = r.json()
    except ValueError:
        data = r.text[:400]
    return {"ok": ok, "status": r.status_code, "body": data, "enviado": body}


def recent_trades(limit=10):
    r = requests.get(f"{BASE_URL}/trades", headers=_headers(),
                     params={"page": 1, "limit": limit}, timeout=15)
    r.raise_for_status()
    return r.json()
