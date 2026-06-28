"""
analise_traderneto_full.py — Bateria completa no canal Trader Neto (Avalon, cripto real/Binance):
 1) taxa real de WIN por entrada + "1 win a cada N operacoes"
 2) caca ao loss: P(WIN | >=N losses antes) para N=3..7 (com IC)
 3) martingale com varios limites de banca (4,6,8,10,12)
Tudo com candles REAIS (Binance). Salva .tmp/serie_traderneto.json p/ reuso.
"""
import os, sys, json, math

sys.path.insert(0, os.path.dirname(__file__))
import analise_avalon as av   # reusa klines, parse, win_dir

ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico_1001738261211.json")
SER = os.path.join(ROOT, ".tmp", "serie_traderneto.json")
PAYOUT = 0.85
BASE = 25.0


def wilson(w, n, z=1.96):
    if n == 0:
        return (None, None)
    p = w / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round((c - h) * 100, 1), round((c + h) * 100, 1))


def build_serie():
    if os.path.exists(SER):
        return json.load(open(SER, encoding="utf-8"))
    msgs = json.load(open(HIST, encoding="utf-8"))
    sinais = av.parse_sinais(msgs)
    porsym = {}
    for (sym, ts) in sinais:
        porsym.setdefault(sym, []).append(ts)
    candles = {}
    for sym, tss in porsym.items():
        candles[sym] = av.klines(sym, min(tss) - 5 * 60000, max(tss) + 5 * 60000)
    serie = []
    for (sym, ts), d in sorted(sinais.items(), key=lambda x: x[0][1]):
        c = candles.get(sym, {}).get(ts)
        w = av.win_dir(c, d)
        if w is not None:
            serie.append(1 if w else 0)
    json.dump(serie, open(SER, "w"))
    return serie


def bets(cap):
    out, S = [], 0.0
    for _ in range(cap):
        b = (S + 1.0) / PAYOUT; out.append(b); S += b
    return out, S


def simula(serie, cap):
    B, S = bets(cap); pnl = 0.0; step = 0; est = 0
    for x in serie:
        if x:
            pnl += B[step] * PAYOUT; step = 0
        else:
            pnl -= B[step]; step += 1
            if step >= cap:
                est += 1; step = 0
    return round(S * BASE), est, round(pnl * BASE)


def main():
    serie = build_serie()
    n = len(serie); wins = sum(serie); p = wins / n
    print(f"TRADER NETO (Avalon, cripto real) — {n} operacoes | WIN entrada: {wins} ({p*100:.1f}%)\n")
    print(f">>> 1 WIN a cada {1/p:.2f} operacoes <<<")
    ev = p * PAYOUT - (1 - p)
    print(f"Expectancia FLAT: {ev*100:+.1f}%/op | break-even {100/(1+PAYOUT):.1f}% | temos {p*100:.1f}%\n")

    print("=== CACA AO LOSS: P(WIN apos >=N losses) ===")
    for N in range(3, 8):
        w = t = 0; c = 0
        for x in serie:
            if c >= N:
                t += 1; w += x
            c = 0 if x else c + 1
        ic = wilson(w, t)
        pw = f"{round(100*w/t,1)}%" if t else "sem dados"
        ictxt = f"[{ic[0]}-{ic[1]}]" if ic[0] is not None else "-"
        print(f"  apos {N} losses: {pw:>10}  (n={t:<4} IC95 {ictxt})")

    print("\n=== MARTINGALE com limites de banca (base $25) ===")
    print(f"{'limite':>8} {'banca':>12} {'estouros':>9} {'PnL($)':>10}")
    for cap in (1, 4, 6, 8, 10, 12):
        banca, est, pnl = simula(serie, cap)
        nome = "flat" if cap == 1 else f"{cap} ent."
        print(f"{nome:>8} {('$'+format(banca,',')):>12} {est:>9} {('$'+format(pnl,',')):>10}")


if __name__ == "__main__":
    main()
