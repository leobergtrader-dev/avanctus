"""
avanctus_client.py — Cliente da API da Avanctus (Layer 3) com LOGIN AUTOMATICO.

Autenticacao: Bearer JWT + x-tenant-id.
Origem do JWT (nesta ordem):
  1) Login automatico com AVANCTUS_EMAIL/PASSWORD (renova sozinho; cache em .tmp/jwt.json)
  2) .tmp/captura.txt (Copy as cURL) ou AUTH_BEARER no .env (fallback manual)

Renova o JWT quando expira ou em qualquer 401. Suporta 2FA opcional (AVANCTUS_2FA_SECRET).
SEGURANCA: ordem REAL (isDemo=False) exige REAL_TRADING_ENABLED=yes no .env.
"""

import os
import re
import json
import time
import base64
import requests

BASE_URL = "https://broker-api.mybrokerdev.com"
ORIGIN = "https://app.avanctus.com"
_ROOT = os.path.dirname(os.path.dirname(__file__))
_CAPTURE = os.path.join(_ROOT, ".tmp", "captura.txt")
_JWT_CACHE = os.path.join(_ROOT, ".tmp", "jwt.json")


def _env(k, d=""):
    return os.environ.get(k, d).strip()


def _decode(jwt):
    """Retorna (exp, tenantId) do payload do JWT."""
    try:
        seg = jwt.split(".")[1]
        seg += "=" * (-len(seg) % 4)
        p = json.loads(base64.urlsafe_b64decode(seg))
        return p.get("exp"), p.get("tenantId")
    except Exception:
        return None, None


def _read_cache():
    try:
        return json.load(open(_JWT_CACHE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_cache(d):
    os.makedirs(os.path.dirname(_JWT_CACHE), exist_ok=True)
    json.dump(d, open(_JWT_CACHE, "w", encoding="utf-8"))


def _from_capture():
    bearer = tenant = None
    if os.path.exists(_CAPTURE):
        txt = open(_CAPTURE, encoding="utf-8").read()
        b = re.search(r"authorization:\s*Bearer\s+([A-Za-z0-9._\-]+)", txt, re.I)
        t = re.search(r"x-tenant-id:\s*([A-Za-z0-9]+)", txt, re.I)
        if b:
            bearer = b.group(1)
        if t:
            tenant = t.group(1)
    return bearer, tenant


def tenant_id():
    t = _env("TENANT_ID")
    if t:
        return t
    _, tc = _from_capture()
    if tc:
        return tc
    c = _read_cache()
    if c.get("token"):
        _, tj = _decode(c["token"])
        if tj:
            return tj
    return None


def _login():
    email, pwd = _env("AVANCTUS_EMAIL"), _env("AVANCTUS_PASSWORD")
    if not email or not pwd:
        raise RuntimeError("Sem AVANCTUS_EMAIL/PASSWORD no .env para login automatico.")
    body = {"email": email, "password": pwd}
    sec = _env("AVANCTUS_2FA_SECRET")
    if sec:
        import pyotp
        body["token"] = pyotp.TOTP(sec).now()
    headers = {
        "Origin": ORIGIN, "Referer": ORIGIN + "/",
        "Content-Type": "application/json", "Accept": "application/json, text/plain, */*",
    }
    tn = tenant_id()
    if tn:
        headers["x-tenant-id"] = tn
    r = requests.post(f"{BASE_URL}/auth/login", headers=headers, json=body, timeout=20)
    try:
        data = r.json()
    except ValueError:
        data = {}
    token = data.get("token") or (data.get("data") or {}).get("token")
    if r.status_code >= 300 or not token:
        raise RuntimeError(f"Login falhou ({r.status_code}): {json.dumps(data, ensure_ascii=False)[:200]}")
    exp, _ = _decode(token)
    _write_cache({"token": token, "exp": exp})
    return token


def get_bearer(force=False):
    if not force:
        c = _read_cache()
        if c.get("token"):
            exp = c.get("exp")
            if not exp or exp - time.time() > 120:   # ainda valido (margem 2 min)
                return c["token"]
    if _env("AVANCTUS_EMAIL") and _env("AVANCTUS_PASSWORD"):
        return _login()
    # fallback manual
    b = _env("AUTH_BEARER")
    if b:
        return b
    bc, _ = _from_capture()
    if bc:
        return bc
    raise RuntimeError("Sem JWT: configure AVANCTUS_EMAIL/PASSWORD ou .tmp/captura.txt")


def _headers():
    bearer, tn = get_bearer(), tenant_id()
    if not bearer or not tn:
        raise RuntimeError("Autenticacao incompleta (bearer/tenant).")
    return {
        "Authorization": f"Bearer {bearer}",
        "x-tenant-id": tn,
        "Origin": ORIGIN, "Referer": ORIGIN + "/",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }


def _request(method, path, **kw):
    r = requests.request(method, BASE_URL + path, headers=_headers(), timeout=15, **kw)
    if r.status_code == 401:                 # JWT morreu -> re-login e tenta 1x
        get_bearer(force=True)
        r = requests.request(method, BASE_URL + path, headers=_headers(), timeout=15, **kw)
    return r


# ---------------- API ----------------

def get_wallets():
    r = _request("GET", "/auth/me")
    r.raise_for_status()
    return r.json().get("wallets", [])


def demo_balance():
    for w in get_wallets():
        if w.get("type") == "DEMO":
            return w.get("balance")
    return None


def real_balance():
    for w in get_wallets():
        if w.get("type") == "REAL":
            return w.get("balance")
    return None


def open_trade(symbol, amount, direction, is_demo=True,
               close_type="01:00", expiration_type="CANDLE_CLOSE", nitro=False):
    if not is_demo and os.environ.get("REAL_TRADING_ENABLED", "").lower() != "yes":
        raise RuntimeError("BLOQUEIO: ordem REAL desativada. Defina REAL_TRADING_ENABLED=yes no .env.")
    body = {
        "symbol": symbol, "amount": amount, "direction": direction, "isDemo": is_demo,
        "expirationType": expiration_type, "closeType": close_type, "nitro": nitro,
    }
    r = _request("POST", "/trades/open-async", json=body)
    ok = r.status_code < 300
    try:
        data = r.json()
    except ValueError:
        data = r.text[:400]
    return {"ok": ok, "status": r.status_code, "body": data, "enviado": body}


def recent_trades(limit=10):
    r = _request("GET", "/trades", params={"page": 1, "limit": limit})
    r.raise_for_status()
    return r.json()
