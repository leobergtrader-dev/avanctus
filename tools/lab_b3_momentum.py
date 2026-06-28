"""
lab_b3_momentum.py — Momentum long-only numa carteira de acoes da B3 (Yahoo Finance, diario).
Mesma metodologia validada na crypto: ensemble TSMOM N=[30,50,80,100], long-only, vol targeting,
walk-forward por epoca, custos. Compara ao buy & hold do IBOVESPA.
Salva tools/b3_momentum_resultado.json.
"""
import os, sys, json, math, datetime, requests

sys.path.insert(0, os.path.dirname(__file__))
import lab_momentum_wf as wf

OUT = os.path.join(os.path.dirname(__file__), "b3_momentum_resultado.json")
UNIVERSO = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "B3SA3", "WEGE3", "BBAS3",
            "ITSA4", "RENT3", "SUZB3", "GGBR4", "RADL3", "LREN3", "EQTL3", "JBSS3",
            "CSAN3", "ELET3", "CMIG4", "VIVT3"]


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


def strat_long(serie):
    """Long-only ensemble TSMOM + vol targeting. Retorna date->ret_estrategia."""
    dates = [d for d, _ in serie]
    px = [p for _, p in serie]
    rets = [0.0] + [px[i] / px[i - 1] - 1 for i in range(1, len(px))]
    out = {}
    pa = 0.0
    for t in range(max(wf.NS) + 1, len(px)):
        sig = sum(1 if px[t] > px[t - N] else -1 for N in wf.NS) / len(wf.NS)
        sig = max(sig, 0.0)                                  # LONG-ONLY
        vol = wf.std(rets[t - wf.JANELA_VOL:t]) * math.sqrt(wf.ANUAL)
        scale = min(wf.ALVO_VOL / vol, wf.LEV_MAX) if vol > 0 else 0
        pos = sig * scale
        out[dates[t]] = pa * rets[t] - wf.CUSTO * abs(pa - pos)
        pa = pos
    return out


def main():
    porcoin = {}
    for s in UNIVERSO:
        d = yfetch(s + ".SA")
        if len(d) > max(wf.NS) + 60:
            porcoin[s] = strat_long(d)
        print(f"  {s}: {len(d)} dias")
    ibov = dict((d, p) for d, p in yfetch("%5EBVSP"))
    idates = sorted(ibov)
    ibov_ret = {idates[i]: ibov[idates[i]] / ibov[idates[i - 1]] - 1 for i in range(1, len(idates))}

    alldates = sorted(set(d for c in porcoin.values() for d in c) & set(ibov_ret))
    port, bench, datas = [], [], []
    for d in alldates:
        ss = [porcoin[c][d] for c in porcoin if d in porcoin[c]]
        if ss:
            port.append(sum(ss) / len(ss)); bench.append(ibov_ret[d]); datas.append(d)
    n = len(port)
    print(f"\nDias: {n} | acoes: {len(porcoin)}\n")

    K = 6; sz = n // K; epocas = []
    for i in range(K):
        a, b = i * sz, (i + 1) * sz if i < K - 1 else n
        ini = datetime.datetime.fromtimestamp(datas[a] / 1000, datetime.UTC).strftime("%Y-%m")
        epocas.append({"periodo": ini, "estrategia": wf.metricas(port[a:b]), "ibov": wf.metricas(bench[a:b])})

    res = {"n_dias": n, "acoes": list(porcoin),
           "geral_estrategia": wf.metricas(port), "geral_ibov": wf.metricas(bench), "epocas": epocas}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=== WALK-FORWARD por epoca (Momentum B3 vs IBOV) ===")
    print(f"{'periodo':9} {'ESTRAT Sharpe/CAGR':>22} {'IBOV Sharpe/CAGR':>20}")
    for e in epocas:
        es, ib = e["estrategia"], e["ibov"]
        if es and ib:
            print(f"{e['periodo']:9} {es['sharpe']:>8} / {es['cagr']:>6}%   {ib['sharpe']:>8} / {ib['cagr']:>6}%")
    g, gi = res["geral_estrategia"], res["geral_ibov"]
    print(f"\nGERAL Momentum B3: Sharpe {g['sharpe']} CAGR {g['cagr']}% MaxDD {g['maxdd']}%")
    print(f"GERAL Ibovespa   : Sharpe {gi['sharpe']} CAGR {gi['cagr']}% MaxDD {gi['maxdd']}%")


if __name__ == "__main__":
    main()
