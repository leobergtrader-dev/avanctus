"""
caca_loss_freq.py — Frequencia de WIN DIRETO (sem martingale), em candles REAIS.
Responde: apos um loss, a cada quantas operacoes em media sai 1 win? E a distribuicao.
Salva a serie real em .tmp/serie_real.json p/ reuso.
"""
import os, sys, json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import backtest_historico as B

ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico_1002835208093.json")
SER = os.path.join(ROOT, ".tmp", "serie_real.json")
PAYOUT = 0.85


def parse(msgs):
    s = {}
    for m in msgs:
        try:
            br = datetime.fromisoformat(m.get("date")).astimezone(B.BR)
        except Exception:
            continue
        for asset, hhmm, direc, _ in B.LINE.findall(m.get("text") or ""):
            tk = B.NAME2TICK.get(asset.strip().upper())
            if not tk:
                continue
            h, mi = map(int, hhmm.split(":"))
            e = datetime(br.year, br.month, br.day, h, mi, tzinfo=B.BR)
            if e > br + timedelta(minutes=15):
                e -= timedelta(days=1)
            s[(tk, int(e.astimezone(timezone.utc).timestamp() * 1000))] = "BUY" if direc.upper() == "CALL" else "SELL"
    return s


def build_serie():
    if os.path.exists(SER):
        return json.load(open(SER, encoding="utf-8"))
    msgs = json.load(open(HIST, encoding="utf-8"))
    sinais = parse(msgs)
    serie = []
    for (tk, ts), d in sorted(sinais.items(), key=lambda x: x[0][1]):
        e = B.win(B.buscar_janela(tk, ts).get(ts), d)
        if e is not None:
            serie.append(1 if e == "WIN" else 0)
    json.dump(serie, open(SER, "w"))
    return serie


def main():
    serie = build_serie()
    n = len(serie)
    wins = sum(serie)
    p = wins / n
    print(f"Operacoes reais: {n} | WIN DIRETO: {wins} ({p*100:.1f}%)\n")
    print(f">>> 1 WIN a cada {1/p:.2f} operacoes, em media (1/taxa) <<<\n")

    # gaps: apos um LOSS, quantas entradas ate o proximo WIN
    gaps = []
    i = 0
    while i < n:
        if serie[i] == 0:  # loss
            k = 1
            while i + k < n and serie[i + k] == 0:
                k += 1
            if i + k < n:        # achou um win
                gaps.append(k)
            i += k
        else:
            i += 1
    media_gap = sum(gaps) / len(gaps) if gaps else 0
    print(f"Apos um LOSS, ops ate o proximo WIN: media {media_gap:.2f}")
    # distribuicao
    from collections import Counter
    dist = Counter(min(g, 6) for g in gaps)
    print("Distribuicao (apos loss, em quantas ops veio o win):")
    for k in range(1, 7):
        lbl = f"{k}" if k < 6 else "6+"
        c = dist.get(k, 0)
        print(f"  em {lbl} op(s): {c:>3}  ({round(100*c/len(gaps),1) if gaps else 0}%)")

    # expectancia FLAT (sem martingale)
    ev = p * PAYOUT - (1 - p)
    print(f"\nExpectancia FLAT por operacao: {ev*100:+.1f}%  (win paga {PAYOUT}, loss custa 1)")
    print(f"Break-even precisa de {100/(1+PAYOUT):.1f}% de acerto. Temos {p*100:.1f}%.")


if __name__ == "__main__":
    main()
