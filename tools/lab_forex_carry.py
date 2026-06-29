"""
lab_forex_carry.py — Backtest do CARRY TRADE (o edge classico de forex).
Ideia: comprar moedas de JURO ALTO e vender as de JURO BAIXO. O lucro vem da
diferenca de juros (carry) + variacao do cambio.

Juros: tabela de taxas oficiais dos bancos centrais (aprox., anual — mudam devagar).
Cambio: mensal do Yahoo (dado real). Estrategia: a cada mes ranqueia 8 moedas pelo juro,
LONG top-3 / SHORT bottom-3 (dolar-neutra). Sharpe/CAGR/MaxDD + walk-forward.
Compara ao 'long-all'. Salva tools/forex_carry_resultado.json.
"""
import os, sys, json, datetime, requests

sys.path.insert(0, os.path.dirname(__file__))
import lab_momentum_wf as wf
wf.ANUAL = 12  # dados mensais

OUT = os.path.join(os.path.dirname(__file__), "forex_carry_resultado.json")
TOPK = 3

# Simbolo Yahoo p/ valor da moeda em USD, e se precisa inverter (par cotado como USDxxx)
SPOT = {
    "EUR": ("EURUSD=X", False), "JPY": ("USDJPY=X", True), "GBP": ("GBPUSD=X", False),
    "AUD": ("AUDUSD=X", False), "CAD": ("USDCAD=X", True), "CHF": ("USDCHF=X", True),
    "NZD": ("NZDUSD=X", False),
}

# Taxa de juros basica aproximada por ano (% a.a.) — bancos centrais.
RATES = {
    "USD": {2010: .25, 2011: .25, 2012: .25, 2013: .25, 2014: .25, 2015: .25, 2016: .50, 2017: 1.25,
            2018: 2.25, 2019: 1.75, 2020: .25, 2021: .25, 2022: 4.25, 2023: 5.25, 2024: 4.75, 2025: 4.0, 2026: 3.75},
    "EUR": {2010: 1.0, 2011: 1.0, 2012: .75, 2013: .25, 2014: .05, 2015: .05, 2016: 0.0, 2017: 0.0,
            2018: 0.0, 2019: 0.0, 2020: 0.0, 2021: 0.0, 2022: 2.0, 2023: 4.0, 2024: 3.0, 2025: 2.5, 2026: 2.0},
    "JPY": {2010: .10, 2011: .10, 2012: .10, 2013: .10, 2014: .10, 2015: .10, 2016: -.10, 2017: -.10,
            2018: -.10, 2019: -.10, 2020: -.10, 2021: -.10, 2022: -.10, 2023: -.10, 2024: .10, 2025: .25, 2026: .50},
    "GBP": {2010: .50, 2011: .50, 2012: .50, 2013: .50, 2014: .50, 2015: .50, 2016: .25, 2017: .50,
            2018: .75, 2019: .75, 2020: .10, 2021: .25, 2022: 3.50, 2023: 5.25, 2024: 4.75, 2025: 4.0, 2026: 3.75},
    "AUD": {2010: 4.75, 2011: 4.25, 2012: 3.0, 2013: 2.50, 2014: 2.50, 2015: 2.0, 2016: 1.50, 2017: 1.50,
            2018: 1.50, 2019: .75, 2020: .10, 2021: .10, 2022: 3.10, 2023: 4.35, 2024: 4.35, 2025: 3.85, 2026: 3.50},
    "CAD": {2010: 1.0, 2011: 1.0, 2012: 1.0, 2013: 1.0, 2014: 1.0, 2015: .50, 2016: .50, 2017: 1.0,
            2018: 1.75, 2019: 1.75, 2020: .25, 2021: .25, 2022: 4.25, 2023: 5.0, 2024: 3.75, 2025: 3.0, 2026: 2.75},
    "CHF": {2010: 0.0, 2011: 0.0, 2012: 0.0, 2013: 0.0, 2014: 0.0, 2015: -.75, 2016: -.75, 2017: -.75,
            2018: -.75, 2019: -.75, 2020: -.75, 2021: -.75, 2022: 1.0, 2023: 1.75, 2024: 1.0, 2025: .50, 2026: .25},
    "NZD": {2010: 3.0, 2011: 2.50, 2012: 2.50, 2013: 2.50, 2014: 3.50, 2015: 2.50, 2016: 1.75, 2017: 1.75,
            2018: 1.75, 2019: 1.0, 2020: .25, 2021: .75, 2022: 4.25, 2023: 5.50, 2024: 4.25, 2025: 3.25, 2026: 3.0},
}


def juro(m, ym):
    y = int(ym[:4])
    tbl = RATES[m]
    return tbl.get(y, tbl[min(tbl, key=lambda k: abs(k - y))])


def yahoo_mensal(sym, invert):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                         params={"interval": "1mo", "range": "15y"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        res = r.json()["chart"]["result"][0]
        ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
        out = {}
        for i in range(len(ts)):
            if cl[i]:
                ym = datetime.datetime.fromtimestamp(ts[i], datetime.UTC).strftime("%Y-%m")
                out[ym] = (1.0 / cl[i]) if invert else cl[i]
        return out
    except Exception as e:
        print("  erro Yahoo", sym, e)
        return {}


def main():
    spot = {}
    for m, (ys, inv) in SPOT.items():
        spot[m] = yahoo_mensal(ys, inv)
        print(f"  {m}: cambio {len(spot[m])} meses")
    moedas = ["USD"] + list(SPOT)

    meses = sorted(set.intersection(*[set(spot[m]) for m in SPOT]))
    meses = [mm for mm in meses if mm >= "2011-01"]
    rets_carry, rets_longall, capt, datas = [], [], [], []

    for i in range(1, len(meses)):
        ym, prev = meses[i], meses[i - 1]
        rus = juro("USD", prev)
        exc, sig = {}, {}
        for m in moedas:
            if m == "USD":
                exc[m] = 0.0
            else:
                spot_ret = spot[m][ym] / spot[m][prev] - 1
                exc[m] = spot_ret + (juro(m, prev) - rus) / 1200.0
            sig[m] = juro(m, prev)
        ordenado = sorted(moedas, key=lambda m: sig[m])
        baixo, alto = ordenado[:TOPK], ordenado[-TOPK:]
        rets_carry.append(sum(exc[m] for m in alto) / TOPK - sum(exc[m] for m in baixo) / TOPK)
        rets_longall.append(sum(exc[m] for m in SPOT) / len(SPOT))
        capt.append((sum(sig[m] for m in alto) - sum(sig[m] for m in baixo)) / TOPK)
        datas.append(ym)

    n = len(rets_carry)
    K = 5; sz = max(1, n // K); epocas = []
    for i in range(K):
        a, b = i * sz, (i + 1) * sz if i < K - 1 else n
        if a < n:
            epocas.append({"periodo": datas[a], "carry": wf.metricas(rets_carry[a:b])})

    res = {"n_meses": n, "inicio": datas[0], "fim": datas[-1],
           "carry_longshort": wf.metricas(rets_carry),
           "long_all": wf.metricas(rets_longall),
           "diferencial_juro_medio_aa": round(sum(capt) / n, 2),
           "epocas": epocas}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\nMeses: {n} ({res['inicio']} a {res['fim']})\n")
    print("=== WALK-FORWARD (Carry long/short) ===")
    for e in epocas:
        c = e["carry"]
        if c:
            print(f"{e['periodo']:9} Sharpe {c['sharpe']:>6} / CAGR {c['cagr']:>6}% / MaxDD {c['maxdd']:>6}%")
    c, la = res["carry_longshort"], res["long_all"]
    print(f"\nGERAL Carry L/S : Sharpe {c['sharpe']} CAGR {c['cagr']}% MaxDD {c['maxdd']}%")
    print(f"GERAL Long-all  : Sharpe {la['sharpe']} CAGR {la['cagr']}% MaxDD {la['maxdd']}%")
    print(f"Diferencial de juro capturado (medio): {res['diferencial_juro_medio_aa']}% a.a.")


if __name__ == "__main__":
    main()
