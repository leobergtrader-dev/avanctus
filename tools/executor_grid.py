"""
executor_grid.py — 2a estrategia em PAPEL: GRID (mercado lateral), versao MEIO-TERMO.
Opera o vai-e-vem nos DOIS sentidos (inclusive na baixa), com re-centragem da faixa,
MAS com um STOP de seguranca: se o patrimonio cair mais de GRID_STOP_PCT do topo, vende
tudo, vira caixa e espera o mercado virar pra voltar (evita o desastre do crash).

Roda BTC, banca-papel $1000, com taxa. Estado: .tmp/paper_grid.json.
Roda: py tools/executor_grid.py
"""
import os, sys, json, datetime, requests

ROOT = os.path.dirname(os.path.dirname(__file__))
STATE = os.path.join(ROOT, ".tmp", "paper_grid.json")
BINANCE = os.environ.get("BINANCE_BASE", "https://data-api.binance.vision")
SYM = "BTCUSDT"
CAPITAL0 = 1000.0
FEE = 0.001
N = 20            # degraus do grid
FAIXA = 0.25      # +/-25% em torno do preco central
STOP_PCT = float(os.environ.get("GRID_STOP_PCT", "0.10"))   # corta tudo se cair +10% do topo


def fetch_hourly(symbol, limit=1000):
    try:
        arr = requests.get(f"{BINANCE}/api/v3/klines",
                           params={"symbol": symbol, "interval": "1h", "limit": limit}, timeout=20).json()
        return [(k[0], float(k[4])) for k in arr] if isinstance(arr, list) else []
    except Exception:
        return []


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _novo_grid(preco, cash):
    low, high = preco * (1 - FAIXA), preco * (1 + FAIXA)
    levels = [low + i * (high - low) / N for i in range(N + 1)]
    qty = [(cash / N) / levels[i] for i in range(N)]
    return {"low": low, "high": high, "levels": levels, "qty": qty, "holding": [0.0] * N}


def _liquida(g, cash, p):
    for i in range(N):
        if g["holding"][i] > 0:
            cash += g["holding"][i] * p * (1 - FEE)
            g["holding"][i] = 0.0
    return cash


def rebalancear(dry=False):
    serie = fetch_hourly(SYM)
    if len(serie) < 5:
        raise RuntimeError("sem dados suficientes da Binance")
    precos = [p for _, p in serie]

    st = load_state()
    if st is None:
        g = _novo_grid(precos[-1], CAPITAL0)
        st = {"cash": CAPITAL0, "p0": precos[-1], "last_ts": serie[-1][0], "recenters": 0,
              "peak": CAPITAL0, "parado": False, "preco_stop": 0.0, "hist": []}
        st.update(g)
    else:
        g = {"low": st["low"], "high": st["high"], "levels": st["levels"],
             "qty": st["qty"], "holding": st["holding"]}
        cash, p0 = st["cash"], st["p0"]
        peak = st.get("peak", cash + sum(g["holding"][i] * st.get("p0", precos[-1]) for i in range(N)))
        parado = st.get("parado", False)
        preco_stop = st.get("preco_stop", 0.0)
        for ts, p1 in serie:
            if ts <= st["last_ts"]:
                continue
            eq = cash + sum(g["holding"][i] * p1 for i in range(N))
            peak = max(peak, eq)
            # se parado pelo stop: espera o preco recuperar pra retomar
            if parado:
                if p1 >= preco_stop:
                    g = _novo_grid(p1, cash); parado = False; p0 = p1; peak = cash
                else:
                    p0 = p1
                    continue
            # STOP por queda do patrimonio
            if any(h > 0 for h in g["holding"]) and eq <= peak * (1 - STOP_PCT):
                cash = _liquida(g, cash, p1)
                parado = True; preco_stop = p1; p0 = p1; peak = cash
                continue
            # saiu da faixa -> liquida e re-centra (segue o preco, pra cima ou pra baixo)
            if p1 < g["low"] or p1 > g["high"]:
                cash = _liquida(g, cash, p1)
                g = _novo_grid(p1, cash); st["recenters"] += 1; p0 = p1
                continue
            # grid normal — opera nos DOIS sentidos (sem filtro de tendencia)
            if p1 < p0:
                for i in range(N):
                    if p1 <= g["levels"][i] < p0 and g["holding"][i] == 0:
                        cash -= g["qty"][i] * g["levels"][i] * (1 + FEE); g["holding"][i] = g["qty"][i]
            elif p1 > p0:
                for i in range(N):
                    if p0 < g["levels"][i + 1] <= p1 and g["holding"][i] > 0:
                        cash += g["holding"][i] * g["levels"][i + 1] * (1 - FEE); g["holding"][i] = 0.0
            p0 = p1
        st["cash"], st["p0"], st["last_ts"] = cash, p0, serie[-1][0]
        st["peak"], st["parado"], st["preco_stop"] = peak, parado, preco_stop
        st.update(g)

    equity = st["cash"] + sum(st["holding"][i] * precos[-1] for i in range(N))
    comprados = sum(1 for h in st["holding"] if h > 0)
    snap = {"quando": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
            "equity": round(equity, 2), "cash": round(st["cash"], 2), "niveis": comprados}
    if not dry:
        st["hist"].append(snap)
        st["hist"] = st["hist"][-400:]
        save_state(st)
    return {"equity": round(equity, 2), "retorno_%": round((equity / CAPITAL0 - 1) * 100, 2),
            "cash": round(st["cash"], 2), "niveis_comprados": comprados,
            "preco": round(precos[-1], 2), "recenters": st.get("recenters", 0),
            "parado": st.get("parado", False), "stop_pct": round(STOP_PCT * 100), "dry": dry}


def mensagem_grid(r):
    """Resumo didatico da 2a estrategia (grid meio-termo)."""
    L = []
    L.append("🪜 *2a ESTRATEGIA: GRID (opera nos 2 sentidos, com stop)* — em papel")
    L.append(f"💼 Banca de teste: *${r['equity']:.2f}*  ({'+' if r['retorno_%'] >= 0 else ''}{r['retorno_%']}%)   | BTC ${r['preco']:.0f}")
    if r.get("parado"):
        L.append(f"🛑 *PAROU pelo stop* (patrimonio caiu mais de {r['stop_pct']}%) — vendeu tudo e espera o mercado virar pra voltar.")
    elif r["niveis_comprados"] > 0:
        L.append(f"📍 Comprado em *{r['niveis_comprados']} de {N} degraus* — operando o vai-e-vem (compra nas quedas, vende nos repiques).")
    else:
        L.append("📍 Sem posicoes no momento — esperando o preco cruzar os degraus.")
    L.append(f"_(Versao meio-termo: opera tambem na baixa, mas corta tudo se cair mais de {r['stop_pct']}% — pra nunca virar desastre.)_")
    return "\n".join(L)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    r = rebalancear(dry=a.dry)
    estado = "PARADO (stop)" if r["parado"] else "operando"
    print(f"{'[DRY] ' if a.dry else ''}GRID papel ({estado}): ${r['equity']} ({r['retorno_%']:+}%) | caixa ${r['cash']} | "
          f"degraus {r['niveis_comprados']}/{N} | BTC ${r['preco']} | recentragens {r['recenters']} | stop {r['stop_pct']}%")


if __name__ == "__main__":
    main()
