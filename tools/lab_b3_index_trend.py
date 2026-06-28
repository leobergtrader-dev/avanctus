"""
lab_b3_index_trend.py — Filtro de tendencia no proprio IBOVESPA (long/caixa).
Segura o indice quando esta acima da media longa; vai pra caixa quando cai abaixo.
Ensemble de medias [50,100,150,200] -> exposicao 0..1. Custos. Walk-forward vs buy & hold.
Salva tools/b3_index_trend_resultado.json.
"""
import os, sys, json, time, datetime, requests

sys.path.insert(0, os.path.dirname(__file__))
import lab_momentum_wf as wf

OUT = os.path.join(os.path.dirname(__file__), "b3_index_trend_resultado.json")
SMAS = [50, 100, 150, 200]


def fetch_ibov_diario(anos=18):
    now = int(time.time())
    p1 = now - anos * 365 * 86400
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP",
                     params={"interval": "1d", "period1": p1, "period2": now},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    res = r.json()["chart"]["result"][0]
    ts = res["timestamp"]; cl = res["indicators"]["quote"][0]["close"]
    return [(ts[i] * 1000, cl[i]) for i in range(len(ts)) if cl[i] is not None]


def sma_at(px, win):
    pref = [0.0]
    for p in px:
        pref.append(pref[-1] + p)
    return [(pref[t + 1] - pref[max(0, t - win + 1)]) / (t + 1 - max(0, t - win + 1)) for t in range(len(px))]


def main():
    serie = fetch_ibov_diario(18)
    serie = [(t, p) for t, p in serie if p]
    dates = [t for t, _ in serie]
    px = [p for _, p in serie]
    n = len(px)
    print(f"Ibovespa: {n} dias ({datetime.datetime.fromtimestamp(dates[0]/1000,datetime.UTC):%Y-%m} a {datetime.datetime.fromtimestamp(dates[-1]/1000,datetime.UTC):%Y-%m})\n")
    rets = [0.0] + [px[i] / px[i - 1] - 1 for i in range(1, n)]
    smas = {w: sma_at(px, w) for w in SMAS}

    def run(modo):
        pos = [0.0] * n
        for t in range(max(SMAS), n):
            if modo == "sma200":
                pos[t] = 1.0 if px[t] > smas[200][t] else 0.0
            else:  # ensemble
                pos[t] = sum(1 for w in SMAS if px[t] > smas[w][t]) / len(SMAS)
        out, datas = [], []
        for t in range(max(SMAS) + 1, n):
            r = pos[t - 1] * rets[t] - wf.CUSTO * abs(pos[t - 1] - pos[t - 2])
            out.append(r); datas.append(dates[t])
        return datas, out

    # buy & hold no mesmo intervalo
    bh = rets[max(SMAS) + 1:]
    datas, ens = run("ensemble")
    _, s200 = run("sma200")

    def epocas(port, K=6):
        sz = len(port) // K; e = []
        for i in range(K):
            a, b = i * sz, (i + 1) * sz if i < K - 1 else len(port)
            ini = datetime.datetime.fromtimestamp(datas[a] / 1000, datetime.UTC).strftime("%Y-%m")
            e.append((ini, wf.metricas(port[a:b]), wf.metricas(bh[a:b])))
        return e

    res = {"n": n,
           "buyhold": wf.metricas(bh),
           "filtro_ensemble": wf.metricas(ens),
           "filtro_sma200": wf.metricas(s200)}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=== GERAL (todo o historico) ===")
    for k in ("buyhold", "filtro_sma200", "filtro_ensemble"):
        m = res[k]
        print(f"  {k:16} Sharpe {m['sharpe']:>5}  CAGR {m['cagr']:>6}%  MaxDD {m['maxdd']:>6}%")
    print("\n=== Walk-forward (filtro ensemble vs buy&hold) ===")
    for ini, es, b in epocas(ens):
        if es and b:
            print(f"  {ini}: filtro {es['sharpe']:>5}/{es['cagr']:>6}% (DD {es['maxdd']:>5}%)   bh {b['sharpe']:>5}/{b['cagr']:>6}% (DD {b['maxdd']:>5}%)")


if __name__ == "__main__":
    main()
