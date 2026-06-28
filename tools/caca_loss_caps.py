"""
caca_loss_caps.py — Mostra que AUMENTAR a banca (mais entradas no martingale) NAO resolve.
Usa a serie REAL salva (.tmp/serie_real.json). Simula martingale de recuperacao com varios
limites de entradas e mostra: banca necessaria, estouros e PnL. Spoiler: piora.
"""
import os, sys, json

ROOT = os.path.dirname(os.path.dirname(__file__))
SER = os.path.join(ROOT, ".tmp", "serie_real.json")
PAYOUT = 0.85
BASE = 25.0   # entrada-base em $


def bets(cap):
    out, S = [], 0.0
    for _ in range(cap):
        b = (S + 1.0) / PAYOUT     # recupera tudo + 1 unidade
        out.append(b); S += b
    return out, S


def simula(serie, cap):
    B, S = bets(cap)
    pnl = 0.0; step = 0; estouros = 0
    for x in serie:
        if x:
            pnl += B[step] * PAYOUT; step = 0
        else:
            pnl -= B[step]; step += 1
            if step >= cap:
                estouros += 1; step = 0
    return {"banca_necessaria_$": round(S * BASE, 0), "estouros": estouros,
            "pnl_unidades": round(pnl, 1), "pnl_$": round(pnl * BASE, 0)}


def main():
    serie = json.load(open(SER, encoding="utf-8"))
    n = len(serie); p = sum(serie) / n
    print(f"Serie real: {n} operacoes | acerto {p*100:.1f}% | base ${BASE:.0f}\n")
    print(f"{'limite':>7} {'banca p/ aguentar':>18} {'estouros':>9} {'PnL($)':>9}")
    for cap in (1, 4, 6, 8, 10, 12):
        r = simula(serie, cap)
        nome = "flat" if cap == 1 else f"{cap} ent."
        print(f"{nome:>7} {('$'+format(int(r['banca_necessaria_$']),',')):>18} {r['estouros']:>9} {('$'+format(int(r['pnl_$']),',')):>9}")
    print("\nQuanto MAIOR o limite: banca explode, estouro fica raro... mas PnL segue NEGATIVO.")
    print("Motivo: cada estouro custa a banca inteira; some todos = sempre negativo (acerto<54%).")


if __name__ == "__main__":
    main()
