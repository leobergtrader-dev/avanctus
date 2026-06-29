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


def mensagem_diaria(r):
    """Monta o aviso DIDATICO (pra leigo) a partir do resultado do rebalance."""
    br = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    eq = r["equity"]; ret = r["retorno_%"]; alvo = r["posicoes_alvo"]; ordens = r["ordens"]
    L = []
    L.append(f"📊 *RELATORIO DIARIO - TRADE IA*  ({br:%d/%m/%Y})")
    L.append("")
    L.append(f"💼 Sua banca de TESTE: *${eq:.2f}*  ({'+' if ret >= 0 else ''}{ret}%)")
    L.append("_(É dinheiro FICTICIO. Estamos testando a estrategia ao vivo, SEM risco, antes de usar dinheiro de verdade.)_")
    L.append("")
    compras = [o for o in ordens if o["lado"] == "COMPRA"]
    vendas = [o for o in ordens if o["lado"] == "VENDA"]
    if not ordens and alvo == 0:
        L.append("📍 *Hoje a estrategia NAO comprou nada — ficou 100% em CAIXA (dinheiro parado).*")
        L.append("")
        L.append("👉 *Por que?* A nossa estrategia se chama MOMENTUM (tendencia). Ela so compra uma moeda quando o preco esta SUBINDO de forma consistente (em tendencia de alta). Hoje o mercado de cripto esta caindo ou de lado, entao ela preferiu *ficar de fora pra PROTEGER seu dinheiro*.")
        L.append("")
        L.append("📚 *Aula de hoje:* No mercado, *nao perder* e tao importante quanto ganhar. Ficar parado numa hora ruim evita prejuizo — e isso ja e uma vitoria. A estrategia tem paciencia: so entra quando ha vantagem real.")
    else:
        if compras:
            nomes = ", ".join(o["sym"].replace("USDT", "") for o in compras)
            L.append(f"🟢 *Hoje a estrategia COMPROU:* {nomes}")
            L.append("👉 *Por que?* Essas moedas entraram em *tendencia de alta* (comecaram a subir de forma firme). A estrategia compra pra 'pegar a onda' da subida.")
        if vendas:
            nomes = ", ".join(o["sym"].replace("USDT", "") for o in vendas)
            L.append(f"🔴 *Hoje a estrategia VENDEU / saiu de:* {nomes}")
            L.append("👉 *Por que?* Essas moedas *perderam a forca* (a alta acabou). A estrategia sai pra proteger o lucro/capital antes que cai mais.")
        L.append("")
        L.append(f"📍 Agora a carteira tem *{alvo} moeda(s)* compradas.")
        L.append("")
        L.append("📚 *Aula de hoje:* A estrategia segue a TENDENCIA — entra quando sobe, sai quando cai. Nao tenta adivinhar o fundo nem o topo; so acompanha o movimento. Disciplina, nao palpite.")
    L.append("")
    L.append("ℹ️ _Lembrete: isso e o 'forward-test' = teste ao vivo com dinheiro de mentira. So pensamos em dinheiro real depois de semanas provando que funciona — e comecando bem pouco._")
    return "\n".join(L)


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
