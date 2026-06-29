"""
binance_client.py — Cliente da API da Binance (spot) para operar de verdade.
Suporta TESTNET (dinheiro fake, p/ validar sem risco) e REAL, via .env.

Config .env:
  BINANCE_API_KEY=...
  BINANCE_API_SECRET=...
  BINANCE_TESTNET=true     # true = ambiente de teste (fake). false = dinheiro real.

Seguranca: a chave deve ser criada SEM permissao de saque. Este cliente nunca saca.
"""
import os, time, hmac, hashlib, math, urllib.parse, requests

TESTNET = os.environ.get("BINANCE_TESTNET", "true").strip().lower() in ("1", "true", "yes", "sim")
BASE = "https://testnet.binance.vision" if TESTNET else "https://api.binance.com"
KEY = os.environ.get("BINANCE_API_KEY", "").strip()
SECRET = os.environ.get("BINANCE_API_SECRET", "").strip()

_offset = 0  # diferenca de relogio com o servidor


def _sync():
    global _offset
    try:
        srv = requests.get(f"{BASE}/api/v3/time", timeout=10).json()["serverTime"]
        _offset = srv - int(time.time() * 1000)
    except Exception:
        _offset = 0


def _signed(method, path, params=None):
    if not KEY or not SECRET:
        raise RuntimeError("BINANCE_API_KEY/SECRET nao configurados")
    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000) + _offset
    params["recvWindow"] = 5000
    qs = urllib.parse.urlencode(params)
    sig = hmac.new(SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = f"{BASE}{path}?{qs}&signature={sig}"
    headers = {"X-MBX-APIKEY": KEY}
    r = requests.request(method, url, headers=headers, timeout=20)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    return {"ok": r.status_code < 400, "status": r.status_code, "body": body}


def conta():
    """Saldos da conta. Retorna {ok, ambiente, saldos:{asset:free}, erro?}."""
    _sync()
    r = _signed("GET", "/api/v3/account")
    if not r["ok"]:
        return {"ok": False, "ambiente": "TESTNET" if TESTNET else "REAL", "erro": r["body"]}
    saldos = {b["asset"]: float(b["free"]) for b in r["body"].get("balances", []) if float(b["free"]) > 0}
    return {"ok": True, "ambiente": "TESTNET" if TESTNET else "REAL", "saldos": saldos}


def preco(symbol):
    try:
        return float(requests.get(f"{BASE}/api/v3/ticker/price",
                                  params={"symbol": symbol}, timeout=10).json()["price"])
    except Exception:
        return None


_filters = {}


def _load_filters():
    if _filters:
        return
    try:
        data = requests.get(f"{BASE}/api/v3/exchangeInfo", timeout=20).json()
        for s in data.get("symbols", []):
            flt = {f["filterType"]: f for f in s["filters"]}
            step = float(flt["LOT_SIZE"]["stepSize"]) if "LOT_SIZE" in flt else 0.0
            _filters[s["symbol"]] = step
    except Exception:
        pass


def ajustar_qty(symbol, qty):
    """Arredonda a quantidade pra baixo no passo (stepSize) que a Binance exige."""
    _load_filters()
    step = _filters.get(symbol, 0.0)
    if step <= 0:
        return qty
    q = math.floor(qty / step) * step
    s = f"{step:.10f}".rstrip("0")
    dec = len(s.split(".")[1]) if "." in s else 0
    return round(q, dec)


def _qty_str(qty):
    return f"{qty:.8f}".rstrip("0").rstrip(".")


def comprar(symbol, usdt):
    """Compra a mercado gastando 'usdt' dolares."""
    _sync()
    return _signed("POST", "/api/v3/order",
                   {"symbol": symbol, "side": "BUY", "type": "MARKET", "quoteOrderQty": round(usdt, 2)})


def vender(symbol, qty):
    """Vende a mercado 'qty' unidades (arredonda pro passo da Binance)."""
    q = ajustar_qty(symbol, qty)
    if q <= 0:
        return {"ok": False, "status": 0, "body": {"erro": "qty abaixo do minimo"}}
    _sync()
    return _signed("POST", "/api/v3/order",
                   {"symbol": symbol, "side": "SELL", "type": "MARKET", "quantity": _qty_str(q)})


def vender_usdt(symbol, usdt):
    """Vende a mercado o equivalente a 'usdt' dolares (parcial)."""
    _sync()
    return _signed("POST", "/api/v3/order",
                   {"symbol": symbol, "side": "SELL", "type": "MARKET", "quoteOrderQty": round(usdt, 2)})


if __name__ == "__main__":
    print("Ambiente:", "TESTNET (fake)" if TESTNET else "REAL ($$$)")
    c = conta()
    if c["ok"]:
        print("Conexao OK! Saldos:", c["saldos"])
    else:
        print("Falha:", c["erro"])
