"""
lab_momentum_refine.py — Refino do momentum: variantes de posicao + blends com buy&hold.

Compara, no mesmo walk-forward (8+ anos, custos, vol targeting):
  - ls        : long-short (baseline)
  - long_only : so comprado (corta short)
  - long_bias : sempre vies comprador (0.5 + 0.5*sinal)
  - blendXX   : XX% estrategia ls + resto buy&hold (mistura protecao + alta)

Objetivo: achar variante com CAGR melhor que ls, mantendo drawdown bem abaixo do buy&hold,
e ROBUSTA por epoca. Salva tools/momentum_refine_resultado.json.
"""
import os, sys, json, math, datetime

sys.path.insert(0, os.path.dirname(__file__))
import lab_momentum_wf as wf

OUT = os.path.join(os.path.dirname(__file__), "momentum_refine_resultado.json")


def strat_coin_multi(serie):
    dates = [d for d, _ in serie]
    px = [p for _, p in serie]
    rets = [0.0] + [px[i] / px[i - 1] - 1 for i in range(1, len(px))]
    out = {}
    pa = {"ls": 0.0, "lo": 0.0, "lb": 0.0}
    for t in range(max(wf.NS) + 1, len(px)):
        sig = sum(1 if px[t] > px[t - N] else -1 for N in wf.NS) / len(wf.NS)
        vol = wf.std(rets[t - wf.JANELA_VOL:t]) * math.sqrt(wf.ANUAL)
        scale = min(wf.ALVO_VOL / vol, wf.LEV_MAX) if vol > 0 else 0
        pos = {"ls": sig * scale, "lo": max(sig, 0) * scale, "lb": (0.5 + 0.5 * sig) * scale}
        r = {}
        for k in pos:
            r[k] = pa[k] * rets[t] - wf.CUSTO * abs(pa[k] - pos[k])
        out[dates[t]] = (r["ls"], r["lo"], r["lb"], rets[t])
        pa = pos
    return out


def metr(rets):
    return wf.metricas(rets)


def por_epoca(serie, datas, K=6):
    n = len(serie); sz = n // K; eps = []
    for i in range(K):
        a, b = i * sz, (i + 1) * sz if i < K - 1 else n
        ini = datetime.datetime.fromtimestamp(datas[a] / 1000, datetime.UTC).strftime("%Y-%m")
        m = metr(serie[a:b])
        eps.append({"periodo": ini, "cagr": m["cagr"] if m else None})
    return eps


def main():
    porcoin = {}
    for s in wf.UNIVERSO:
        serie = wf.fetch_daily(s)
        if len(serie) > max(wf.NS) + 60:
            porcoin[s] = strat_coin_multi(serie)
    alldates = sorted(set(d for c in porcoin.values() for d in c))
    series = {"ls": [], "lo": [], "lb": [], "bh": []}
    datas = []
    for d in alldates:
        vals = [porcoin[c][d] for c in porcoin if d in porcoin[c]]
        if not vals:
            continue
        for idx, k in enumerate(("ls", "lo", "lb", "bh")):
            series[k].append(sum(v[idx] for v in vals) / len(vals))
        datas.append(d)
    n = len(datas)
    print(f"Dias: {n} | moedas: {len(porcoin)}\n")

    # blends da ls com buy&hold
    for w in (0.3, 0.5, 0.7):
        series[f"blend{int(w*100)}"] = [w * series["ls"][i] + (1 - w) * series["bh"][i] for i in range(n)]

    variantes = ["ls", "lo", "lb", "blend30", "blend50", "blend70", "bh"]
    nomes = {"ls": "Long-Short", "lo": "Long-only", "lb": "Long-bias",
             "blend30": "30% estr+70% hold", "blend50": "50/50", "blend70": "70% estr+30% hold", "bh": "Buy & Hold"}
    resultado = {"n_dias": n, "geral": {}, "epocas": {}}
    for v in variantes:
        resultado["geral"][v] = {"nome": nomes[v], **(metr(series[v]) or {})}
        resultado["epocas"][v] = por_epoca(series[v], datas)
    json.dump(resultado, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=== COMPARACAO GERAL (8+ anos) ===")
    print(f"{'variante':22} {'Sharpe':>7} {'CAGR':>8} {'MaxDD':>7}")
    for v in variantes:
        g = resultado["geral"][v]
        print(f"{nomes[v]:22} {g['sharpe']:>7} {g['cagr']:>7}% {g['maxdd']:>6}%")
    print("\n=== CAGR POR EPOCA ===")
    eps_lbl = [e["periodo"] for e in resultado["epocas"]["ls"]]
    print("variante              " + " ".join(f"{p:>8}" for p in eps_lbl))
    for v in variantes:
        print(f"{nomes[v]:22}" + " ".join(f"{(e['cagr'] if e['cagr'] is not None else 0):>7}%" for e in resultado["epocas"][v]))


if __name__ == "__main__":
    main()
