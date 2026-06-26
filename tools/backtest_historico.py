"""
backtest_historico.py — Backtest REAL das estrategias sobre os sinais historicos do canal.

Para cada sinal (ativo, horario, direcao) extraido do historico, busca o CANDLE REAL
e determina win/loss de verdade (close vs open). Depois simula flat/gale/1-em-5 e mede
PnL, drawdown e pior sequencia. Valida o fuso comparando com o resultado do canal.

Salva tools/backtest_resultado.json (lido pelo relatorio).
Roda: py tools/backtest_historico.py
"""
import os
import re
import sys
import json
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import market

ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico.json")
OUT = os.path.join(os.path.dirname(__file__), "backtest_resultado.json")
BR = timezone(timedelta(hours=-3))  # Brasilia (sem horario de verao)

# nome do canal (sem OTC) -> ticker
try:
    _m = json.load(open(os.path.join(os.path.dirname(__file__), "symbols_otc.json"), encoding="utf-8"))
    NAME2TICK = {k.replace("(OTC)", "").strip().upper(): v for k, v in _m.items()}
except Exception:
    NAME2TICK = {}

LINE = re.compile(r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ]+?)\s*-\s*(\d{1,2}:\d{2})\s*-\s*(PUT|CALL)\s*-*>\s*\**\s*(GAIN|WIN|LOSS|LOSE)", re.I)

def buscar_janela(ticker, ts_ms):
    """Busca candles de ts_ms ate ts_ms+7min; indexa por time."""
    import requests
    try:
        r = requests.get(
            f"{market.API_URL}/aggregated-prices/prices",
            headers={"api-key": market.API_KEY, "Origin": market.ORIGIN},
            params={"slot": "default", "pair": ticker, "startTime": ts_ms - 60000,
                    "endTime": ts_ms + 8 * 60000, "type": "otc", "interval": "1m", "skip": 0, "limit": 12},
            timeout=12,
        )
        out = {}
        for c in r.json():
            out[c["time"]] = c
        return out
    except Exception:
        return {}


def win(candle, direcao):
    if not candle:
        return None
    o, c = candle["openPrice"], candle["closePrice"]
    if o == c:
        return "DRAW"
    sobe = c > o
    return "WIN" if (sobe == (direcao == "BUY")) else "LOSS"


def gale_sim(outcomes, b, base, levels, mult):
    """Simula uma sequencia. outcomes: lista de WIN/LOSS/DRAW por nivel. Retorna pnl da sequencia."""
    stake = base
    pnl = 0.0
    for i in range(levels + 1):
        if i >= len(outcomes) or outcomes[i] is None:
            return pnl  # sem dado -> encerra
        res = outcomes[i]
        if res == "WIN":
            return pnl + stake * b
        if res == "DRAW":
            return pnl  # devolve stake
        pnl -= stake
        stake = round(stake * mult, 2)
    return pnl  # perdeu todos os niveis


def main():
    msgs = json.load(open(HIST, encoding="utf-8"))
    # extrai sinais
    sinais = {}
    for m in msgs:
        try:
            msg_dt = datetime.fromisoformat(m.get("date"))
        except Exception:
            continue
        br = msg_dt.astimezone(BR)
        for asset, hhmm, direc, ch_res in LINE.findall(m.get("text") or ""):
            nome = asset.strip().upper()
            tick = NAME2TICK.get(nome)
            if not tick:
                continue
            h, mi = map(int, hhmm.split(":"))
            entry = datetime(br.year, br.month, br.day, h, mi, tzinfo=BR)
            if entry > br + timedelta(minutes=15):   # relatorio pos-meia-noite
                entry -= timedelta(days=1)
            ts = int(entry.astimezone(timezone.utc).timestamp() * 1000)
            direction = "BUY" if direc.upper() == "CALL" else "SELL"
            sinais[(tick, ts, direction)] = (ch_res.upper() in ("GAIN", "WIN"))

    print(f"Sinais unicos: {len(sinais)}. Buscando candles reais...")
    registros = []
    for i, ((tick, ts, direction), ch_gain) in enumerate(sorted(sinais.items(), key=lambda x: x[0][1])):
        janela = buscar_janela(tick, ts)
        outs = [win(janela.get(ts + k * 60000), direction) for k in range(6)]  # main + 5 gales
        if outs[0] is None:
            continue
        registros.append({"ts": ts, "tick": tick, "dir": direction, "ch_gain": ch_gain, "outs": outs})
        if i % 50 == 0:
            print(f"  {i}/{len(sinais)}...")

    n = len(registros)
    if not n:
        print("Sem candles. Abortando."); return

    main_wins = sum(1 for r in registros if r["outs"][0] == "WIN")
    win2 = sum(1 for r in registros if "WIN" in r["outs"][:2])
    win3 = sum(1 for r in registros if "WIN" in r["outs"][:3])
    ch_gains = sum(1 for r in registros if r["ch_gain"])
    # validacao do fuso: concordancia entre "win em ate 3 velas" e canal disse GAIN
    concorda = sum(1 for r in registros if ("WIN" in r["outs"][:3]) == r["ch_gain"])

    b, base = 0.85, 25
    estrats = {
        "Flat (sem gale)": (0, 1),
        "Gale 2 (x2)": (2, 2),
        "Gale 3 (x2)": (3, 2),
        "1-em-5 (x2.18)": (4, (1 + b) / b),
    }
    sim = []
    for nome, (levels, mult) in estrats.items():
        pnl, eq, peak, maxdd, streak, worst = 0.0, 0.0, 0.0, 0, 0, 0
        for r in registros:
            s = gale_sim(r["outs"], b, base, levels, mult)
            pnl += s
            eq += s
            peak = max(peak, eq)
            maxdd = max(maxdd, peak - eq)
            if s < 0:
                streak += 1; worst = max(worst, streak)
            else:
                streak = 0
        sim.append({"estrategia": nome, "pnl_total": round(pnl, 2),
                    "drawdown_max": round(maxdd, 2), "pior_sequencia": worst})

    resultado = {
        "gerado_em": None,  # preenchido fora
        "n_sinais": n,
        "acerto_entrada": round(100 * main_wins / n, 1),
        "acerto_ate_2_velas": round(100 * win2 / n, 1),
        "acerto_ate_3_velas": round(100 * win3 / n, 1),
        "canal_declarou_gain": round(100 * ch_gains / n, 1),
        "validacao_fuso_concordancia": round(100 * concorda / n, 1),
        "breakeven": round(100 / (1 + b), 1),
        "estrategias": sim,
    }
    json.dump(resultado, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n=== RESULTADO ===")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
