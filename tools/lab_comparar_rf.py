"""
lab_comparar_rf.py — Compara TODAS as estrategias com a renda fixa brasileira (CDI/LCI/LCA/CDB).
Detalhe-chave: cripto/forex rendem em DOLAR; B3 e a renda fixa rendem em REAL.
Pra comparar justo, converto os retornos em dolar para reais somando a desvalorizacao do real
(medida com dados reais do Yahoo). Mostra tabela + quanto vira R$10.000 em 5 anos.
"""
import os, datetime, requests

# --- renda fixa BR (aprox., meados de 2026; Selic ~15%) ---
CDI = 0.1475                 # CDI bruto a.a.
LCI_LCA = CDI * 0.92         # isento de IR, ~92% do CDI -> liquido
CDB_NET = CDI * 1.05 * (1 - 0.15)   # 105% CDI, menos IR 15% (resgate > 2 anos)
US_RF = 0.045               # juro 'sem risco' americano (T-bill ~4,5%)

# --- estrategias: (nome, cagr, moeda, sharpe, maxdd) ---
ESTRAT = [
    ("Cripto — Momentum",        0.217, "USD", 0.87, 37),
    ("Cripto — Buy&Hold",        0.476, "USD", 0.89, 84),
    ("Cripto — Grid (papel)",    0.00,  "USD", 0.0,  0),
    ("Forex — Carry Trade",      0.018, "USD", 0.30, 13),
    ("Forex — Momentum",        -0.014, "USD", -0.30, 16),
    ("Forex — Grid",             0.00,  "USD", 0.0,  0),
    ("B3 — IBOV Buy&Hold",       0.177, "BRL", 0.73, 47),
    ("B3 — Momentum",            0.019, "BRL", 0.21, 31),
]


def brl_deprec():
    """Desvalorizacao anualizada do real vs dolar (10 anos, Yahoo)."""
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/USDBRL=X",
                         params={"interval": "1mo", "range": "10y"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        cl = [c for c in r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
        anos = len(cl) / 12.0
        return (cl[-1] / cl[0]) ** (1 / anos) - 1
    except Exception as e:
        print("  (usando 8% de desvalorizacao padrao;", e, ")")
        return 0.08


def vira(cagr, anos=5, principal=10000):
    return principal * (1 + cagr) ** anos


def main():
    dep = brl_deprec()
    print(f"\nDesvalorizacao do real vs dolar (medida, 10a): {dep*100:.1f}% ao ano")
    print("=> Toda estrategia em DOLAR ganha esse tanto a mais quando vira real (historicamente).\n")

    print(f"{'RENDA FIXA (sem risco)':28} {'a.a.':>7} {'R$10k em 5a':>13}")
    for nome, taxa in [("CDI (100%)", CDI), ("LCI/LCA (isento IR)", LCI_LCA), ("CDB (liq. de IR)", CDB_NET)]:
        print(f"{nome:28} {taxa*100:>6.1f}% {vira(taxa):>12,.0f}")
    print()

    print(f"{'ESTRATEGIA':24} {'moeda':5} {'a.a.orig':>8} {'a.a.em R$':>9} {'R$10k/5a':>10} {'vs LCI':>7} {'risco(DD)':>9}")
    linhas = []
    for nome, cagr, moeda, sharpe, dd in ESTRAT:
        cagr_brl = (1 + cagr) * (1 + dep) - 1 if moeda == "USD" else cagr
        venc = "GANHA" if cagr_brl > LCI_LCA else "perde"
        linhas.append((nome, moeda, cagr, cagr_brl, sharpe, dd, venc))
        print(f"{nome:24} {moeda:5} {cagr*100:>7.1f}% {cagr_brl*100:>8.1f}% {vira(cagr_brl):>9,.0f} {venc:>7} {dd:>7}%")

    print("\n--- Regra rigorosa (paridade de juros) ---")
    print(f"Uma estrategia em DOLAR so vale mais que a renda fixa BR se o retorno em dolar")
    print(f"superar o juro sem risco americano (~{US_RF*100:.1f}%). Abaixo disso, o CDI/LCI ganha.")
    for nome, cagr, moeda, *_ in ESTRAT:
        if moeda == "USD":
            v = "VALE a pena" if cagr > US_RF else "NAO vale (renda fixa ganha)"
            print(f"  {nome:24} {cagr*100:>6.1f}% em USD  ->  {v}")


if __name__ == "__main__":
    main()
