"""
lab_oportunidades.py — Garimpo de edges documentados (alem de cripto momentum), com dados reais (Yahoo, mensal).
Testa:
  1) GEM / Dual Momentum (Antonacci): rotaciona acoes-EUA / acoes-internacionais / titulos, com filtro absoluto.
  2) Rotacao de Setores EUA: segura os 3 setores de maior momentum (12m).
  3) Trend-timing S&P500 (Faber): dentro acima da media de 10 meses, fora (caixa) abaixo.
  4) Ouro: buy&hold e com trend-timing.
Compara tudo (Sharpe/CAGR/MaxDD em USD) ao S&P500 buy&hold. Salva tools/oportunidades_resultado.json.
"""
import os, sys, json, datetime, requests

sys.path.insert(0, os.path.dirname(__file__))
import lab_momentum_wf as wf
wf.ANUAL = 12

OUT = os.path.join(os.path.dirname(__file__), "oportunidades_resultado.json")


def ymensal(sym, rng="20y"):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                         params={"interval": "1mo", "range": rng},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        res = r.json()["chart"]["result"][0]
        ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
        out = {}
        for i in range(len(ts)):
            if cl[i]:
                ym = datetime.datetime.fromtimestamp(ts[i], datetime.UTC).strftime("%Y-%m")
                out[ym] = cl[i]
        return out
    except Exception as e:
        print("  erro", sym, e); return {}


def serie_comum(dicts):
    meses = sorted(set.intersection(*[set(d) for d in dicts]))
    return meses


def mom(d, meses, t, k=12):
    return d[meses[t]] / d[meses[t - k]] - 1


def gem(spy, efa, agg, bil):
    meses = serie_comum([spy, efa, agg, bil])
    rets = []
    for t in range(12, len(meses) - 1):
        prox = meses[t + 1]
        m_spy, m_efa, m_bil = mom(spy, meses, t), mom(efa, meses, t), mom(bil, meses, t)
        if m_spy > m_bil:                                   # momentum absoluto positivo
            escolha = spy if m_spy >= m_efa else efa
        else:
            escolha = agg                                   # defensivo: titulos
        rets.append(escolha[prox] / escolha[meses[t]] - 1)
    return rets


def setores(secs, bench, k=12, topn=3):
    meses = serie_comum(list(secs.values()) + [bench])
    rets = []
    for t in range(k, len(meses) - 1):
        prox = meses[t + 1]
        rank = sorted(secs, key=lambda s: mom(secs[s], meses, t, k), reverse=True)
        top = rank[:topn]
        # filtro absoluto: so entra se o momentum medio do topo for positivo, senao caixa
        mm = sum(mom(secs[s], meses, t, k) for s in top) / topn
        if mm <= 0:
            rets.append(0.0)
        else:
            rets.append(sum(secs[s][prox] / secs[s][meses[t]] - 1 for s in top) / topn)
    return rets


def trend_timing(d, k=10):
    meses = sorted(d)
    rets = []
    for t in range(k, len(meses) - 1):
        sma = sum(d[meses[t - i]] for i in range(k)) / k
        prox = meses[t + 1]
        if d[meses[t]] > sma:
            rets.append(d[prox] / d[meses[t]] - 1)
        else:
            rets.append(0.0)                                # caixa
    return rets


def buyhold(d):
    meses = sorted(d)
    return [d[meses[t + 1]] / d[meses[t]] - 1 for t in range(len(meses) - 1)]


def main():
    print("baixando dados...")
    spy = ymensal("SPY"); efa = ymensal("EFA"); agg = ymensal("AGG"); bil = ymensal("BIL")
    gld = ymensal("GLD")
    secs = {s: ymensal(s) for s in ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU"]}
    for nome, d in [("SPY", spy), ("EFA", efa), ("AGG", agg), ("BIL", bil), ("GLD", gld)]:
        print(f"  {nome}: {len(d)} meses")

    res = {
        "GEM_DualMomentum": wf.metricas(gem(spy, efa, agg, bil)),
        "Rotacao_Setores": wf.metricas(setores(secs, spy)),
        "Trend_SP500_10m": wf.metricas(trend_timing(spy)),
        "Ouro_BuyHold": wf.metricas(buyhold(gld)),
        "Ouro_Trend_10m": wf.metricas(trend_timing(gld)),
        "SP500_BuyHold_ref": wf.metricas(buyhold(spy)),
    }
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n{'ESTRATEGIA (USD)':22} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>7}")
    for k, m in res.items():
        if m:
            print(f"{k:22} {m['cagr']:>6}% {m['sharpe']:>7} {m['maxdd']:>6}%")


if __name__ == "__main__":
    main()
