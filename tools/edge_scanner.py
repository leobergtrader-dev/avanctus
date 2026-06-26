"""
edge_scanner.py — Garimpo de edge probabilistico (pensa como quant).

Testa 5 hipoteses sobre dados REAIS, com intervalo de confianca (Wilson) e
validacao OUT-OF-SAMPLE (treina nos 70% antigos, valida nos 30% recentes):

 #1 Edge por ativo / hora
 #2 Estado tecnico do sinal (tendencia, RSI, streak no momento do sinal)
 #3 Micro-estrutura do OTC (reversao/continuacao apos sequencias de cor) — independe do canal
 #4 Fade (apostar contra o sinal), geral e condicionado
 #5 Autocorrelacao (resultados andam em ondas? P(win|win anterior) vs P(win|loss))

Break-even = 54.1% (payout 85%). Edge real = taxa cujo CI-inferior > 54% E sobrevive no teste.
Salva tools/edge_resultado.json (lido pelo relatorio). Roda: py tools/edge_scanner.py
"""
import os
import re
import sys
import json
import math
import time
import requests
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import market
import indicators as ind

ROOT = os.path.dirname(os.path.dirname(__file__))
HIST = os.path.join(ROOT, ".tmp", "historico.json")
OUT = os.path.join(os.path.dirname(__file__), "edge_resultado.json")
BR = timezone(timedelta(hours=-3))
BREAKEVEN = 0.541

try:
    _m = json.load(open(os.path.join(os.path.dirname(__file__), "symbols_otc.json"), encoding="utf-8"))
    NAME2TICK = {k.replace("(OTC)", "").strip().upper(): v for k, v in _m.items()}
except Exception:
    NAME2TICK = {}

LINE = re.compile(r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ]+?)\s*-\s*(\d{1,2}:\d{2})\s*-\s*(PUT|CALL)\s*-*>\s*\**\s*(GAIN|WIN|LOSS|LOSE)", re.I)


def wilson(wins, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round((centre - half) * 100, 1), round((centre + half) * 100, 1))


def fetch_continuo(ticker, t0, t1):
    """Candles 1m de t0..t1 (ms), em blocos de 1000. Retorna dict time->candle."""
    out = {}
    cur = t0
    step = 1000 * 60000
    while cur < t1 and len(out) < 60000:
        try:
            r = requests.get(f"{market.API_URL}/aggregated-prices/prices",
                             headers={"api-key": market.API_KEY, "Origin": market.ORIGIN},
                             params={"slot": "default", "pair": ticker, "startTime": cur,
                                     "endTime": min(cur + step, t1), "type": "otc", "interval": "1m",
                                     "skip": 0, "limit": 1000}, timeout=20)
            arr = r.json()
            if not isinstance(arr, list) or not arr:
                cur += step
                continue
            for c in arr:
                out[c["time"]] = c
            cur = max(arr[-1]["time"] + 60000, cur + step)
        except Exception:
            cur += step
    return out


def colour(c):
    return 1 if c["closePrice"] > c["openPrice"] else (-1 if c["closePrice"] < c["openPrice"] else 0)


def win_dir(c, direction):  # direction 'BUY'/'SELL'
    cl = colour(c)
    if cl == 0:
        return None
    return cl == (1 if direction == "BUY" else -1)


def parse_sinais(msgs):
    s = {}
    for m in msgs:
        try:
            br = datetime.fromisoformat(m.get("date")).astimezone(BR)
        except Exception:
            continue
        for asset, hhmm, direc, chres in LINE.findall(m.get("text") or ""):
            tk = NAME2TICK.get(asset.strip().upper())
            if not tk:
                continue
            h, mi = map(int, hhmm.split(":"))
            entry = datetime(br.year, br.month, br.day, h, mi, tzinfo=BR)
            if entry > br + timedelta(minutes=15):
                entry -= timedelta(days=1)
            ts = int(entry.astimezone(timezone.utc).timestamp() * 1000)
            s[(tk, ts)] = "BUY" if direc.upper() == "CALL" else "SELL"
    return s


def taxa(wins, n):
    return round(100 * wins / n, 1) if n else None


def bloco_cond(registros, chave_fn):
    """win rate por bucket (train/test) p/ uma funcao de chave."""
    out = {}
    for split in ("train", "test"):
        sub = [r for r in registros if r["split"] == split]
        d = {}
        for r in sub:
            k = chave_fn(r)
            if k is None:
                continue
            d.setdefault(k, [0, 0])
            d[k][1] += 1
            if r["win"]:
                d[k][0] += 1
        out[split] = {str(k): {"wr": taxa(v[0], v[1]), "n": v[1], "ci": wilson(v[0], v[1])}
                      for k, v in d.items()}
    return out


def main():
    msgs = json.load(open(HIST, encoding="utf-8"))
    sinais = parse_sinais(msgs)
    print(f"Sinais: {len(sinais)}. Coletando candles continuos por ativo...")

    por_ticker = {}
    for (tk, ts) in sinais:
        por_ticker.setdefault(tk, []).append(ts)
    candles = {}
    for tk, tss in por_ticker.items():
        t0, t1 = min(tss) - 40 * 60000, max(tss) + 8 * 60000
        candles[tk] = fetch_continuo(tk, t0, t1)
        print(f"  {tk}: {len(candles[tk])} candles")

    # ---- monta registros de sinais (com indicadores e desfecho) ----
    registros = []
    for (tk, ts), direction in sorted(sinais.items(), key=lambda x: x[0][1]):
        cmap = candles.get(tk, {})
        main_c = cmap.get(ts)
        if not main_c:
            continue
        w = win_dir(main_c, direction)
        if w is None:
            continue
        pre = [cmap[ts - k * 60000] for k in range(25, 0, -1) if (ts - k * 60000) in cmap]
        analise = ind.analisar(
            [{"open": c["openPrice"], "close": c["closePrice"], "high": c["highPrice"], "low": c["lowPrice"]} for c in pre] +
            [{"open": main_c["openPrice"], "close": main_c["closePrice"], "high": main_c["highPrice"], "low": main_c["lowPrice"]}],
            direction) if len(pre) >= 22 else None
        registros.append({"tk": tk, "ts": ts, "dir": direction, "win": w,
                          "hora": datetime.fromtimestamp(ts / 1000, BR).hour,
                          "score": (analise or {}).get("score"),
                          "tend_ok": None if not analise else (analise.get("tendencia") == ("alta" if direction == "BUY" else "baixa")),
                          "rsi": (analise or {}).get("rsi"),
                          "gale1": win_dir(cmap.get(ts + 60000), direction) if cmap.get(ts + 60000) else None})
    n = len(registros)
    corte = int(n * 0.7)
    for i, r in enumerate(registros):
        r["split"] = "train" if i < corte else "test"
    print(f"Registros validos: {n} (train {corte} / test {n-corte})")

    wins_all = sum(1 for r in registros if r["win"])

    # #1 ativo / hora
    edge1_ativo = bloco_cond(registros, lambda r: r["tk"])
    edge1_hora = bloco_cond(registros, lambda r: f"{r['hora']:02d}h")
    # #2 estado tecnico
    edge2_tend = bloco_cond([r for r in registros if r["tend_ok"] is not None],
                            lambda r: "tendencia a favor" if r["tend_ok"] else "tendencia contra")
    def rsi_bucket(r):
        v = r["rsi"]
        if v is None:
            return None
        return "RSI<35" if v < 35 else ("RSI>65" if v > 65 else "RSI 35-65")
    edge2_rsi = bloco_cond(registros, rsi_bucket)
    # #4 fade (apostar contra): win = not win
    fade = {"geral": {}}
    for split in ("train", "test"):
        sub = [r for r in registros if r["split"] == split]
        w = sum(1 for r in sub if not r["win"])
        fade["geral"][split] = {"wr": taxa(w, len(sub)), "n": len(sub), "ci": wilson(w, len(sub))}
    # #5 autocorrelacao
    seq = [r["win"] for r in registros]
    after_win = [seq[i + 1] for i in range(len(seq) - 1) if seq[i]]
    after_loss = [seq[i + 1] for i in range(len(seq) - 1) if not seq[i]]
    auto = {
        "p_win_apos_win": {"wr": taxa(sum(after_win), len(after_win)), "n": len(after_win), "ci": wilson(sum(after_win), len(after_win))},
        "p_win_apos_loss": {"wr": taxa(sum(after_loss), len(after_loss)), "n": len(after_loss), "ci": wilson(sum(after_loss), len(after_loss))},
    }

    # #3 micro-estrutura: sobre TODOS os candles continuos, por streak de cor
    rev = {}  # k -> [reversoes, total] (pos i com streak k, olha i+1)
    cont_split = {}
    for tk, cmap in candles.items():
        times = sorted(cmap)
        cols = [colour(cmap[t]) for t in times]
        k = 0
        last = 0
        for i in range(len(cols) - 1):
            c = cols[i]
            if c == 0:
                k = 0; last = 0; continue
            if c == last:
                k += 1
            else:
                k = 1; last = c
            nxt = cols[i + 1]
            if nxt == 0:
                continue
            kk = min(k, 6)
            # split por posicao (70/30) p/ out-of-sample
            sp = "train" if i < len(cols) * 0.7 else "test"
            d = cont_split.setdefault(sp, {})
            d.setdefault(kk, [0, 0])
            d[kk][1] += 1
            if nxt != c:  # reverteu
                d[kk][0] += 1
    micro = {}
    for sp, d in cont_split.items():
        micro[sp] = {f"streak {kk}": {"reversao_wr": taxa(v[0], v[1]), "n": v[1], "ci": wilson(v[0], v[1])}
                     for kk, v in sorted(d.items())}

    resultado = {
        "n_sinais": n, "acerto_geral": taxa(wins_all, n), "breakeven": 54.1,
        "edge1_ativo": edge1_ativo, "edge1_hora": edge1_hora,
        "edge2_tendencia": edge2_tend, "edge2_rsi": edge2_rsi,
        "edge3_microestrutura": micro,
        "edge4_fade": fade, "edge5_autocorrelacao": auto,
    }
    # destaca candidatos: train CI-inf > 54 E test wr > 54
    candidatos = []
    def scan(nome, bloco):
        tr, te = bloco.get("train", {}), bloco.get("test", {})
        for k, v in tr.items():
            if v["ci"][0] > 54 and v["n"] >= 20:
                tw = te.get(k, {}).get("wr")
                candidatos.append({"hipotese": nome, "condicao": k, "train_wr": v["wr"],
                                   "train_ci_inf": v["ci"][0], "train_n": v["n"],
                                   "test_wr": tw, "sobrevive": (tw is not None and tw > 54)})
    scan("ativo", edge1_ativo); scan("hora", edge1_hora)
    scan("tendencia", edge2_tend); scan("rsi", edge2_rsi)
    scan("micro-estrutura", micro)
    resultado["candidatos"] = candidatos

    json.dump(resultado, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n=== CANDIDATOS A EDGE (train CI-inf>54% e n>=20) ===")
    print(json.dumps(candidatos, ensure_ascii=False, indent=2) if candidatos else "  NENHUM edge robusto encontrado.")
    print("\n#3 micro-estrutura (reversao por streak):")
    print(json.dumps(micro.get("train", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
