"""
lab_momentum_wf.py — Blindagem do momentum: ensemble + volatility targeting + walk-forward.

Estrategia: para cada moeda, sinal = MEDIA de sinais TSMOM em N=[30,50,80,100] (long-short),
dimensionado por VOLATILITY TARGETING (risco anual alvo ~40%, alavancagem max 3x).
Carteira = media das moedas disponiveis no dia (entra moeda conforme lista).

Valida por EPOCAS (divide o historico em janelas consecutivas) — mostra se o edge sobrevive
em alta E baixa, nao so num periodo. Com custos. Compara a buy & hold.

Salva tools/momentum_wf_resultado.json. Roda: py tools/lab_momentum_wf.py
"""
import os, sys, json, math, requests

OUT = os.path.join(os.path.dirname(__file__), "momentum_wf_resultado.json")
UNIVERSO = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "XRPUSDT",
            "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "DOTUSDT", "MATICUSDT"]
NS = [30, 50, 80, 100]
ALVO_VOL = 0.40
JANELA_VOL = 30
LEV_MAX = 3.0
CUSTO = 0.001
ANUAL = 365


def fetch_daily(symbol, paginas=4):
    """Pega ate ~paginas*1000 dias, paginando para tras."""
    todos = {}
    end = None
    for _ in range(paginas):
        params = {"symbol": symbol, "interval": "1d", "limit": 1000}
        if end:
            params["endTime"] = end
        try:
            arr = requests.get("https://api.binance.com/api/v3/klines", params=params, timeout=20).json()
        except Exception:
            break
        if not isinstance(arr, list) or not arr:
            break
        for k in arr:
            todos[k[0]] = float(k[4])
        end = arr[0][0] - 1
        if len(arr) < 1000:
            break
    return sorted(todos.items())


def std(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / n)


def strat_coin(serie):
    """Retorna dict date->(strat_ret, bh_ret) para uma moeda."""
    dates = [d for d, _ in serie]
    px = [p for _, p in serie]
    rets = [0.0] + [px[i] / px[i - 1] - 1 for i in range(1, len(px))]
    out = {}
    pos_ant = 0.0
    for t in range(max(NS) + 1, len(px)):
        sig = sum(1 if px[t] > px[t - N] else -1 for N in NS) / len(NS)   # [-1,1]
        vol = std(rets[t - JANELA_VOL:t]) * math.sqrt(ANUAL)
        scale = min(ALVO_VOL / vol, LEV_MAX) if vol > 0 else 0
        pos = sig * scale
        r = pos_ant * rets[t] - CUSTO * abs(pos_ant - pos)   # posicao de ontem aplicada hoje
        out[dates[t]] = (r, rets[t])
        pos_ant = pos
    return out


def metricas(rets):
    if len(rets) < 5:
        return None
    eq = peak = 1.0
    maxdd = 0.0
    for r in rets:
        eq *= (1 + r); peak = max(peak, eq); maxdd = max(maxdd, (peak - eq) / peak)
    dias = len(rets)
    mu = sum(rets) / dias
    sd = std(rets)
    return {"cagr": round((eq ** (ANUAL / dias) - 1) * 100, 1),
            "sharpe": round(mu / sd * math.sqrt(ANUAL), 2) if sd > 0 else 0,
            "maxdd": round(maxdd * 100, 1)}


def main():
    porcoin = {}
    for s in UNIVERSO:
        serie = fetch_daily(s)
        if len(serie) > max(NS) + 60:
            porcoin[s] = strat_coin(serie)
        print(f"  {s}: {len(serie)} dias")

    # carteira: media das moedas disponiveis por data
    alldates = sorted(set(d for c in porcoin.values() for d in c))
    port_s, port_bh, datas = [], [], []
    for d in alldates:
        ss = [porcoin[c][d][0] for c in porcoin if d in porcoin[c]]
        bb = [porcoin[c][d][1] for c in porcoin if d in porcoin[c]]
        if ss:
            port_s.append(sum(ss) / len(ss)); port_bh.append(sum(bb) / len(bb)); datas.append(d)
    n = len(port_s)
    print(f"\nDias de carteira: {n} | moedas: {len(porcoin)}\n")

    # walk-forward por epocas (6 janelas consecutivas)
    K = 6
    sz = n // K
    epocas = []
    for i in range(K):
        a, b = i * sz, (i + 1) * sz if i < K - 1 else n
        import datetime
        ini = datetime.datetime.utcfromtimestamp(datas[a] / 1000).strftime("%Y-%m")
        fim = datetime.datetime.utcfromtimestamp(datas[b - 1] / 1000).strftime("%Y-%m")
        epocas.append({"periodo": f"{ini}..{fim}", "estrategia": metricas(port_s[a:b]),
                       "buyhold": metricas(port_bh[a:b])})

    resultado = {"n_dias": n, "moedas": list(porcoin),
                 "geral_estrategia": metricas(port_s), "geral_buyhold": metricas(port_bh),
                 "epocas": epocas}
    json.dump(resultado, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=== WALK-FORWARD POR EPOCA (estrategia vs buy&hold) ===")
    print(f"{'periodo':16} {'ESTRAT sharpe/cagr':>22} {'BH sharpe/cagr':>20}")
    for e in epocas:
        es, bh = e["estrategia"], e["buyhold"]
        if es and bh:
            print(f"{e['periodo']:16} {es['sharpe']:>8} / {es['cagr']:>7}%   {bh['sharpe']:>8} / {bh['cagr']:>7}%")
    g, gb = resultado["geral_estrategia"], resultado["geral_buyhold"]
    print(f"\nGERAL  Estrategia: Sharpe {g['sharpe']} CAGR {g['cagr']}% MaxDD {g['maxdd']}%")
    print(f"       Buy & Hold: Sharpe {gb['sharpe']} CAGR {gb['cagr']}% MaxDD {gb['maxdd']}%")


if __name__ == "__main__":
    main()
