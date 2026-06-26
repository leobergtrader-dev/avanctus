"""
lab_momentum.py — Laboratorio de pesquisa: Time-Series Momentum em cripto (Binance, diario).

Hipotese: ativos que subiram nas ultimas N barras tendem a continuar (momentum/tendencia).
Testa varios N, long-only e long-short, por moeda e em carteira; com CUSTOS, OUT-OF-SAMPLE
(treino 70% / teste 30%) e comparado a BUY & HOLD. So vale se bater o buy & hold no teste.

Metricas: CAGR, Sharpe (anualizado), Max Drawdown, % tempo no mercado, nº de trades.
Salva tools/momentum_resultado.json. Roda: py tools/lab_momentum.py
"""
import os, sys, json, math, requests

OUT = os.path.join(os.path.dirname(__file__), "momentum_resultado.json")
UNIVERSO = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "XRPUSDT",
            "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
NS = [10, 20, 30, 50, 100]
CUSTO = 0.001          # 0.1% por mudanca de posicao
ANUAL = 365


def closes_diario(symbol, limit=1000):
    try:
        r = requests.get("https://api.binance.com/api/v3/klines",
                         params={"symbol": symbol, "interval": "1d", "limit": limit}, timeout=20)
        return [(k[0], float(k[4])) for k in r.json()]
    except Exception:
        return []


def metricas(rets):
    """rets: lista de retornos diarios da estrategia."""
    if not rets:
        return None
    eq = 1.0
    peak = 1.0
    maxdd = 0.0
    for r in rets:
        eq *= (1 + r)
        peak = max(peak, eq)
        maxdd = max(maxdd, (peak - eq) / peak)
    dias = len(rets)
    total = eq - 1
    cagr = (eq ** (ANUAL / dias) - 1) if dias > 0 else 0
    mu = sum(rets) / dias
    var = sum((x - mu) ** 2 for x in rets) / dias
    sd = math.sqrt(var)
    sharpe = (mu / sd * math.sqrt(ANUAL)) if sd > 0 else 0
    return {"cagr": round(cagr * 100, 1), "sharpe": round(sharpe, 2),
            "maxdd": round(maxdd * 100, 1), "total": round(total * 100, 1)}


def backtest(closes, N, modo):
    """modo: 'long' (1/0) ou 'ls' (1/-1). Retorna (rets_estrategia, rets_buyhold, n_trades, exposicao)."""
    precos = [c[1] for c in closes]
    rets_bh = [precos[i] / precos[i - 1] - 1 for i in range(1, len(precos))]
    pos = [0.0] * len(precos)
    for t in range(N, len(precos)):
        up = precos[t] > precos[t - N]
        pos[t] = 1.0 if up else (0.0 if modo == "long" else -1.0)
    rets = []
    trades = 0
    expo = 0
    for t in range(N + 1, len(precos)):
        p = pos[t - 1]                       # posicao decidida ontem (sem lookahead)
        mudou = abs(pos[t - 1] - pos[t - 2])
        r = p * (precos[t] / precos[t - 1] - 1) - CUSTO * mudou
        rets.append(r)
        if mudou > 0:
            trades += 1
        if p != 0:
            expo += 1
    return rets, rets_bh[N:], trades, (round(100 * expo / len(rets), 0) if rets else 0)


def split(rets, frac=0.7):
    c = int(len(rets) * frac)
    return rets[:c], rets[c:]


def main():
    dados = {}
    for s in UNIVERSO:
        d = closes_diario(s)
        if len(d) > 200:
            dados[s] = d
        print(f"  {s}: {len(d)} dias")
    print(f"\nMoedas: {len(dados)} | custo {CUSTO*100}%/trade\n")

    resultado = {"universo": list(dados), "ns": NS, "por_estrategia": {}}

    for modo in ("long", "ls"):
        for N in NS:
            # carteira: media dos retornos das moedas (equal weight)
            todas = []
            bh_todas = []
            trades_tot = 0
            for s, d in dados.items():
                rets, bh, tr, _ = backtest(d, N, modo)
                todas.append(rets)
                bh_todas.append(bh)
                trades_tot += tr
            L = min(len(x) for x in todas)
            port = [sum(todas[i][-L:][t] for i in range(len(todas))) / len(todas) for t in range(L)]
            bh_port = [sum(bh_todas[i][-L:][t] for i in range(len(bh_todas))) / len(bh_todas) for t in range(L)]
            tr_in, tr_out = split(port)
            bh_in, bh_out = split(bh_port)
            chave = f"{modo}_N{N}"
            resultado["por_estrategia"][chave] = {
                "treino": metricas(tr_in), "teste": metricas(tr_out),
                "buyhold_teste": metricas(bh_out), "trades": trades_tot,
            }

    # buy & hold puro da carteira (referencia)
    resultado["buyhold_carteira"] = metricas(bh_port)

    json.dump(resultado, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=== MOMENTUM (carteira) — TESTE out-of-sample vs BUY & HOLD ===")
    print(f"{'estrategia':12} {'Sharpe_teste':>12} {'CAGR_teste':>11} {'MaxDD':>7} {'BH_Sharpe':>10} {'BH_CAGR':>9}")
    for k, v in resultado["por_estrategia"].items():
        t = v["teste"]; b = v["buyhold_teste"]
        if t and b:
            print(f"{k:12} {t['sharpe']:>12} {t['cagr']:>10}% {t['maxdd']:>6}% {b['sharpe']:>10} {b['cagr']:>8}%")
    bh = resultado["buyhold_carteira"]
    print(f"\nBuy & Hold carteira (total): Sharpe {bh['sharpe']} CAGR {bh['cagr']}% MaxDD {bh['maxdd']}%")


if __name__ == "__main__":
    main()
