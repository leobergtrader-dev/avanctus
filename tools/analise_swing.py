"""
analise_swing.py — Backtest de sinais de SWING/SPOT (canal Tio Huli) com dados reais da Binance.

Sinais: direcao + ativo + preco de entrada + stop-loss (sem alvo). Como nao ha TP definido,
testamos varias regras de saida e medimos EXPECTANCIA (R por trade) — a metrica certa p/ swing.
R = retorno em multiplos do risco (|entrada - stop|).  Expectancia > 0 = potencialmente lucrativo.

Salva tools/swing_resultado.json. Roda: py tools/analise_swing.py
"""
import os, re, sys, json, requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico_1001696398530.json")
OUT = os.path.join(os.path.dirname(__file__), "swing_resultado.json")

HORIZON_H = 24          # janela maxima do trade
RR_TARGETS = [1, 1.5, 2, 3]
TIME_EXITS = [1, 4, 12, 24]


def klines(symbol, t0, t1):
    out = []
    cur = t0
    while cur < t1:
        try:
            r = requests.get("https://api.binance.com/api/v3/klines",
                             params={"symbol": symbol, "interval": "1m", "startTime": cur,
                                     "endTime": t1, "limit": 1000}, timeout=20)
            arr = r.json()
            if not isinstance(arr, list) or not arr:
                break
            for k in arr:
                out.append({"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4])})
            if len(arr) < 1000:
                break
            cur = arr[-1][0] + 60000
        except Exception:
            break
    return out


def parse(msgs):
    sigs = []
    for m in msgs:
        t = m.get("text") or ""
        if "entrada" not in t.lower():
            continue
        di = re.search(r"(COMPRA\s*/\s*BUY|VENDA\s*/\s*SELL|\bBUY\b|\bSELL\b|COMPRA|VENDA)", t, re.I)
        cr = re.search(r"Cripto:\s*([A-Za-z0-9]+)", t)
        en = re.search(r"entrada:\s*([0-9.]+)", t, re.I)
        sl = re.search(r"SL[^:]*:+\s*([0-9.]+)", t, re.I)
        if not (di and cr and en and sl):
            continue
        d = "BUY" if re.search(r"COMPRA|BUY", di.group(1), re.I) else "SELL"
        try:
            ts = int(datetime.fromisoformat(m.get("date")).timestamp() * 1000)
        except Exception:
            continue
        sigs.append({"sym": cr.group(1).upper() + "USDT", "dir": d,
                     "entry": float(en.group(1)), "sl": float(sl.group(1)), "ts": ts})
    return sigs


def simular(sig, cs):
    e, sl, d = sig["entry"], sig["sl"], sig["dir"]
    risk = abs(e - sl)
    if risk <= 0:
        return None
    # valida se o preco real bate com a entrada declarada (descarta ativo mal-mapeado)
    if not cs or abs(cs[0]["o"] - e) / e > 0.03:
        return None
    sign = 1 if d == "BUY" else -1
    # stop no lado certo?
    if (d == "BUY" and sl >= e) or (d == "SELL" and sl <= e):
        return None
    res = {"rr": {}, "time": {}}
    # R:R targets
    for R in RR_TARGETS:
        tp = e + sign * R * risk
        outcome = None
        for c in cs:
            hit_sl = (c["l"] <= sl) if d == "BUY" else (c["h"] >= sl)
            hit_tp = (c["h"] >= tp) if d == "BUY" else (c["l"] <= tp)
            if hit_sl and hit_tp:
                outcome = -1.0; break          # ambos na mesma vela -> conservador (stop)
            if hit_sl:
                outcome = -1.0; break
            if hit_tp:
                outcome = float(R); break
        if outcome is None:                    # nao bateu nada -> fecha no fim
            outcome = sign * (cs[-1]["c"] - e) / risk
        res["rr"][R] = round(outcome, 3)
    # saidas por tempo
    for H in TIME_EXITS:
        alvo_t = sig["ts"] + H * 3600000
        c = next((x for x in cs if x["t"] >= alvo_t), cs[-1])
        res["time"][H] = round(sign * (c["c"] - e) / risk, 3)
    return res


def agreg(valores):
    n = len(valores)
    if not n:
        return None
    wins = sum(1 for v in valores if v > 0)
    soma = sum(valores)
    ganhos = sum(v for v in valores if v > 0)
    perdas = -sum(v for v in valores if v < 0)
    return {"n": n, "winrate": round(100 * wins / n, 1), "expectancia_R": round(soma / n, 3),
            "total_R": round(soma, 1), "profit_factor": round(ganhos / perdas, 2) if perdas else None}


def main():
    if not os.path.exists(HIST):
        print("Sem historico do canal."); return
    msgs = json.load(open(HIST, encoding="utf-8"))
    sigs = parse(msgs)
    print(f"Sinais parseados: {len(sigs)}")
    # candles por sinal
    resultados = []
    for s in sigs:
        cs = klines(s["sym"], s["ts"], s["ts"] + HORIZON_H * 3600000)
        r = simular(s, cs)
        if r:
            resultados.append(r)
    n = len(resultados)
    print(f"Sinais validos (preco confere): {n}")
    if not n:
        print("Nenhum sinal valido."); return

    out = {"fonte": "Tio Huli - Cripto Swing (Binance real)", "n_sinais": n, "rr": {}, "time": {}}
    for R in RR_TARGETS:
        out["rr"][str(R)] = agreg([r["rr"][R] for r in resultados])
    for H in TIME_EXITS:
        out["time"][str(H)] = agreg([r["time"][H] for r in resultados])
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n=== TIO HULI (swing) ===")
    print("Por alvo R:R (TP em X vezes o risco):")
    for R, v in out["rr"].items():
        print(f"  TP {R}R: win {v['winrate']}%  expectancia {v['expectancia_R']:+}R  PF {v['profit_factor']}  (n={v['n']})")
    print("Por saida no tempo:")
    for H, v in out["time"].items():
        print(f"  {H}h: expectancia {v['expectancia_R']:+}R  win {v['winrate']}%  (n={v['n']})")
    print("\nExpectancia > 0 = potencialmente lucrativo (antes de custos ~0.1%/lado).")


if __name__ == "__main__":
    main()
