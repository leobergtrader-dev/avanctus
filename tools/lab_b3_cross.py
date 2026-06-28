"""
lab_b3_cross.py — Estrategias de ACOES na B3 (Yahoo diario), long-only, walk-forward vs IBOV:
 A) Momentum CRUZADO (relative strength): ranqueia e compra as K mais fortes (12-1 style)
 B) Reversao de curto prazo: compra as K que mais cairam (bounce)
Custos incluidos. Salva tools/b3_cross_resultado.json.
"""
import os, sys, json, datetime

sys.path.insert(0, os.path.dirname(__file__))
import lab_b3_momentum as b3m
import lab_momentum_wf as wf

OUT = os.path.join(os.path.dirname(__file__), "b3_cross_resultado.json")


def build_aligned(symbols):
    series = {}
    for s in symbols:
        d = b3m.yfetch(s + ".SA")
        if len(d) > 300:
            series[s] = dict(d)
    ibov = dict(b3m.yfetch("%5EBVSP"))
    master = sorted(set().union(*[set(v) for v in series.values()], set(ibov)))
    aligned = {}
    for s, v in series.items():
        arr, last = [], None
        for t in master:
            if t in v:
                last = v[t]
            arr.append(last)
        aligned[s] = arr
    ib, last = [], None
    for t in master:
        if t in ibov:
            last = ibov[t]
        ib.append(last)
    return master, aligned, ib


def ret(arr, i):
    a, p = arr[i], arr[i - 1]
    return (a / p - 1) if (a is not None and p is not None and p > 0) else None


def estrategia(master, aligned, ib, look, skip, K, reb, modo):
    n = len(master)
    start = look + 2
    port, datas, bench = [], [], []
    held = []
    for i in range(start, n):
        if (i - start) % reb == 0:
            sc = {}
            for s, arr in aligned.items():
                a, b = arr[i - skip], arr[i - look]
                if a is not None and b is not None and b > 0:
                    sc[s] = a / b - 1
            ordenado = sorted(sc.items(), key=lambda x: x[1], reverse=(modo == "momentum"))
            novo = [s for s, _ in ordenado[:K]]
            turn = len(set(novo) ^ set(held)) / max(K, 1)
            cost = wf.CUSTO * turn
            held = novo
        else:
            cost = 0.0
        rs = [r for s in held if (r := ret(aligned[s], i)) is not None]
        rb = ret(ib, i)
        if rs and rb is not None:
            port.append(sum(rs) / len(rs) - cost)
            bench.append(rb)
            datas.append(master[i])
    return datas, port, bench


def epocas(datas, port, bench, K=6):
    n = len(port); sz = n // K; out = []
    for i in range(K):
        a, b = i * sz, (i + 1) * sz if i < K - 1 else n
        ini = datetime.datetime.fromtimestamp(datas[a] / 1000, datetime.UTC).strftime("%Y-%m")
        out.append({"periodo": ini, "estrategia": wf.metricas(port[a:b]), "ibov": wf.metricas(bench[a:b])})
    return out


def main():
    master, aligned, ib = build_aligned(b3m.UNIVERSO)
    print(f"acoes alinhadas: {len(aligned)} | dias: {len(master)}\n")
    cfgs = [
        ("Momentum cruzado (6m, top5, mensal)", dict(look=126, skip=21, K=5, reb=21, modo="momentum")),
        ("Reversao curto (5d, piores5, 5d)", dict(look=6, skip=1, K=5, reb=5, modo="reversao")),
    ]
    res = {}
    for nome, cfg in cfgs:
        datas, port, bench = estrategia(master, aligned, ib, **cfg)
        g = wf.metricas(port); gi = wf.metricas(bench)
        eps = epocas(datas, port, bench)
        res[nome] = {"geral": g, "ibov": gi, "epocas": eps}
        print(f"=== {nome} ===")
        print(f"  GERAL: Sharpe {g['sharpe']} CAGR {g['cagr']}% MaxDD {g['maxdd']}%  |  IBOV Sharpe {gi['sharpe']} CAGR {gi['cagr']}%")
        for e in eps:
            es, ii = e["estrategia"], e["ibov"]
            if es and ii:
                print(f"    {e['periodo']}: estrat {es['sharpe']:>5}/{es['cagr']:>6}%   ibov {ii['sharpe']:>5}/{ii['cagr']:>6}%")
        print()
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
