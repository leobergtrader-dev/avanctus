"""
analise_avalon.py — Backtest + Edge Scanner do canal "Operacoes - Trader Neto" (corretora Avalon),
usando candles REAIS e GRATUITOS da Binance (cripto real, nao OTC).

Mesma metodologia do scanner Avanctus: win/loss real por vela, CI de Wilson, out-of-sample,
backtest de estrategias (flat/gale/1-em-5) e garimpo de edge (#1..#5).
Salva tools/avalon_resultado.json. Roda: py tools/analise_avalon.py
"""
import os, re, sys, json, math, requests
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind

ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico_1001738261211.json")
OUT = os.path.join(os.path.dirname(__file__), "avalon_resultado.json")
BR = timezone(timedelta(hours=-3))

ASSET2BIN = {
    "BITCOIN": "BTCUSDT", "CARDANO": "ADAUSDT", "SOLANA": "SOLUSDT", "TRON": "TRXUSDT",
    "SHIBA INU": "SHIBUSDT", "SHIBA": "SHIBUSDT", "ARBITRUM": "ARBUSDT",
    "TRUMP": "TRUMPUSDT", "TUMP": "TRUMPUSDT",
}


def wilson(w, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = w / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round((c - h) * 100, 1), round((c + h) * 100, 1))


def taxa(w, n):
    return round(100 * w / n, 1) if n else None


def klines(symbol, t0, t1):
    out = {}
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
                out[k[0]] = {"open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])}
            cur = arr[-1][0] + 60000
            if len(arr) < 1000:
                break
        except Exception:
            break
    return out


def parse_sinais(msgs):
    s = {}
    for m in msgs:
        t = m.get("text") or ""
        if "ENTRADA" not in t.upper():
            continue
        c = re.sub(r"[*_📊🚨⏰➡️🔞]", "", t)
        a = re.search(r"([A-Za-z ]{2,25}?)\s*->\s*(\d+)\s*MIN", c, re.I)
        di = re.search(r"\b(COMPRAR|VENDER)\b", c, re.I)
        tm = re.search(r"(\d{1,2}:\d{2})", c)
        if not (a and di and tm):
            continue
        sym = ASSET2BIN.get(re.sub(r"\s+", " ", a.group(1)).strip().upper())
        if not sym:
            continue
        try:
            br = datetime.fromisoformat(m.get("date")).astimezone(BR)
        except Exception:
            continue
        h, mi = map(int, tm.group(1).split(":"))
        entry = datetime(br.year, br.month, br.day, h, mi, tzinfo=BR)
        if entry > br + timedelta(minutes=15):
            entry -= timedelta(days=1)
        ts = int(entry.astimezone(timezone.utc).timestamp() * 1000)
        direction = "BUY" if di.group(1).upper() == "COMPRAR" else "SELL"
        s[(sym, ts)] = direction
    return s


def win_dir(c, direction):
    if not c or c["close"] == c["open"]:
        return None
    return (c["close"] > c["open"]) == (direction == "BUY")


def gale_sim(outs, b, base, levels, mult):
    stake, pnl = base, 0.0
    for i in range(levels + 1):
        if i >= len(outs) or outs[i] is None:
            return pnl
        if outs[i]:
            return pnl + stake * b
        pnl -= stake; stake = round(stake * mult, 2)
    return pnl


def main():
    if not os.path.exists(HIST):
        print("Falta o historico do canal. Rode: py tools/historico_dump.py 1000 -1001738261211")
        return
    msgs = json.load(open(HIST, encoding="utf-8"))
    sinais = parse_sinais(msgs)
    print(f"Sinais parseados: {len(sinais)}")
    porsym = {}
    for (sym, ts) in sinais:
        porsym.setdefault(sym, []).append(ts)
    candles = {}
    for sym, tss in porsym.items():
        candles[sym] = klines(sym, min(tss) - 40 * 60000, max(tss) + 10 * 60000)
        print(f"  {sym}: {len(candles[sym])} candles Binance")

    regs = []
    for (sym, ts), direction in sorted(sinais.items(), key=lambda x: x[0][1]):
        cmap = candles.get(sym, {})
        mc = cmap.get(ts)
        if not mc:
            continue
        w = win_dir(mc, direction)
        if w is None:
            continue
        pre = [cmap[ts - k * 60000] for k in range(25, 0, -1) if (ts - k * 60000) in cmap]
        an = ind.analisar(pre + [mc], direction) if len(pre) >= 22 else None
        outs = [win_dir(cmap.get(ts + k * 60000), direction) for k in range(6)]
        regs.append({"sym": sym, "ts": ts, "dir": direction, "win": w, "outs": outs,
                     "hora": datetime.fromtimestamp(ts / 1000, BR).hour,
                     "tend_ok": None if not an else (an.get("tendencia") == ("alta" if direction == "BUY" else "baixa"))})
    n = len(regs)
    if not n:
        print("Sem candles casados. Verifique fuso/datas."); return
    corte = int(n * 0.7)
    for i, r in enumerate(regs):
        r["split"] = "train" if i < corte else "test"

    wins = sum(1 for r in regs if r["win"])
    win2 = sum(1 for r in regs if any(r["outs"][:2]))
    win3 = sum(1 for r in regs if any(r["outs"][:3]))

    b, base = 0.85, 25
    sim = []
    for nome, (lv, mu) in {"Flat": (0, 1), "Gale 2": (2, 2), "Gale 3": (3, 2), "1-em-5": (4, (1 + b) / b)}.items():
        pnl = eq = peak = maxdd = 0.0
        for r in regs:
            s = gale_sim(r["outs"], b, base, lv, mu)
            pnl += s; eq += s; peak = max(peak, eq); maxdd = max(maxdd, peak - eq)
        sim.append({"estrategia": nome, "pnl": round(pnl, 2), "drawdown_max": round(maxdd, 2)})

    def cond(fn):
        out = {}
        for sp in ("train", "test"):
            d = {}
            for r in [x for x in regs if x["split"] == sp]:
                k = fn(r)
                if k is None:
                    continue
                d.setdefault(k, [0, 0]); d[k][1] += 1; d[k][0] += 1 if r["win"] else 0
            out[sp] = {str(k): {"wr": taxa(v[0], v[1]), "n": v[1], "ci": wilson(v[0], v[1])} for k, v in d.items()}
        return out

    seq = [r["win"] for r in regs]
    aw = [seq[i + 1] for i in range(len(seq) - 1) if seq[i]]
    al = [seq[i + 1] for i in range(len(seq) - 1) if not seq[i]]

    res = {
        "fonte": "Avalon / Trader Neto (Binance real)", "n_sinais": n,
        "acerto_entrada": taxa(wins, n), "acerto_ate_2": taxa(win2, n), "acerto_ate_3": taxa(win3, n),
        "ci_entrada": wilson(wins, n), "breakeven": 54.1,
        "estrategias": sim,
        "por_ativo": cond(lambda r: r["sym"]),
        "por_hora": cond(lambda r: f"{r['hora']:02d}h"),
        "por_direcao": cond(lambda r: r["dir"]),
        "por_tendencia": cond(lambda r: None if r["tend_ok"] is None else ("a favor" if r["tend_ok"] else "contra")),
        "autocorr": {"apos_win": {"wr": taxa(sum(aw), len(aw)), "n": len(aw), "ci": wilson(sum(aw), len(aw))},
                     "apos_loss": {"wr": taxa(sum(al), len(al)), "n": len(al), "ci": wilson(sum(al), len(al))}},
    }
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n=== RESULTADO AVALON / TRADER NETO ===")
    print(json.dumps({k: res[k] for k in ("n_sinais", "acerto_entrada", "ci_entrada", "acerto_ate_3", "breakeven", "estrategias")}, ensure_ascii=False, indent=2))
    print("\nPor ativo (treino):", json.dumps(res["por_ativo"]["train"], ensure_ascii=False))
    print("Por direcao (treino):", json.dumps(res["por_direcao"]["train"], ensure_ascii=False))


if __name__ == "__main__":
    main()
