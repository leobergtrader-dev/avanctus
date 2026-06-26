"""
lab_grid_smart.py — GRID INTELIGENTE: grid + filtro de regime (anti-crash).

Regra: roda o grid normalmente quando o preco esta ACIMA da media longa (lateral/alta);
quando cai ABAIXO da media (tendencia de baixa), LIQUIDA pra caixa e pausa o grid.
Isso evita o "saco" dos crashes — o ponto fraco do grid puro.

Compara, nas mesmas 24 janelas (BTC/ETH, com taxas): grid puro vs grid inteligente vs buy&hold.
Salva tools/grid_smart_resultado.json. Roda: py tools/lab_grid_smart.py
"""
import os, sys, json, datetime

sys.path.insert(0, os.path.dirname(__file__))
import lab_grid as lg

OUT = os.path.join(os.path.dirname(__file__), "grid_smart_resultado.json")
TREND_H = 480          # media de regime ~20 dias (em horas)


def sma_series(precos, win):
    """SMA trailing por indice (usa prefix sums)."""
    pref = [0.0]
    for p in precos:
        pref.append(pref[-1] + p)
    out = []
    for t in range(len(precos)):
        a = max(0, t - win)
        out.append((pref[t + 1] - pref[a]) / (t + 1 - a))
    return out


def grid_smart(precos, smas, low, high, n, capital, fee):
    levels = [low + i * (high - low) / n for i in range(n + 1)]
    qty = [(capital / n) / levels[i] for i in range(n)]
    holding = [0.0] * n
    cash = capital
    p0 = precos[0]
    for t in range(1, len(precos)):
        p1 = precos[t]
        regime_up = p1 >= smas[t]
        if not regime_up:
            # tendencia de baixa: liquida tudo e pausa
            for i in range(n):
                if holding[i] > 0:
                    cash += holding[i] * p1 * (1 - fee); holding[i] = 0.0
            p0 = p1
            continue
        if p1 < p0:
            for i in range(n):
                if p1 <= levels[i] < p0 and holding[i] == 0:
                    cash -= qty[i] * levels[i] * (1 + fee); holding[i] = qty[i]
        elif p1 > p0:
            for i in range(n):
                if p0 < levels[i + 1] <= p1 and holding[i] > 0:
                    cash += holding[i] * levels[i + 1] * (1 - fee); holding[i] = 0.0
        p0 = p1
    final = precos[-1]
    valor = cash + sum(holding[i] * final for i in range(n))
    return round((valor / capital - 1) * 100, 1)


def main():
    resultado = {"config": {"N": lg.N, "faixa": lg.FAIXA, "trend_h": TREND_H}, "janelas": []}
    for sym in ["BTCUSDT", "ETHUSDT"]:
        serie = lg.fetch_hourly(sym)
        precos_full = [p for _, p in serie]
        smas_full = sma_series(precos_full, TREND_H)
        print(f"{sym}: {len(serie)} horas")
        passo = lg.JANELA_DIAS * 24
        i = 0
        while i + passo <= len(serie):
            bloco = serie[i:i + passo]
            precos = [p for _, p in bloco]
            smas = smas_full[i:i + passo]
            p_ini = precos[0]
            low, high = p_ini * (1 - lg.FAIXA), p_ini * (1 + lg.FAIXA)
            puro = lg.grid_backtest(precos, low, high, lg.N, lg.CAPITAL, lg.FEE)["net"]
            smart = grid_smart(precos, smas, low, high, lg.N, lg.CAPITAL, lg.FEE)
            bh = round((precos[-1] / precos[0] - 1) * 100, 1)
            ini = datetime.datetime.fromtimestamp(bloco[0][0] / 1000, datetime.UTC).strftime("%Y-%m")
            resultado["janelas"].append({"sym": sym, "inicio": ini, "grid_puro": puro,
                                         "grid_smart": smart, "buyhold": bh})
            i += passo

    js = resultado["janelas"]
    def med(k): return round(sum(j[k] for j in js) / len(js), 1)
    def pos(k): return sum(1 for j in js if j[k] > 0)
    resultado["resumo"] = {
        "n": len(js),
        "puro_medio": med("grid_puro"), "puro_pos": pos("grid_puro"), "puro_pior": min(j["grid_puro"] for j in js),
        "smart_medio": med("grid_smart"), "smart_pos": pos("grid_smart"), "smart_pior": min(j["grid_smart"] for j in js),
        "buyhold_medio": med("buyhold"),
    }
    json.dump(resultado, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n{'inicio':9} {'ativo':8} {'PURO':>7} {'SMART':>7} {'BUYHOLD':>8}")
    for j in js:
        print(f"{j['inicio']:9} {j['sym']:8} {j['grid_puro']:>6}% {j['grid_smart']:>6}% {j['buyhold']:>7}%")
    r = resultado["resumo"]
    print(f"\nGRID PURO : medio {r['puro_medio']}% | positivas {r['puro_pos']}/{r['n']} | pior {r['puro_pior']}%")
    print(f"GRID SMART: medio {r['smart_medio']}% | positivas {r['smart_pos']}/{r['n']} | pior {r['smart_pior']}%")
    print(f"BUY & HOLD: medio {r['buyhold_medio']}%")


if __name__ == "__main__":
    main()
