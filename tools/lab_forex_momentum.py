"""
lab_forex_momentum.py — Momentum (TSMOM) no mercado de moedas (Forex), dados diarios do Yahoo.
Diferenca vs cripto: aqui o momentum e LONG/SHORT (compra a tendencia de alta E vende a de baixa),
porque moeda nao tem 'drift' de alta como cripto. Mesma metodologia: ensemble N=[30,50,80,100],
vol targeting, walk-forward por epoca, com custos. Compara long/short vs long-only vs buy&hold.
Salva tools/forex_momentum_resultado.json.
"""
import os, sys, json, math, datetime, requests

sys.path.insert(0, os.path.dirname(__file__))
import lab_momentum_wf as wf

# --- parametros CORRETOS pra forex (nao os de cripto) ---
NS = [60, 120, 180, 252]   # janelas longas (momentum classico de moedas ~12 meses)
ALVO_VOL = 0.10            # vol-alvo 10% a.a. (forex e calmo)
JANELA_VOL = 60
LEV_MAX = 2.0
CUSTO = 0.0002            # ~2 bps por giro (spread de major)
wf.ANUAL = 252            # forex opera ~252 dias/ano (metricas usa wf.ANUAL)

OUT = os.path.join(os.path.dirname(__file__), "forex_momentum_resultado.json")
PARES = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCHF=X",
         "USDCAD=X", "NZDUSD=X", "EURJPY=X", "EURGBP=X", "USDBRL=X"]


def yfetch(sym, rng="10y"):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                         params={"interval": "1d", "range": rng},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        res = r.json()["chart"]["result"][0]
        ts = res["timestamp"]
        cl = res["indicators"]["quote"][0]["close"]
        return [(ts[i] * 1000, cl[i]) for i in range(len(ts)) if cl[i] is not None]
    except Exception as e:
        print("  erro", sym, e)
        return []


def strat(serie, long_only=False):
    """TSMOM. long_only=False -> compra E vende (classico de forex)."""
    dates = [d for d, _ in serie]
    px = [p for _, p in serie]
    rets = [0.0] + [px[i] / px[i - 1] - 1 for i in range(1, len(px))]
    out = {}
    pa = 0.0
    for t in range(max(NS) + 1, len(px)):
        sig = sum(1 if px[t] > px[t - N] else -1 for N in NS) / len(NS)
        if long_only:
            sig = max(sig, 0.0)
        vol = wf.std(rets[t - JANELA_VOL:t]) * math.sqrt(wf.ANUAL)
        scale = min(ALVO_VOL / vol, LEV_MAX) if vol > 0 else 0
        pos = sig * scale
        out[dates[t]] = pa * rets[t] - CUSTO * abs(pa - pos)
        pa = pos
    return out


def carteira(series, **kw):
    por = {s: strat(series[s], **kw) for s in series}
    alldates = sorted(set(d for c in por.values() for d in c))
    port, datas = [], []
    for d in alldates:
        ss = [por[c][d] for c in por if d in por[c]]
        if ss:
            port.append(sum(ss) / len(ss)); datas.append(d)
    return port, datas


def main():
    series = {}
    for s in PARES:
        d = yfetch(s)
        if len(d) > max(wf.NS) + 60:
            series[s] = d
        print(f"  {s}: {len(d)} dias")

    ls_port, datas = carteira(series, long_only=False)
    lo_port, _ = carteira(series, long_only=True)
    # buy & hold equal-weight (referencia)
    bh = {}
    for s in series:
        px = [p for _, p in series[s]]
        ds = [d for d, _ in series[s]]
        for i in range(1, len(px)):
            bh.setdefault(ds[i], []).append(px[i] / px[i - 1] - 1)
    bh_dates = sorted(bh)
    bh_port = [sum(bh[d]) / len(bh[d]) for d in bh_dates]

    n = len(ls_port)
    K = 6; sz = n // K; epocas = []
    for i in range(K):
        a, b = i * sz, (i + 1) * sz if i < K - 1 else n
        ini = datetime.datetime.fromtimestamp(datas[a] / 1000, datetime.UTC).strftime("%Y-%m")
        epocas.append({"periodo": ini, "long_short": wf.metricas(ls_port[a:b])})

    res = {"n_dias": n, "pares": list(series),
           "long_short": wf.metricas(ls_port),
           "long_only": wf.metricas(lo_port),
           "buyhold": wf.metricas(bh_port),
           "epocas": epocas}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\nDias: {n} | pares: {len(series)}\n")
    print("=== WALK-FORWARD (Momentum Forex long/short) ===")
    for e in epocas:
        m = e["long_short"]
        if m:
            print(f"{e['periodo']:9} Sharpe {m['sharpe']:>6} / CAGR {m['cagr']:>6}% / MaxDD {m['maxdd']:>6}%")
    ls, lo, b = res["long_short"], res["long_only"], res["buyhold"]
    print(f"\nGERAL Long/Short : Sharpe {ls['sharpe']} CAGR {ls['cagr']}% MaxDD {ls['maxdd']}%")
    print(f"GERAL Long-only  : Sharpe {lo['sharpe']} CAGR {lo['cagr']}% MaxDD {lo['maxdd']}%")
    print(f"GERAL Buy&Hold   : Sharpe {b['sharpe']} CAGR {b['cagr']}% MaxDD {b['maxdd']}%")


if __name__ == "__main__":
    main()
