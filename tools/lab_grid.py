"""
lab_grid.py — Backtest honesto de GRID TRADING (estilo WunderTrading) com dados reais.

Grid: faixa [low,high] dividida em N degraus; compra ao cair um degrau, vende ao subir um.
Lucra na oscilacao (mercado lateral). Risco: se o preco SAI da faixa por baixo (crash),
fica "saco" de posicoes perdedoras. Testamos em VARIAS janelas (lateral/alta/crash), com taxas,
e comparamos a buy & hold.

Salva tools/grid_resultado.json. Roda: py tools/lab_grid.py
"""
import os, json, datetime, requests

OUT = os.path.join(os.path.dirname(__file__), "grid_resultado.json")
BINANCE = os.environ.get("BINANCE_BASE", "https://data-api.binance.vision")
FEE = 0.001         # 0.1% por trade
N = 20              # degraus
FAIXA = 0.25        # +/-25% em torno do preco inicial da janela
JANELA_DIAS = 90
CAPITAL = 1000.0


def fetch_hourly(symbol, n_candles=26000):
    out = {}
    end = None
    while len(out) < n_candles:
        p = {"symbol": symbol, "interval": "1h", "limit": 1000}
        if end:
            p["endTime"] = end
        try:
            arr = requests.get(f"{BINANCE}/api/v3/klines", params=p, timeout=20).json()
        except Exception:
            break
        if not isinstance(arr, list) or not arr:
            break
        for k in arr:
            out[k[0]] = float(k[4])
        end = arr[0][0] - 1
        if len(arr) < 1000:
            break
    return sorted(out.items())


def grid_backtest(precos, low, high, n, capital, fee):
    levels = [low + i * (high - low) / n for i in range(n + 1)]
    qty = [(capital / n) / levels[i] for i in range(n)]
    holding = [0.0] * n
    cash = capital
    p0 = precos[0]
    for p1 in precos[1:]:
        if p1 < p0:                       # caiu: compra nos niveis cruzados
            for i in range(n):
                if p1 <= levels[i] < p0 and holding[i] == 0:
                    cash -= qty[i] * levels[i] * (1 + fee); holding[i] = qty[i]
        elif p1 > p0:                     # subiu: vende a celula de baixo no topo
            for i in range(n):
                if p0 < levels[i + 1] <= p1 and holding[i] > 0:
                    cash += holding[i] * levels[i + 1] * (1 - fee); holding[i] = 0.0
        p0 = p1
    final = precos[-1]
    valor = cash + sum(holding[i] * final for i in range(n))
    return {"net": round((valor / capital - 1) * 100, 1),
            "bagged": round(100 * sum(1 for h in holding if h > 0) / n, 0)}


def main():
    simbolos = ["BTCUSDT", "ETHUSDT"]
    resultado = {"config": {"N": N, "faixa": FAIXA, "fee": FEE, "janela_dias": JANELA_DIAS}, "janelas": []}
    for sym in simbolos:
        serie = fetch_hourly(sym)
        print(f"{sym}: {len(serie)} horas")
        passo = JANELA_DIAS * 24
        i = 0
        while i + passo <= len(serie):
            bloco = serie[i:i + passo]
            precos = [p for _, p in bloco]
            p_ini = precos[0]
            low, high = p_ini * (1 - FAIXA), p_ini * (1 + FAIXA)
            g = grid_backtest(precos, low, high, N, CAPITAL, FEE)
            bh = round((precos[-1] / precos[0] - 1) * 100, 1)
            ini = datetime.datetime.fromtimestamp(bloco[0][0] / 1000, datetime.UTC).strftime("%Y-%m")
            saiu = "abaixo (crash)" if precos[-1] < low else ("acima (rally)" if precos[-1] > high else "dentro")
            resultado["janelas"].append({"sym": sym, "inicio": ini, "grid_net": g["net"],
                                         "buyhold": bh, "saco_perc": g["bagged"], "preco_final": saiu})
            i += passo
    # resumo
    gs = [j["grid_net"] for j in resultado["janelas"]]
    resultado["resumo"] = {
        "n_janelas": len(gs),
        "grid_medio": round(sum(gs) / len(gs), 1),
        "grid_positivas": sum(1 for x in gs if x > 0),
        "pior_grid": min(gs),
        "buyhold_medio": round(sum(j["buyhold"] for j in resultado["janelas"]) / len(gs), 1),
    }
    json.dump(resultado, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n{'inicio':9} {'ativo':8} {'GRID':>7} {'BUYHOLD':>8} {'saco':>6} {'final'}")
    for j in resultado["janelas"]:
        print(f"{j['inicio']:9} {j['sym']:8} {j['grid_net']:>6}% {j['buyhold']:>7}% {j['saco_perc']:>5}% {j['preco_final']}")
    r = resultado["resumo"]
    print(f"\nGRID medio: {r['grid_medio']}% | positivas {r['grid_positivas']}/{r['n_janelas']} | PIOR {r['pior_grid']}% | BuyHold medio {r['buyhold_medio']}%")


if __name__ == "__main__":
    main()
