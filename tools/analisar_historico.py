"""
analisar_historico.py — Estatistica dos RESULTADOS auto-reportados pelo canal.

Le .tmp/historico.json (gerado por historico_dump.py), extrai as linhas de resultado
(ATIVO - HORA - DIRECAO -> GAIN/LOSS) e calcula win/loss geral, por ativo, hora e direcao.

ATENCAO: numeros AUTODECLARADOS pelo canal (tendem a ser otimistas). O numero real
e o que medimos operando na demo (analisar.py).
"""
import os, sys, re, json
from collections import defaultdict
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SRC = os.path.join(os.path.dirname(__file__), "..", ".tmp", "historico.json")
if not os.path.exists(SRC):
    print("Rode antes: py tools/historico_dump.py"); sys.exit(0)

msgs = json.load(open(SRC, encoding="utf-8"))

# Linha de resultado: ATIVO - HH:MM - PUT/CALL -> (GAIN|WIN|LOSS|LOSE)
LINE = re.compile(
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ]+?)\s*-\s*(\d{1,2}:\d{2})\s*-\s*(PUT|CALL)\s*-*>\s*\**\s*(GAIN|WIN|LOSS|LOSE)",
    re.I,
)

ops = {}  # dedup por (dia, ativo, hora, direcao)
for m in msgs:
    dia = (m.get("date") or "")[:10]
    for asset, hhmm, direc, res in LINE.findall(m.get("text") or ""):
        asset = asset.strip().upper()
        direc = direc.upper()
        win = res.upper() in ("GAIN", "WIN")
        ops[(dia, asset, hhmm, direc)] = win

if not ops:
    print("Nenhuma linha de resultado encontrada na amostra baixada."); sys.exit(0)

total = len(ops)
wins = sum(1 for v in ops.values() if v)
def pct(a, b): return f"{100*a/b:.1f}%" if b else "-"

dias = sorted({k[0] for k in ops})
print("=" * 56)
print("  ESTATISTICA DO CANAL (auto-reportada)")
print("=" * 56)
print(f"Periodo: {dias[0]} a {dias[-1]}  ({len(dias)} dias)")
print(f"Operacoes: {total} | WIN: {wins} | LOSS: {total-wins}")
print(f">>> Taxa de acerto declarada: {pct(wins, total)} <<<")

por_ativo = defaultdict(lambda: [0, 0])
por_hora = defaultdict(lambda: [0, 0])
por_dir = defaultdict(lambda: [0, 0])
for (dia, asset, hhmm, direc), win in ops.items():
    for d, key in ((por_ativo, asset), (por_hora, hhmm[:2]), (por_dir, direc)):
        d[key][0] += 1 if win else 0
        d[key][1] += 1

print("\n--- Por ativo ---")
for a, (w, t) in sorted(por_ativo.items(), key=lambda x: -x[1][1]):
    print(f"  {a:14} {pct(w,t):>6} ({w}/{t})")
print("\n--- Por hora ---")
for h, (w, t) in sorted(por_hora.items()):
    print(f"  {h}h  {pct(w,t):>6} ({w}/{t})")
print("\n--- Por direcao ---")
for dd, (w, t) in por_dir.items():
    print(f"  {dd:4} {pct(w,t):>6} ({w}/{t})")

print("\nLembrete: numero do CANAL (otimista). Break-even real ~54% (payout 85%).")
print("=" * 56)
