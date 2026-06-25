"""
analisar.py — Relatorio de estatisticas das operacoes (.tmp/operacoes.csv).

Responde as perguntas que decidem a estrategia:
 - Qual a acuracia REAL dos sinais (entradas principais)?
 - Estamos no lucro ou prejuizo? (PnL liquido)
 - Qual o payout real medido?
 - Quais ativos / horarios sao melhores?
 - O gale recupera mais do que destroi?

Roda: py tools/analisar.py
"""

import os
import sys
import csv
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CSV = os.path.join(os.path.dirname(__file__), "..", ".tmp", "operacoes.csv")

if not os.path.exists(CSV):
    print("Ainda nao ha operacoes registradas (.tmp/operacoes.csv).")
    print("Rode o robo (5-ROBO.bat) e deixe coletar alguns sinais primeiro.")
    sys.exit(0)

rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
if not rows:
    print("CSV vazio ainda.")
    sys.exit(0)

def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0

def pct(a, b):
    return f"{(100*a/b):.1f}%" if b else "-"

# ---- Reconstroi sequencias (ENTRADA + gales ate fechar) ----
seqs, cur = [], None
for r in rows:
    if r["nivel"] == "ENTRADA":
        if cur:
            seqs.append(cur)
        cur = [r]
    elif cur:
        cur.append(r)
if cur:
    seqs.append(cur)

total_pnl = sum(num(r.get("pnl")) for r in rows)
mains = [r for r in rows if r["nivel"] == "ENTRADA"]
main_wins = sum(1 for r in mains if r["resultado"] == "WIN")

# payout real medido a partir dos WINs
win_rows = [r for r in rows if r["resultado"] == "WIN" and num(r["valor"]) > 0]
payout = (sum(num(r["pnl"]) / num(r["valor"]) for r in win_rows) / len(win_rows)) if win_rows else None
breakeven = (1 / (1 + payout)) if payout else None

seq_wins = sum(1 for s in seqs if s[-1]["resultado"] in ("WIN", "DRAW"))

print("=" * 56)
print("  RELATORIO TRADE IA")
print("=" * 56)
print(f"Sinais operados (sequencias): {len(seqs)}")
print(f"Entradas totais (com gale):   {len(rows)}")
print(f"PnL liquido:                  {total_pnl:+.2f}")
print()
print(f"Acuracia dos SINAIS (entrada principal): {pct(main_wins, len(mains))}  ({main_wins}/{len(mains)})")
print(f"Sucesso por SEQUENCIA (com gale):        {pct(seq_wins, len(seqs))}  ({seq_wins}/{len(seqs)})")
if payout:
    print(f"Payout real medido:  {payout*100:.1f}%   ->  precisa acertar > {breakeven*100:.1f}% p/ lucrar (sem gale)")
    edge = "ACIMA do break-even (promissor)" if len(mains) and (main_wins/len(mains)) > breakeven else "ABAIXO do break-even (cuidado!)"
    print(f"Veredito atual: {edge}")

# ---- Por ativo ----
por_ativo = defaultdict(lambda: [0, 0, 0.0])  # wins, total, pnl
for r in mains:
    a = por_ativo[r["ativo"]]
    a[0] += 1 if r["resultado"] == "WIN" else 0
    a[1] += 1
for r in rows:
    por_ativo[r["ativo"]][2] += num(r.get("pnl"))
print("\n--- Por ativo (entrada principal) ---")
for ativo, (w, t, p) in sorted(por_ativo.items(), key=lambda x: -x[1][2]):
    print(f"  {ativo:14} win {pct(w,t):>6} ({w}/{t})   PnL {p:+.2f}")

# ---- Por hora ----
por_hora = defaultdict(lambda: [0, 0])
for r in mains:
    h = r["quando"][11:13] if len(r["quando"]) >= 13 else "??"
    por_hora[h][0] += 1 if r["resultado"] == "WIN" else 0
    por_hora[h][1] += 1
print("\n--- Por hora (entrada principal) ---")
for h, (w, t) in sorted(por_hora.items()):
    print(f"  {h}h  win {pct(w,t):>6} ({w}/{t})")

# ---- Gale ----
mains_loss = [s for s in seqs if s[0]["resultado"] == "LOSS"]
recuperadas = sum(1 for s in mains_loss if s[-1]["resultado"] in ("WIN", "DRAW"))
print("\n--- Gale ---")
print(f"  Entradas principais que perderam: {len(mains_loss)}")
print(f"  Recuperadas pelo gale:            {recuperadas}  ({pct(recuperadas, len(mains_loss))})")
print("=" * 56)
