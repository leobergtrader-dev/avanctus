"""
analytics.py — Avaliacao matematica de estrategias e relatorio.

Dado o win-rate por entrada (p) e o payout (b), calcula EV, perda maxima e risco
de cada estrategia (flat, gale-N, 1-em-5 escalonado). Tudo deterministico.
"""
import csv
import os
import json
from collections import defaultdict


# ---------------- estrategias ----------------

def gale_eval(p, b, base, levels, mult):
    """levels = niveis de gale (0 = flat). Retorna EV por ciclo, perda maxima, prob de perda total."""
    stakes = [base * (mult ** i) for i in range(levels + 1)]
    ev = 0.0
    for i in range(levels + 1):              # ganha no nivel i (perde i vezes antes)
        prob = ((1 - p) ** i) * p
        investido_antes = sum(stakes[:i])
        net = stakes[i] * b - investido_antes
        ev += prob * net
    prob_all = (1 - p) ** (levels + 1)        # perde tudo
    ev += prob_all * (-sum(stakes))
    return {
        "ev_ciclo": round(ev, 2),
        "perda_maxima": round(sum(stakes), 2),
        "prob_perda_total": round(prob_all, 4),
        "stakes": [round(s, 2) for s in stakes],
    }


def recovery_mult(b):
    """Multiplicador que recupera perdas + lucro base (~2.18 p/ payout 0.85)."""
    return (1 + b) / b


def comparar_estrategias(p, b=0.85, base=25, sinais_por_dia=20):
    estrategias = {
        "Flat (sem gale)":      gale_eval(p, b, base, 0, 1),
        "Gale 2 (x2)":          gale_eval(p, b, base, 2, 2),
        "Gale 3 (x2)":          gale_eval(p, b, base, 3, 2),
        "1-em-5 (x2.18)":       gale_eval(p, b, base, 4, recovery_mult(b)),
    }
    ciclos_dia = max(1, sinais_por_dia)
    out = []
    for nome, r in estrategias.items():
        # risco de pelo menos um "estouro" (perda total) no dia
        risco_dia = 1 - (1 - r["prob_perda_total"]) ** ciclos_dia
        out.append({
            "estrategia": nome,
            "ev_por_ciclo": r["ev_ciclo"],
            "perda_maxima": r["perda_maxima"],
            "prob_perda_total": r["prob_perda_total"],
            "risco_estouro_dia": round(risco_dia, 3),
            "veredito": "POSITIVO" if r["ev_ciclo"] > 0 else "NEGATIVO",
        })
    return out


# ---------------- relatorio dos dados coletados ----------------

def _rows(path):
    if not os.path.exists(path):
        return []
    try:
        return list(csv.DictReader(open(path, encoding="utf-8")))
    except OSError:
        return []


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def relatorio(ops_csv, analises_csv, payout=0.85, base=25):
    rows = _rows(ops_csv)
    mains = [r for r in rows if r.get("nivel") == "ENTRADA"]
    n = len(mains)
    wins = sum(1 for r in mains if r.get("resultado") == "WIN")
    p = (wins / n) if n else None
    total_pnl = sum(_num(r.get("pnl")) for r in rows)

    # payout real medido
    win_rows = [r for r in rows if r.get("resultado") == "WIN" and _num(r.get("valor")) > 0]
    payout_medido = (sum(_num(r["pnl"]) / _num(r["valor"]) for r in win_rows) / len(win_rows)) if win_rows else None

    def por(campo_fn):
        d = defaultdict(lambda: [0, 0, 0.0])
        for r in mains:
            k = campo_fn(r)
            d[k][0] += 1 if r.get("resultado") == "WIN" else 0
            d[k][1] += 1
        for r in rows:
            d[campo_fn(r)][2] += _num(r.get("pnl"))
        return {k: {"wins": v[0], "total": v[1], "winrate": round(100 * v[0] / v[1], 1) if v[1] else None,
                    "pnl": round(v[2], 2)} for k, v in d.items()}

    por_ativo = por(lambda r: r.get("ativo", "?"))
    por_hora = por(lambda r: (r.get("quando", "")[11:13] or "?") + "h")
    por_dir = por(lambda r: r.get("direcao", "?"))

    # filtro IA (sombra): cruza analises com resultados das entradas
    filtro = _avaliar_filtro(mains, _rows(analises_csv))

    p_calc = p if p is not None else 0.5
    sim = comparar_estrategias(p_calc, payout_medido or payout, base, max(1, n // 7 or 10))

    def _carrega(nome):
        p = os.path.join(os.path.dirname(__file__), nome)
        if os.path.exists(p):
            try:
                return json.load(open(p, encoding="utf-8"))
            except (OSError, ValueError):
                return None
        return None

    backtest = _carrega("backtest_resultado.json")
    edge = _carrega("edge_resultado.json")
    avalon = _carrega("avalon_resultado.json")
    swing = _carrega("swing_resultado.json")

    return {
        "backtest": backtest,
        "edge": edge,
        "avalon": avalon,
        "swing": swing,
        "amostra": n, "wins": wins, "winrate": round(100 * p, 1) if p is not None else None,
        "pnl_total": round(total_pnl, 2),
        "payout_medido": round(payout_medido * 100, 1) if payout_medido else None,
        "breakeven": round(100 / (1 + (payout_medido or payout)), 1),
        "por_ativo": por_ativo, "por_hora": por_hora, "por_direcao": por_dir,
        "filtro_ia": filtro,
        "simulador": sim, "p_usado": round(p_calc * 100, 1),
    }


def _avaliar_filtro(mains, analises):
    """Junta cada analise (por ativo+horario) ao resultado da entrada e mede
    se score alto ganha mais que score baixo."""
    if not analises:
        return None
    # index resultados por (ativo, hora-minuto aproximado)
    res_por_chave = {}
    for r in mains:
        chave = (r.get("ativo"), (r.get("quando", "")[11:16]))
        res_por_chave[chave] = r.get("resultado")
    alto = [0, 0]
    baixo = [0, 0]
    for a in analises:
        sc = a.get("score")
        try:
            sc = float(sc)
        except (TypeError, ValueError):
            continue
        # tenta achar o resultado da entrada correspondente
        result = None
        for r in mains:
            if r.get("ativo") == a.get("ativo"):
                result = r.get("resultado")
                break
        if result is None:
            continue
        bucket = alto if sc >= 0.5 else baixo
        bucket[1] += 1
        if result == "WIN":
            bucket[0] += 1
    def wr(b):
        return round(100 * b[0] / b[1], 1) if b[1] else None
    return {"score_alto": {"wins": alto[0], "total": alto[1], "winrate": wr(alto)},
            "score_baixo": {"wins": baixo[0], "total": baixo[1], "winrate": wr(baixo)}}
