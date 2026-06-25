"""
market.py — Puxa candles reais (OHLCV) do agregador de precos da corretora.

Endpoint (UDF/datafeed): {SYMBOL_API_URL}/aggregated-prices/prices
  header: api-key   params: slot, pair, startTime, endTime, type, interval, skip, limit
Retorna velas de 1m: {time, open, close, high, low, vol}.
"""
import os
import time
import requests

API_URL = os.environ.get("SYMBOL_API_URL", "https://symbol-prices-aggregator.mybrokerdev.com").rstrip("/")
API_KEY = os.environ.get("SYMBOL_API_KEY", "Sl293kk22ss8")
ORIGIN = "https://app.avanctus.com"


def get_candles(ticker, interval="1m", limit=60, slot="default", tipo="otc"):
    """Retorna lista cronologica de candles {time,open,close,high,low,vol}."""
    now = int(time.time() * 1000)
    janela = limit * 60_000 * 3  # folga
    r = requests.get(
        f"{API_URL}/aggregated-prices/prices",
        headers={"api-key": API_KEY, "Origin": ORIGIN},
        params={"slot": slot, "pair": ticker, "startTime": now - janela, "endTime": now,
                "type": tipo, "interval": interval, "skip": 0, "limit": limit},
        timeout=12,
    )
    r.raise_for_status()
    out = []
    for c in r.json():
        out.append({
            "time": c.get("time"),
            "open": c.get("openPrice"),
            "close": c.get("closePrice"),
            "high": c.get("highPrice"),
            "low": c.get("lowPrice"),
            "vol": c.get("volume", 0),
        })
    out.sort(key=lambda x: x["time"] or 0)
    return out
