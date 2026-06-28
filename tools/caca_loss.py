"""
caca_loss.py — P(WIN | N derrotas seguidas antes) nos sinais da Avanctus, com candles REAIS.

Testa a hipotese "depois de N losses, a proxima tem mais chance de ganhar?" (reversao de mare).
Duas series:
  (a) com gale  -> sinal vence se entrada OU gales (janela de 3 velas) vencer
  (b) so entrada -> vela unica
Para N=3..7: prob de WIN logo apos >= N losses consecutivos, com amostra (n) e IC de Wilson.

Roda: py tools/caca_loss.py
"""
import os, sys, re, json, math
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import backtest_historico as B   # reusa buscar_janela, win, NAME2TICK, BR, market

ROOT = os.path.dirname(os.path.dirname(__file__))
# usa o maior arquivo disponivel do canal Avanctus
CANDIDATOS = ["historico_1002835208093.json", "historico.json"]
HIST = next((os.path.join(ROOT, ".tmp", f) for f in CANDIDATOS if os.path.exists(os.path.join(ROOT, ".tmp", f))), None)
OUT = os.path.join(os.path.dirname(__file__), "caca_loss_resultado.json")


def wilson(w, n, z=1.96):
    if n == 0:
        return (None, None)
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round((c - h) * 100, 1), round((c + h) * 100, 1))


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
            entry = datetime(br.year, br.month, br.day, h, mi, tzinfo=B.BR)
            if entry > br + timedelta(minutes=15):
                entry -= timedelta(days=1)
            ts = int(entry.astimezone(timezone.utc).timestamp() * 1000)
            s[(tk, ts)] = "BUY" if direc.upper() == "CALL" else "SELL"
    return s


def cond_apos_losses(series, nmax=7):
    """series: lista bool (True=win) em ordem cronologica. Retorna P(win | >=N losses antes)."""
    out = {}
    for N in range(3, nmax + 1):
        wins = tot = 0
        c = 0  # losses consecutivos correntes
        for x in series:
            if c >= N:                 # antes deste, ja havia >=N losses
                tot += 1
                if x:
                    wins += 1
            c = 0 if x else c + 1
        out[N] = {"n": tot, "wins": wins,
                  "p_win": round(100 * wins / tot, 1) if tot else None,
                  "ic": wilson(wins, tot)}
    return out


def main():
    if not HIST:
        print("Sem historico do canal Avanctus."); return
    msgs = json.load(open(HIST, encoding="utf-8"))
    sinais = parse(msgs)
    print(f"Arquivo: {os.path.basename(HIST)} | sinais unicos: {len(sinais)}")
    entry_serie, gale_serie = [], []
    for (tk, ts), direction in sorted(sinais.items(), key=lambda x: x[0][1]):
        jan = B.buscar_janela(tk, ts)
        e = B.win(jan.get(ts), direction)
        if e is None:
            continue
        entry_serie.append(e == "WIN")
        gale_serie.append(any(B.win(jan.get(ts + k * 60000), direction) == "WIN" for k in range(3)))
    n = len(entry_serie)
    base_e = round(100 * sum(entry_serie) / n, 1) if n else None
    base_g = round(100 * sum(gale_serie) / n, 1) if n else None
    res = {
        "n_sinais": n, "base_entrada": base_e, "base_com_gale": base_g, "breakeven": 54.1,
        "a_com_gale": cond_apos_losses(gale_serie),
        "b_so_entrada": cond_apos_losses(entry_serie),
    }
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\nSinais validos: {n} | base ENTRADA {base_e}% | base COM GALE {base_g}% | break-even 54,1%\n")
    for titulo, chave in (("(a) COM GALE", "a_com_gale"), ("(b) SO ENTRADA", "b_so_entrada")):
        print(f"=== {titulo}: P(WIN apos >=N losses) ===")
        for N in range(3, 8):
            d = res[chave][N]
            ic = f"[{d['ic'][0]}-{d['ic'][1]}]" if d['ic'][0] is not None else "-"
            pw = f"{d['p_win']}%" if d['p_win'] is not None else "sem dados"
            print(f"  apos {N} losses: {pw:>10}  (amostra n={d['n']:<4} IC95 {ic})")
        print()


if __name__ == "__main__":
    main()
