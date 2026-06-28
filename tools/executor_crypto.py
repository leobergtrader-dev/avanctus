"""
executor_crypto.py — Executor do momentum crypto. Comeca em PAPEL (carteira simulada, sem risco,
sem API key). Todo dia: le a carteira-alvo (estrategia_momentum) e rebalanceia a carteira-papel
aos pesos-alvo (spot, sem alavancagem), com taxa. Guarda a curva de patrimonio.

Depois e so trocar a "execucao em papel" por ordens reais (Binance testnet -> real).
Estado em .tmp/paper_crypto.json. Roda: py tools/executor_crypto.py
"""
import os, sys, json, datetime

sys.path.insert(0, os.path.dirname(__file__))
import estrategia_momentum as em

ROOT = os.path.dirname(os.path.dirname(__file__))
STATE = os.path.join(ROOT, ".tmp", "paper_crypto.json")
CAPITAL0 = 1000.0      # banca-papel inicial (USDT ficticios)
FEE = 0.001
MIN_NOTIONAL = 10.0


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"cash": CAPITAL0, "holdings": {}, "hist": []}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def rebalancear(dry=False):
    st = load_state()
    cart = em.carteira_hoje()
    precos = {i["sym"]: i["preco"] for i in cart["itens"]}
    # patrimonio atual
    equity = st["cash"] + sum(st["holdings"].get(s, 0) * precos.get(s, 0) for s in precos)
    # pesos-alvo (normaliza p/ nao alavancar: soma <= 1, resto caixa)
    total_t = sum(i["tamanho"] for i in cart["itens"])
    fator = 1.0 / max(1.0, total_t)
    alvo = {i["sym"]: i["tamanho"] * fator * equity for i in cart["itens"]}

    ordens = []
    for sym, px in precos.items():
        if px <= 0:
            continue
        atual = st["holdings"].get(sym, 0) * px
        diff = alvo.get(sym, 0) - atual
        if abs(diff) < MIN_NOTIONAL:
            continue
        qty = diff / px
        ordens.append({"sym": sym, "lado": "COMPRA" if qty > 0 else "VENDA",
                       "qtd": round(abs(qty), 6), "valor": round(abs(diff), 2), "preco": px})
        if not dry:
            st["cash"] -= diff + abs(diff) * FEE         # paga e taxa
            st["holdings"][sym] = st["holdings"].get(sym, 0) + qty

    equity_final = st["cash"] + sum(st["holdings"].get(s, 0) * precos.get(s, 0) for s in precos)
    comprados = sum(1 for s in st["holdings"] if st["holdings"][s] * precos.get(s, 0) > MIN_NOTIONAL)
    snap = {"quando": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
            "equity": round(equity_final, 2), "cash": round(st["cash"], 2),
            "posicoes": comprados, "ordens": len(ordens)}
    if not dry:
        st["hist"].append(snap)
        st["hist"] = st["hist"][-400:]
        save_state(st)
    return {"equity": round(equity_final, 2), "retorno_%": round((equity_final / CAPITAL0 - 1) * 100, 2),
            "cash": round(st["cash"], 2), "posicoes_alvo": cart["n_comprado"],
            "ordens": ordens, "dry": dry}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="so mostra as ordens, nao executa")
    a = ap.parse_args()
    r = rebalancear(dry=a.dry)
    print(f"{'[DRY-RUN] ' if a.dry else ''}Patrimonio-papel: ${r['equity']} ({r['retorno_%']:+}%) | "
          f"caixa ${r['cash']} | alvo comprado {r['posicoes_alvo']} coins")
    if r["ordens"]:
        print("Ordens:")
        for o in r["ordens"]:
            print(f"  {o['lado']:7} {o['sym']:10} ${o['valor']:>8} @ {o['preco']}")
    else:
        print("Sem ordens (ja na carteira-alvo, ou tudo em caixa).")


if __name__ == "__main__":
    main()
