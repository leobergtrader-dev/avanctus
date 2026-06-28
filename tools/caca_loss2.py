"""
caca_loss2.py — Estrategia "1 win direto por loss" (martingale ate 6 entradas), com os
MARCADORES REAIS do canal VIVA DE RENDA (o que voce ve ao vivo):
  WIN DIRETO -> ganhou na entrada     | WIN NO GALE / Seguimos em Analise -> entrada perdeu

Gatilho: apos um "Seguimos em Analise" (loss). Recuperar buscando 1 WIN DIRETO, aumentando
a aposta ate 6 tentativas. Mede: P(recuperar ate N), chance de estouro, e PnL simulado real.

Roda: py tools/caca_loss2.py
"""
import os, sys, json, re

sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico_1002835208093.json")
OUT = os.path.join(os.path.dirname(__file__), "caca_loss2_resultado.json")
PAYOUT = 0.85
MAX_ENTRADAS = 6


def classificar(t):
    tl = t.lower()
    if re.search(r"seguimos em an[áa]lise", tl):
        return "LOSS"
    if "win" in tl and "gale" in tl:
        return "WIN_GALE"
    if "win" in tl:
        return "WIN_DIRETO"
    return None


def main():
    msgs = json.load(open(HIST, encoding="utf-8"))
    msgs = sorted(msgs, key=lambda m: m.get("date") or "")
    seq = [c for m in msgs if (c := classificar(m.get("text") or ""))]
    n = len(seq)
    cnt = {k: seq.count(k) for k in ("WIN_DIRETO", "WIN_GALE", "LOSS")}
    p_direto = round(100 * cnt["WIN_DIRETO"] / n, 1) if n else 0
    print(f"Marcadores: {cnt} | total {n}")
    print(f"Taxa WIN DIRETO (base): {p_direto}%  | break-even bin. ~54%\n")

    # entrada "ganha" para a estrategia = WIN_DIRETO; qualquer outra coisa = perdeu a entrada
    venceu = [x == "WIN_DIRETO" for x in seq]

    # apos cada LOSS, quantas entradas ate o 1o WIN DIRETO?
    recuper = []      # nº de entradas ate recuperar (1..6) ou None se estourou
    for i in range(n):
        if seq[i] != "LOSS":
            continue
        achou = None
        for k in range(1, MAX_ENTRADAS + 1):
            if i + k < n and venceu[i + k]:
                achou = k
                break
            if i + k >= n:
                break
        recuper.append(achou)

    total_gatilhos = len(recuper)
    dentro = [r for r in recuper if r is not None]
    cumK = {}
    for K in range(1, MAX_ENTRADAS + 1):
        cumK[K] = sum(1 for r in dentro if r <= K)
    estouros = sum(1 for r in recuper if r is None)

    # martingale: bet_i recupera tudo + 1 unidade. EV simulado real.
    def bets():
        S = 0.0; out = []
        for _ in range(MAX_ENTRADAS):
            b = (S + 1.0) / PAYOUT
            out.append(b); S += b
        return out, S
    BETS, S_total = bets()
    pnl = 0.0
    for r in recuper:
        if r is None:
            pnl -= S_total          # estourou: perdeu as 6 apostas
        else:
            pnl += 1.0              # recuperou: +1 unidade liquida

    res = {
        "marcadores": cnt, "total_sinais": n, "taxa_win_direto": p_direto,
        "gatilhos_loss": total_gatilhos,
        "prob_recuperar_ate": {K: round(100 * cumK[K] / total_gatilhos, 1) for K in cumK},
        "estouros": estouros, "prob_estouro": round(100 * estouros / total_gatilhos, 1),
        "aposta_total_se_estourar": round(S_total, 1),
        "pnl_unidades": round(pnl, 1),
        "pnl_por_gatilho": round(pnl / total_gatilhos, 3),
    }
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"Gatilhos (apos um LOSS): {total_gatilhos}\n")
    print("P(conseguir 1 WIN DIRETO ate a entrada N, apos um loss):")
    for K in range(1, MAX_ENTRADAS + 1):
        print(f"  ate {K}a entrada: {res['prob_recuperar_ate'][K]:>5}%  (aposta acumulada {round(sum(BETS[:K]),1)}u)")
    print(f"\nESTOUROS (6 entradas sem win direto): {estouros}  ({res['prob_estouro']}% dos gatilhos)")
    print(f"Se estourar, perde {res['aposta_total_se_estourar']} unidades de uma vez.")
    print(f"\nPnL SIMULADO (real): {res['pnl_unidades']:+} unidades em {total_gatilhos} gatilhos "
          f"({res['pnl_por_gatilho']:+}/gatilho)")
    print("(1 unidade = o valor da aposta-base. Negativo = estrategia perde.)")


if __name__ == "__main__":
    main()
