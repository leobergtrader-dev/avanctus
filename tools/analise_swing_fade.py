"""
analise_swing_fade.py — Fade (ao contrario) dos sinais de SWING do Tio Huli, com candles reais.
No spot nao ha 'casa': se o sinal perde de verdade, fadear pode ser positivo (menos ~0.1% taxa).
Compara ORIGINAL vs FADE por regra de saida (expectancia em R). Reusa analise_swing.
"""
import os, sys, json
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import analise_swing as sw

ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico_1001696398530.json")


def main():
    msgs = json.load(open(HIST, encoding="utf-8"))
    sigs = sw.parse(msgs)
    print(f"Sinais: {len(sigs)}")
    orig = {"rr": {R: [] for R in sw.RR_TARGETS}, "time": {H: [] for H in sw.TIME_EXITS}}
    fade = {"rr": {R: [] for R in sw.RR_TARGETS}, "time": {H: [] for H in sw.TIME_EXITS}}
    linhas = []   # (ts, fade_24h, fade_1h)
    nval = 0
    for s in sorted(sigs, key=lambda x: x["ts"]):
        cs = sw.klines(s["sym"], s["ts"], s["ts"] + sw.HORIZON_H * 3600000)
        ro = sw.simular(s, cs)
        if not ro:
            continue
        # fade: direcao invertida + stop espelhado (mesma distancia de risco)
        fsig = dict(s)
        fsig["dir"] = "SELL" if s["dir"] == "BUY" else "BUY"
        fsig["sl"] = 2 * s["entry"] - s["sl"]
        rf = sw.simular(fsig, cs)
        if not rf:
            continue
        nval += 1
        for R in sw.RR_TARGETS:
            orig["rr"][R].append(ro["rr"][R]); fade["rr"][R].append(rf["rr"][R])
        for H in sw.TIME_EXITS:
            orig["time"][H].append(ro["time"][H]); fade["time"][H].append(rf["time"][H])
        linhas.append((s["ts"], rf["time"][24], rf["time"][1]))

    print(f"Validos: {nval}\n")
    print(f"{'saida':>10} {'ORIGINAL exp':>14} {'FADE exp':>12} {'FADE win':>10}")
    for R in sw.RR_TARGETS:
        ao = sw.agreg(orig["rr"][R]); af = sw.agreg(fade["rr"][R])
        print(f"  TP {R}R   {ao['expectancia_R']:>+9}R   {af['expectancia_R']:>+9}R   {af['winrate']:>7}%")
    for H in sw.TIME_EXITS:
        ao = sw.agreg(orig["time"][H]); af = sw.agreg(fade["time"][H])
        print(f"  {H}h     {ao['expectancia_R']:>+9}R   {af['expectancia_R']:>+9}R   {af['winrate']:>7}%")
    # ---- estabilidade do FADE (segurar 24h): out-of-sample + mes a mes ----
    def media(xs):
        return round(sum(xs) / len(xs), 3) if xs else None
    corte = int(len(linhas) * 0.7)
    tr = [r[1] for r in linhas[:corte]]; te = [r[1] for r in linhas[corte:]]
    print("\n=== FADE (segurar 24h) — OUT-OF-SAMPLE ===")
    print(f"  TREINO (70%): exp {media(tr):+}R  (n={len(tr)})")
    print(f"  TESTE  (30%): exp {media(te):+}R  (n={len(te)})")
    pm = defaultdict(list)
    for ts, f24, _ in linhas:
        pm[datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m")].append(f24)
    print("\n=== FADE 24h por mes ===")
    for mes in sorted(pm):
        v = pm[mes]
        print(f"  {mes}: exp {media(v):+}R  (n={len(v)})")
    print("\nFADE so e edge real se a expectancia ficar POSITIVA no TESTE e na maioria dos meses.")


if __name__ == "__main__":
    main()
