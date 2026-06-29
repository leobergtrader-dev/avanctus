"""
executor_binance.py — Execucao REAL/TESTNET das 2 estrategias na Binance.
Cada estrategia tem orcamento e ledger proprios (.tmp/real_*.json), executa ordens
de verdade via binance_client e atualiza o estado pelos fills reais.

  momentum_real(): cesta de moedas, rebalance (rodar ~1x/dia).
  grid_real():     BTC, grid meio-termo com stop (rodar com frequencia, ex.: a cada 15 min).

Seguranca: comeca em TESTNET (BINANCE_TESTNET=true). So vira real trocando a chave.
"""
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(__file__))
import binance_client as bc
import estrategia_momentum as em

ROOT = os.path.dirname(os.path.dirname(__file__))
MOM_STATE = os.path.join(ROOT, ".tmp", "real_momentum.json")
GRID_STATE = os.path.join(ROOT, ".tmp", "real_grid.json")
MOM_BUDGET = float(os.environ.get("MOM_BUDGET", "1000"))
GRID_BUDGET = float(os.environ.get("GRID_BUDGET", "1000"))
MIN_NOTIONAL = 11.0
GSYM = "BTCUSDT"
N = 20
FAIXA = 0.25
STOP_PCT = float(os.environ.get("GRID_STOP_PCT", "0.10"))


def _load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(path, st):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(st, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _amb():
    return "TESTNET" if bc.TESTNET else "REAL"


# ----------------------------------------------------------- MOMENTUM
def momentum_real(dry=False):
    st = _load(MOM_STATE) or {"cash": MOM_BUDGET, "holdings": {}, "hist": []}
    cart = em.carteira_hoje()
    precos = {i["sym"]: i["preco"] for i in cart["itens"]}
    equity = st["cash"] + sum(st["holdings"].get(s, 0) * precos.get(s, 0) for s in precos)
    total_t = sum(i["tamanho"] for i in cart["itens"])
    fator = 1.0 / max(1.0, total_t)
    alvo = {i["sym"]: i["tamanho"] * fator * equity for i in cart["itens"]}
    ordens = []
    # vende primeiro (libera caixa), depois compra
    for sym in list(precos):
        atual = st["holdings"].get(sym, 0) * precos[sym]
        diff = alvo.get(sym, 0) - atual
        if diff < -MIN_NOTIONAL:
            ev = _vender_mom(st, sym, abs(diff), precos[sym], alvo.get(sym, 0), dry)
            if ev:
                ordens.append(ev)
    for sym in list(precos):
        atual = st["holdings"].get(sym, 0) * precos[sym]
        diff = alvo.get(sym, 0) - atual
        if diff > MIN_NOTIONAL:
            ev = _comprar_mom(st, sym, diff, dry)
            if ev:
                ordens.append(ev)
    equity2 = st["cash"] + sum(st["holdings"].get(s, 0) * precos.get(s, 0) for s in precos)
    if not dry:
        st["hist"].append({"quando": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
                           "equity": round(equity2, 2)})
        st["hist"] = st["hist"][-400:]
        _save(MOM_STATE, st)
    return {"ambiente": _amb(), "equity": round(equity2, 2), "cash": round(st["cash"], 2),
            "retorno_%": round((equity2 / MOM_BUDGET - 1) * 100, 2),
            "alvo_coins": cart["n_comprado"], "ordens": ordens, "dry": dry}


def _comprar_mom(st, sym, usdt, dry):
    if dry:
        return {"sym": sym, "lado": "COMPRA", "valor": round(usdt, 2), "dry": True}
    r = bc.comprar(sym, usdt)
    if r["ok"]:
        b = r["body"]
        st["holdings"][sym] = st["holdings"].get(sym, 0) + float(b["executedQty"])
        st["cash"] -= float(b["cummulativeQuoteQty"])
        return {"sym": sym, "lado": "COMPRA", "valor": round(float(b["cummulativeQuoteQty"]), 2)}
    return {"sym": sym, "lado": "COMPRA", "erro": str(r["body"])[:120]}


def _vender_mom(st, sym, usdt, preco, alvo_usdt, dry):
    held = st["holdings"].get(sym, 0)
    if held <= 0:
        return None
    if dry:
        return {"sym": sym, "lado": "VENDA", "valor": round(min(usdt, held * preco), 2), "dry": True}
    r = bc.vender(sym, held) if alvo_usdt < MIN_NOTIONAL else bc.vender_usdt(sym, usdt)
    if r["ok"]:
        b = r["body"]
        st["holdings"][sym] = max(0.0, held - float(b["executedQty"]))
        st["cash"] += float(b["cummulativeQuoteQty"])
        return {"sym": sym, "lado": "VENDA", "valor": round(float(b["cummulativeQuoteQty"]), 2)}
    return {"sym": sym, "lado": "VENDA", "erro": str(r["body"])[:120]}


# ----------------------------------------------------------- GRID
def _novo_grid(preco, cash):
    low, high = preco * (1 - FAIXA), preco * (1 + FAIXA)
    levels = [low + i * (high - low) / N for i in range(N + 1)]
    return {"low": low, "high": high, "levels": levels, "val": cash / N, "holding": [0.0] * N}


def _grid_vende_tudo(g, cash, dry, ordens, tag):
    for i in range(N):
        if g["holding"][i] > 0:
            if not dry:
                r = bc.vender(GSYM, g["holding"][i])
                if r["ok"]:
                    cash += float(r["body"]["cummulativeQuoteQty"])
            ordens.append({"lado": tag, "nivel": i})
            g["holding"][i] = 0.0
    return cash


def grid_real(dry=False):
    px = bc.preco(GSYM)
    if not px:
        raise RuntimeError("sem preco da Binance")
    st = _load(GRID_STATE)
    if st is None:
        g = _novo_grid(px, GRID_BUDGET)
        st = {"cash": GRID_BUDGET, "p0": px, "peak": GRID_BUDGET, "parado": False,
              "preco_stop": 0.0, "recenters": 0, "hist": []}
        st.update(g)
        if not dry:
            _save(GRID_STATE, st)
        return {"ambiente": _amb(), "equity": GRID_BUDGET, "cash": GRID_BUDGET, "retorno_%": 0.0,
                "niveis_comprados": 0, "preco": round(px, 2), "parado": False, "ordens": [], "dry": dry, "novo": True}

    g = {k: st[k] for k in ["low", "high", "levels", "val", "holding"]}
    cash, p0 = st["cash"], st["p0"]
    peak = st.get("peak", cash)
    parado = st.get("parado", False)
    preco_stop = st.get("preco_stop", 0.0)
    ordens = []
    eq = cash + sum(g["holding"][i] * px for i in range(N))
    peak = max(peak, eq)

    if parado:
        if px >= preco_stop:
            g = _novo_grid(px, cash); parado = False; peak = cash
    if not parado:
        if any(h > 0 for h in g["holding"]) and eq <= peak * (1 - STOP_PCT):
            cash = _grid_vende_tudo(g, cash, dry, ordens, "VENDA-STOP")
            parado = True; preco_stop = px; peak = cash
        elif px < g["low"] or px > g["high"]:
            cash = _grid_vende_tudo(g, cash, dry, ordens, "VENDA-RECENTRO")
            g = _novo_grid(px, cash); st["recenters"] = st.get("recenters", 0) + 1
        else:
            if px < p0:
                for i in range(N):
                    if px <= g["levels"][i] < p0 and g["holding"][i] == 0:
                        if dry:
                            ordens.append({"lado": "COMPRA", "nivel": i, "dry": True})
                        else:
                            r = bc.comprar(GSYM, g["val"])
                            if r["ok"]:
                                g["holding"][i] = float(r["body"]["executedQty"])
                                cash -= float(r["body"]["cummulativeQuoteQty"])
                                ordens.append({"lado": "COMPRA", "nivel": i})
            elif px > p0:
                for i in range(N):
                    if p0 < g["levels"][i + 1] <= px and g["holding"][i] > 0:
                        if dry:
                            ordens.append({"lado": "VENDA", "nivel": i, "dry": True})
                        else:
                            r = bc.vender(GSYM, g["holding"][i])
                            if r["ok"]:
                                cash += float(r["body"]["cummulativeQuoteQty"]); g["holding"][i] = 0.0
                                ordens.append({"lado": "VENDA", "nivel": i})
    p0 = px
    eq2 = cash + sum(g["holding"][i] * px for i in range(N))
    comprados = sum(1 for h in g["holding"] if h > 0)
    st.update(g)
    st["cash"], st["p0"], st["peak"], st["parado"], st["preco_stop"] = cash, p0, peak, parado, preco_stop
    if not dry:
        st["hist"].append({"quando": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
                           "equity": round(eq2, 2)})
        st["hist"] = st["hist"][-400:]
        _save(GRID_STATE, st)
    return {"ambiente": _amb(), "equity": round(eq2, 2), "cash": round(cash, 2),
            "retorno_%": round((eq2 / GRID_BUDGET - 1) * 100, 2), "niveis_comprados": comprados,
            "preco": round(px, 2), "parado": parado, "ordens": ordens, "dry": dry}


if __name__ == "__main__":
    print("=== MOMENTUM (dry) ===")
    print(momentum_real(dry=True))
    print("=== GRID (dry) ===")
    print(grid_real(dry=True))
