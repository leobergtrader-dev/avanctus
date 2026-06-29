"""
lab_forex_grid.py — Testa GRID TRADING no forex (a hipotese: moeda 'fica variando', bom pra grid).
Dados de hora em hora do Yahoo (~2 anos). Faixa ajustada pra baixa vol do forex.
Reusa a logica de grid ja validada (lab_grid / lab_grid_smart). Compara grid puro vs
grid inteligente (filtro de regime) vs buy&hold, em varias janelas e pares.
Salva tools/forex_grid_resultado.json.
"""
import os, sys, json, datetime, requests

sys.path.insert(0, os.path.dirname(__file__))
import lab_grid as lg
import lab_grid_smart as lgs

OUT = os.path.join(os.path.dirname(__file__), "forex_grid_resultado.json")
PARES = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDBRL=X"]
FAIXA = 0.06        # +/-6% em torno do preco inicial (forex anda pouco)
N = 20              # degraus
FEE = 0.0001        # ~1 bps por ordem (spread de major; forex e barato)
WIN_BARS = 800      # tamanho da janela (em barras horarias)
TREND_H = 240       # SMA de regime


def yfetch_hourly(sym, rng="730d"):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                         params={"interval": "60m", "range": rng},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        res = r.json()["chart"]["result"][0]
        ts = res["timestamp"]
        cl = res["indicators"]["quote"][0]["close"]
        return [cl[i] for i in range(len(ts)) if cl[i] is not None]
    except Exception as e:
        print("  erro", sym, e)
        return []


def main():
    resultado = {"config": {"N": N, "faixa": FAIXA, "fee": FEE, "win_bars": WIN_BARS}, "janelas": []}
    for sym in PARES:
        serie = yfetch_hourly(sym)
        print(f"  {sym}: {len(serie)} barras horarias")
        if len(serie) < WIN_BARS + TREND_H:
            continue
        smas_full = lgs.sma_series(serie, TREND_H)
        i = 0
        while i + WIN_BARS <= len(serie):
            precos = serie[i:i + WIN_BARS]
            smas = smas_full[i:i + WIN_BARS]
            p0 = precos[0]
            low, high = p0 * (1 - FAIXA), p0 * (1 + FAIXA)
            puro = lg.grid_backtest(precos, low, high, N, 1000.0, FEE)["net"]
            smart = lgs.grid_smart(precos, smas, low, high, N, 1000.0, FEE)
            bh = round((precos[-1] / precos[0] - 1) * 100, 1)
            resultado["janelas"].append({"par": sym.replace("=X", ""), "grid_puro": puro,
                                         "grid_smart": smart, "buyhold": bh})
            i += WIN_BARS

    js = resultado["janelas"]
    if not js:
        print("sem dados suficientes."); return

    def med(k): return round(sum(j[k] for j in js) / len(js), 2)
    def pos(k): return sum(1 for j in js if j[k] > 0)
    resultado["resumo"] = {
        "n": len(js),
        "puro_medio": med("grid_puro"), "puro_pos": pos("grid_puro"), "puro_pior": min(j["grid_puro"] for j in js),
        "smart_medio": med("grid_smart"), "smart_pos": pos("grid_smart"), "smart_pior": min(j["grid_smart"] for j in js),
        "buyhold_medio": med("buyhold"),
    }
    json.dump(resultado, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n{'par':9} {'PURO':>8} {'SMART':>8} {'BUYHOLD':>9}")
    for j in js:
        print(f"{j['par']:9} {j['grid_puro']:>7}% {j['grid_smart']:>7}% {j['buyhold']:>8}%")
    r = resultado["resumo"]
    print(f"\nGRID PURO : medio {r['puro_medio']}% | positivas {r['puro_pos']}/{r['n']} | pior {r['puro_pior']}%")
    print(f"GRID SMART: medio {r['smart_medio']}% | positivas {r['smart_pos']}/{r['n']} | pior {r['smart_pior']}%")
    print(f"BUY & HOLD: medio {r['buyhold_medio']}%")


if __name__ == "__main__":
    main()
