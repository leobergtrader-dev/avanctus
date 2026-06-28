"""
caca_loss_real.py — A MESMA estrategia (martingale ate 6 p/ 1 win direto), mas com
candles REAIS (nao com os marcadores inventados do canal). Mostra a verdade.
"""
import os, sys, json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import backtest_historico as B

ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico_1002835208093.json")
PAYOUT = 0.85
MAXN = 6


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


def main():
    msgs = json.load(open(HIST, encoding="utf-8"))
    sinais = parse(msgs)
    serie = []
    for (tk, ts), d in sorted(sinais.items(), key=lambda x: x[0][1]):
        e = B.win(B.buscar_janela(tk, ts).get(ts), d)
        if e is not None:
            serie.append(e == "WIN")
    n = len(serie)
    p = sum(serie) / n
    print(f"Sinais reais: {n} | WIN DIRETO real (entrada): {p*100:.1f}%  (canal alega 72%)")

    # bets que recuperam tudo + 1 unidade
    bets, S = [], 0.0
    for _ in range(MAXN):
        b = (S + 1.0) / PAYOUT; bets.append(b); S += b

    # simula martingale cap 6 na serie REAL
    pnl, step, ciclos, recup, estouros = 0.0, 0, 0, 0, 0
    for x in serie:
        if step == 0:
            ciclos += 1
        if x:
            pnl += bets[step] * PAYOUT; recup += 1; step = 0
        else:
            pnl -= bets[step]; step += 1
            if step >= MAXN:
                estouros += 1; step = 0
    blow_prob = (1 - p) ** MAXN
    print(f"\nP(estourar) = (1-{p:.2f})^6 = {blow_prob*100:.1f}% por ciclo  | se estoura, perde {S:.0f} unidades")
    print(f"Estouros reais na serie: {estouros} | recuperacoes: {recup}")
    print(f"\nPnL REAL simulado: {pnl:+.0f} unidades  ({pnl/n:+.2f}/entrada)")
    print("Compare: nos marcadores do canal dava +144 (falso). Na vida real:", f"{pnl:+.0f}.")


if __name__ == "__main__":
    main()
