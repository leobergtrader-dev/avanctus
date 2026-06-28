"""
analise_traderneto_fade.py — Fade (sinal ao contrario) do Trader Neto, ANALISADO POR PERIODO.
Mostra se "fadear" e tendencia estavel (>54% mes a mes) ou blip de sorte. Candles reais (Binance).
Salva .tmp/serie_tn_ts.json (ts, win) p/ reuso.
"""
import os, sys, json, math
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import analise_avalon as av

ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico_1001738261211.json")
SER = os.path.join(ROOT, ".tmp", "serie_tn_ts.json")


def wilson(w, n, z=1.96):
    if n == 0:
        return (None, None)
    p = w / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round((c - h) * 100, 1), round((c + h) * 100, 1))


def build():
    if os.path.exists(SER):
        return json.load(open(SER, encoding="utf-8"))
    msgs = json.load(open(HIST, encoding="utf-8"))
    sinais = av.parse_sinais(msgs)
    porsym = {}
    for (sym, ts) in sinais:
        porsym.setdefault(sym, []).append(ts)
    candles = {s: av.klines(s, min(t) - 5 * 60000, max(t) + 5 * 60000) for s, t in porsym.items()}
    out = []
    for (sym, ts), d in sorted(sinais.items(), key=lambda x: x[0][1]):
        w = av.win_dir(candles.get(sym, {}).get(ts), d)
        if w is not None:
            out.append([ts, 1 if w else 0])
    json.dump(out, open(SER, "w"))
    return out


def main():
    serie = build()
    n = len(serie)
    # fade = 1 - win
    fades = [(ts, 1 - w) for ts, w in serie]
    geral = sum(f for _, f in fades)
    print(f"Trader Neto: {n} operacoes | fade GERAL {100*geral/n:.1f}%  IC95 {wilson(geral,n)}\n")

    # por mes
    pormes = defaultdict(list)
    for ts, f in fades:
        mes = datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m")
        pormes[mes].append(f)
    print("=== FADE por mes ===")
    print(f"{'mes':9} {'fade':>7} {'n':>5} {'IC95':>16}")
    for mes in sorted(pormes):
        v = pormes[mes]; nn = len(v); w = sum(v)
        ic = wilson(w, nn)
        flag = " <<" if (nn >= 15 and 100 * w / nn > 54) else ""
        print(f"{mes:9} {100*w/nn:>6.1f}% {nn:>5} {str(ic):>16}{flag}")

    # janelas recentes acumuladas
    print("\n=== FADE acumulado (ultimos N sinais) ===")
    for k in (30, 60, 90, 150):
        if k <= n:
            sub = [f for _, f in fades[-k:]]; w = sum(sub)
            print(f"  ultimos {k:>3}: {100*w/k:.1f}%  IC95 {wilson(w,k)}")
    print("\nLeitura: se o fade for >54% de forma ESTAVEL nos meses recentes (e o IC inferior > ~52%),")
    print("vira candidato real. Se pula de 40% a 65% sem padrao, e ruido.")


if __name__ == "__main__":
    main()
