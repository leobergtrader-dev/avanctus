"""
estrategia_momentum.py — Gera a CARTEIRA-ALVO de hoje (long-only momentum validado) e
mantem o registro do FORWARD-TEST (paper trade ao vivo).

Estrategia validada: ensemble TSMOM N=[30,50,80,100], LONG-ONLY, com volatility targeting.
Para cada moeda: comprado (tamanho ~ alvo_vol/vol) se em tendencia de alta; senao, caixa.

Roda sob demanda (endpoint do painel). Salva snapshots em .tmp/forward_momentum.json
para construir a curva real do forward-test.
"""
import os, json, math, requests, datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
FWD = os.path.join(ROOT, ".tmp", "forward_momentum.json")
UNIVERSO = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "XRPUSDT",
            "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "DOTUSDT", "MATICUSDT"]
NS = [30, 50, 80, 100]
ALVO_VOL = 0.40
JANELA_VOL = 30
LEV_MAX = 3.0


def _daily(symbol, limit=160):
    try:
        r = requests.get("https://api.binance.com/api/v3/klines",
                         params={"symbol": symbol, "interval": "1d", "limit": limit}, timeout=15)
        return [(k[0], float(k[4])) for k in r.json()]
    except Exception:
        return []


def _std(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / n)


def carteira_hoje():
    itens = []
    for sym in UNIVERSO:
        s = _daily(sym)
        px = [p for _, p in s]
        if len(px) < max(NS) + JANELA_VOL + 2:
            continue
        sig = sum(1 if px[-1] > px[-1 - N] else -1 for N in NS) / len(NS)   # [-1,1]
        sig_long = max(sig, 0.0)
        rets = [px[i] / px[i - 1] - 1 for i in range(len(px) - JANELA_VOL, len(px))]
        vol = _std(rets) * math.sqrt(365)
        scale = min(ALVO_VOL / vol, LEV_MAX) if vol > 0 else 0
        pos = round(sig_long * scale, 2)
        itens.append({"coin": sym.replace("USDT", ""), "sym": sym,
                      "tendencia": "ALTA" if sig > 0 else ("MISTA" if sig == 0 else "BAIXA"),
                      "acao": "COMPRADO" if pos > 0 else "CAIXA",
                      "tamanho": pos, "preco": px[-1],
                      "vol_anual": round(vol * 100, 0)})
    comprados = [i for i in itens if i["tamanho"] > 0]
    return {
        "itens": sorted(itens, key=lambda x: -x["tamanho"]),
        "n_comprado": len(comprados),
        "n_total": len(itens),
        "exposicao_media": round(sum(i["tamanho"] for i in itens) / len(itens), 2) if itens else 0,
    }


def _load_fwd():
    try:
        return json.load(open(FWD, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def registrar_snapshot(carteira):
    """Salva 1 snapshot por dia (UTC): posicoes + precos. Para a curva do forward-test."""
    hoje = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    fwd = _load_fwd()
    fwd[hoje] = {i["sym"]: {"pos": i["tamanho"], "px": i["preco"]} for i in carteira["itens"]}
    os.makedirs(os.path.dirname(FWD), exist_ok=True)
    json.dump(fwd, open(FWD, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def forward_stats():
    """Curva real do forward-test a partir dos snapshots diarios."""
    fwd = _load_fwd()
    dias = sorted(fwd)
    if len(dias) < 2:
        return {"inicio": dias[0] if dias else None, "dias": len(dias),
                "retorno_total": None, "obs": "coletando (precisa de >=2 dias)"}
    eq = 1.0
    curva = []
    for k in range(1, len(dias)):
        ant, hoje = fwd[dias[k - 1]], fwd[dias[k]]
        rs = []
        for sym, a in ant.items():
            if sym in hoje and a["px"]:
                r = a["pos"] * (hoje[sym]["px"] / a["px"] - 1)
                rs.append(r)
        if rs:
            eq *= (1 + sum(rs) / len(rs))
        curva.append({"dia": dias[k], "eq": round(eq, 4)})
    return {"inicio": dias[0], "dias": len(dias),
            "retorno_total": round((eq - 1) * 100, 2), "curva": curva[-30:]}
