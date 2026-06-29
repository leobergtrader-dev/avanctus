"""
painel.py — TRADE IA (crypto). Roda os forward-tests em PAPEL (Momentum + Grid),
rebalanceia 1x/dia automaticamente, avisa no WhatsApp (cada acao + resumo diario)
e serve o painel web. Sem nada de opcoes binarias.

Local: http://localhost:3000   |   Nuvem: Railway (mesmo codigo).
"""
import os
import sys
import time
import threading
from collections import deque
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(ROOT, ".env")
load_dotenv(ENV_PATH)

import estrategia_momentum
import executor_crypto
import executor_grid
import notify
from flask import Flask, jsonify, request, send_from_directory

WEB = os.path.join(ROOT, "painel_web")
LOG = deque(maxlen=200)


def emit(msg):
    linha = f"{datetime.now().strftime('%H:%M:%S')}  {msg}"
    LOG.append(linha)
    print(linha)


def envbool(k, d=False):
    return os.environ.get(k, str(d)).strip().lower() in ("1", "true", "yes", "sim")


app = Flask(__name__, static_folder=None)

PAINEL_USUARIO = os.environ.get("PAINEL_USUARIO", "admin").strip()
PAINEL_SENHA = os.environ.get("PAINEL_SENHA", "").strip()


@app.before_request
def _exige_senha():
    if not PAINEL_SENHA:
        return  # sem senha (uso local) -> acesso livre
    a = request.authorization
    if not a or a.username != PAINEL_USUARIO or a.password != PAINEL_SENHA:
        return ("Acesso restrito", 401, {"WWW-Authenticate": 'Basic realm="TRADE IA"'})


# ------------------------------------------------------------------ API
@app.get("/api/status")
def status():
    return jsonify({
        "sistema": "TRADE IA — crypto (forward-test em papel)",
        "notificar_acoes": envbool("NOTIFICAR_ACOES", True),
        "whatsapp_ok": bool(os.environ.get("BOTCONVERSA_WEBHOOK_URL", "").strip()
                            or os.environ.get("WHATS_APIKEY", "").strip()),
    })


@app.get("/api/log")
def log():
    return jsonify(list(LOG)[-80:][::-1])


@app.get("/api/estrategia")
def estrategia():
    try:
        c = estrategia_momentum.carteira_hoje()
        estrategia_momentum.registrar_snapshot(c)
        return jsonify({"carteira": c, "forward": estrategia_momentum.forward_stats()})
    except Exception as e:
        return jsonify({"erro": str(e)})


@app.post("/api/notify/test")
def notify_test():
    partes = []
    try:
        partes.append(executor_crypto.mensagem_diaria(executor_crypto.rebalancear(dry=True)))
    except Exception as e:
        partes.append(f"(momentum: nao consegui montar a previa: {e})")
    try:
        partes.append(executor_grid.mensagem_grid(executor_grid.rebalancear(dry=True)))
    except Exception as e:
        partes.append(f"(grid: nao consegui montar a previa: {e})")
    return jsonify(notify.enviar("\n\n———————————\n\n".join(partes)))


@app.post("/api/executor/run")
def executor_run():
    try:
        return jsonify(executor_crypto.rebalancear(dry=False))
    except Exception as e:
        return jsonify({"erro": str(e)})


@app.get("/api/executor")
def executor_state():
    try:
        st = executor_crypto.load_state()
        return jsonify({"cash": round(st.get("cash", 0), 2),
                        "hist": st.get("hist", [])[-60:],
                        "posicoes": {k: round(v, 6) for k, v in st.get("holdings", {}).items() if v}})
    except Exception as e:
        return jsonify({"erro": str(e)})


@app.get("/api/grid")
def grid_state():
    try:
        st = executor_grid.load_state() or {}
        comprados = sum(1 for h in st.get("holding", []) if h > 0)
        return jsonify({"cash": round(st.get("cash", executor_grid.CAPITAL0), 2),
                        "hist": st.get("hist", [])[-60:],
                        "niveis_comprados": comprados,
                        "recenters": st.get("recenters", 0)})
    except Exception as e:
        return jsonify({"erro": str(e)})


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/style.css")
def _css():
    return send_from_directory(WEB, "style.css")


@app.get("/app.js")
def _js():
    return send_from_directory(WEB, "app.js")


# ------------------------------------------------------------------ robô (forward-test diário)
def _auto_executor():
    """Roda o rebalance em PAPEL 1x por dia (forward-test automatico) das 2 estrategias."""
    ultimo = None
    grid_ativo_prev = None
    while True:
        try:
            hoje = datetime.now().strftime("%Y-%m-%d")
            if hoje != ultimo:
                partes = []
                # ----- MOMENTUM -----
                r = executor_crypto.rebalancear(dry=False)
                emit(f"momentum {hoje}: equity ${r['equity']} ({r['retorno_%']:+}%), {len(r['ordens'])} ordens")
                for o in r["ordens"]:                       # alerta por acao
                    moeda = o["sym"].replace("USDT", "")
                    if o["lado"] == "COMPRA":
                        notify.acao(f"🟢 *AÇÃO — Momentum COMPROU {moeda}* (~${o['valor']:.0f})\n_Essa moeda entrou em tendencia de alta; o robo entrou pra 'pegar a onda'._")
                    else:
                        notify.acao(f"🔴 *AÇÃO — Momentum VENDEU {moeda}* (~${o['valor']:.0f})\n_Essa moeda perdeu a forca; o robo saiu pra proteger o capital._")
                partes.append(executor_crypto.mensagem_diaria(r))
                # ----- GRID -----
                try:
                    rg = executor_grid.rebalancear(dry=False)
                    emit(f"grid {hoje}: equity ${rg['equity']} ({rg['retorno_%']:+}%), {rg['niveis_comprados']} degraus")
                    ativo = rg["niveis_comprados"] > 0
                    if grid_ativo_prev is not None and ativo != grid_ativo_prev:   # alerta por acao
                        if ativo:
                            notify.acao(f"🪜 *AÇÃO — Grid ACORDOU* (comprou em {rg['niveis_comprados']} degraus)\n_Mercado entrou em faixa lateral; o grid comecou a operar o vai-e-vem._")
                        else:
                            notify.acao("🪜 *AÇÃO — Grid voltou pra CAIXA* (liquidou tudo)\n_Mercado virou pra baixo; o grid pausou e protegeu o dinheiro._")
                    grid_ativo_prev = ativo
                    partes.append(executor_grid.mensagem_grid(rg))
                except Exception as e:
                    emit(f"grid erro: {e}")
                # ----- RESUMO DIARIO -----
                notify.enviar("\n\n———————————\n\n".join(partes))
                ultimo = hoje
        except Exception as e:
            emit(f"executor erro: {e}")
        time.sleep(3600)


if __name__ == "__main__":
    threading.Thread(target=_auto_executor, daemon=True).start()
    port = int(os.environ.get("PORT", 3000))
    print(f"\n  PAINEL TRADE IA (crypto) -> http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, threaded=True)
