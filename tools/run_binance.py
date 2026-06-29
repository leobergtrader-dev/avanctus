"""
run_binance.py — Roda as estrategias na Binance a partir da SUA maquina
(a nuvem e bloqueada pela Binance; sua maquina nao). Deixe a janela aberta.

Grid: a cada 20 min (pega oscilacao). Momentum: 1x/dia.
Ambiente vem do .env (BINANCE_TESTNET=true = fake; false = real).
"""
import os, sys, time, datetime
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

import executor_binance as ex
import notify

AMB = "TESTNET (dinheiro fake)" if ex.bc.TESTNET else "REAL ($$$)"


def agora():
    return datetime.datetime.now().strftime("%H:%M:%S")


def main():
    print("=" * 56)
    print(f"  EXECUTOR BINANCE — ambiente: {AMB}")
    print("  Deixe esta janela ABERTA. Ctrl+C para parar.")
    print("=" * 56)
    # checa conexao
    c = ex.bc.conta()
    if not c["ok"]:
        print(f"[ERRO] nao conectou na Binance: {c.get('erro')}")
        return
    print(f"{agora()} conectado. USDT: {c['saldos'].get('USDT', 0)}")
    ultimo_mom = None
    while True:
        try:
            rg = ex.grid_real(dry=False)
            est = "PARADO(stop)" if rg.get("parado") else "ok"
            if rg.get("ordens"):
                print(f"{agora()} GRID: {len(rg['ordens'])} ordens | equity ${rg['equity']} | BTC ${rg['preco']}")
                for o in rg["ordens"]:
                    notify.acao(f"🪜 *AÇÃO Grid ({rg['ambiente']})* — {o['lado']} degrau {o.get('nivel','?')}\nBTC ${rg['preco']:.0f} | banca ${rg['equity']}")
            else:
                print(f"{agora()} grid {est}: equity ${rg['equity']} | BTC ${rg['preco']} | degraus {rg['niveis_comprados']}/20")

            hoje = datetime.datetime.now().strftime("%Y-%m-%d")
            if hoje != ultimo_mom:
                rm = ex.momentum_real(dry=False)
                print(f"{agora()} MOMENTUM: {len(rm['ordens'])} ordens | equity ${rm['equity']} | alvo {rm['alvo_coins']} coins")
                for o in rm["ordens"]:
                    if "erro" not in o:
                        notify.acao(f"🌊 *AÇÃO Momentum ({rm['ambiente']})* — {o['lado']} {o['sym'].replace('USDT','')} (~${o.get('valor',0)})")
                ultimo_mom = hoje
        except Exception as e:
            print(f"{agora()} erro: {e}")
        time.sleep(1200)  # 20 min


if __name__ == "__main__":
    main()
