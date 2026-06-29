"""
painel.py — Aplicativo unico: roda o ROBO + serve o PAINEL WEB.

Abra http://localhost:3000 e controle tudo por botoes:
 - Ligar/Desligar o robo (Telegram -> ordem na Avanctus, conta DEMO)
 - Saldo, PnL do dia, edge-gate, validade do login
 - Operacoes ao vivo + estatisticas
 - Editar a estrategia (valor, stops, horarios, gale)

Roda local agora; o mesmo codigo sobe pra um VPS depois (24h).
"""

import os
import sys
import csv
import json
import time
import asyncio
import threading
from collections import deque
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(ROOT, ".env")
load_dotenv(ENV_PATH)

import avanctus_client as ac
from signal_parser import parse_signal
from risk import RiskManager
import market
import indicators
import ai as ai_mod
import analytics
import estrategia_momentum
import executor_crypto
import notify
from flask import Flask, jsonify, request, send_from_directory
from telethon import TelegramClient, events
from telethon.sessions import StringSession

CSV = os.path.join(ROOT, ".tmp", "operacoes.csv")
ANALISES = os.path.join(ROOT, ".tmp", "analises.csv")
STOP_FILE = os.path.join(ROOT, ".tmp", "STOP")
WEB = os.path.join(ROOT, "painel_web")

rm = RiskManager()


def reload_config():
    """Recarrega .env e recria o gestor de risco (apos editar config)."""
    global rm
    load_dotenv(ENV_PATH, override=True)
    rm = RiskManager()


def envbool(k, d=False):
    return os.environ.get(k, str(d)).strip().lower() in ("1", "true", "yes", "sim")


# ------------------------------------------------------------------ engine
class Engine:
    def __init__(self):
        self.thread = None
        self.loop = None
        self.client = None
        self.running = False
        self.canal = None
        self.log = deque(maxlen=400)
        self.busy = threading.Lock()
        self.halt = False

    def emit(self, msg):
        linha = f"{datetime.now().strftime('%H:%M:%S')}  {msg}"
        self.log.append(linha)
        print(linha)

    def start(self):
        if self.running:
            return
        self.halt = False
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.client and self.loop:
            try:
                asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
            except Exception:
                pass
        self.emit("Robo desligado.")

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop
        try:
            loop.run_until_complete(self._main())
        except Exception as e:
            self.emit(f"ERRO no robo: {e}")
        finally:
            self.running = False

    async def _main(self):
        api_id = int(os.environ["TELEGRAM_API_ID"])
        api_hash = os.environ["TELEGRAM_API_HASH"]
        session = os.environ.get("TELEGRAM_SESSION", "").strip()
        grupo = int(os.environ["TELEGRAM_GRUPO"])
        self.client = TelegramClient(StringSession(session), api_id, api_hash)
        await self.client.connect()
        if not await self.client.is_user_authorized():
            self.emit("Sessao do Telegram invalida. Rode telegram_login.py.")
            return
        await self.client.get_dialogs()
        ent = await self.client.get_entity(grupo)
        self.canal = getattr(ent, "title", str(grupo))
        self.emit(f"Conectado ao canal: {self.canal}. Aguardando sinais...")

        @self.client.on(events.NewMessage(chats=ent))
        async def handler(event):
            sig = parse_signal(event.message.text or "")
            if not sig:
                return
            self.emit(f"SINAL: {sig['ativo_texto']} {sig['direcao']} entrada {sig['horario_entrada']}")
            threading.Thread(target=self.run_sequence, args=(sig,), daemon=True).start()

        await self.client.run_until_disconnected()

    def run_sequence(self, sig):
        if envbool("ONE_AT_A_TIME", True) and not self.busy.acquire(blocking=False):
            self.emit("  (ja ha uma operacao em andamento; sinal ignorado)")
            return
        try:
            if self.halt:
                return
            ok, motivo = rm.pode_operar(sig)
            if not ok:
                self.emit(f"  (ignorado: {motivo})")
                return
            conta_demo = envbool("CONTA_DEMO", True)
            if not conta_demo:
                n, wr, liberado = rm.edge_status()
                if not liberado:
                    self.emit(f"  (REAL bloqueado pelo edge-gate: amostra {n})")
                    return
            amount = rm.tamanho()
            if amount <= 0:
                self.emit("  (sizing=0: sem vantagem medida; ignorado)")
                return

            symbol = sig["ativo_ticker"]
            direction = sig["lado_api"]
            mins = int(sig["expiracao_min"] or 1)
            close_type = f"{mins:02d}:00"

            if sig.get("horario_entrada"):
                h, m = map(int, sig["horario_entrada"].split(":"))
                alvo = datetime.now().replace(hour=h, minute=m, second=1, microsecond=0)
                wait = (alvo - datetime.now()).total_seconds()
                if wait < -45:
                    self.emit(f"  (sinal vencido {sig['horario_entrada']}; ignorado)")
                    return
                if wait > 0:
                    self.emit(f"  aguardando ate {sig['horario_entrada']} ({int(wait)}s)...")
                    time.sleep(wait)

            # --- Filtro hibrido (analise tecnica + IA) — MODO SOMBRA por padrao ---
            analise = None
            try:
                candles = market.get_candles(symbol, limit=40)
                analise = indicators.analisar(candles, direction)
                if analise.get("score") is not None:
                    self.emit(f"  analise: score {analise['score']} ({analise['favor']}/{analise['total']}) "
                              f"tend {analise['tendencia']} RSI {analise['rsi']}")
                    expl = ai_mod.explain(sig, analise, candles)
                    if expl:
                        self.emit(f"  IA: {expl}")
                    _log_analise([datetime.now().isoformat(timespec="seconds"), symbol, direction,
                                  sig.get("horario_entrada"), analise.get("score"), analise.get("favor"),
                                  analise.get("total"), analise.get("tendencia"), analise.get("rsi"),
                                  analise.get("streak"), " | ".join(analise.get("razoes", []))])
            except Exception as e:
                self.emit(f"  (analise indisponivel: {e})")

            if envbool("FILTRO_ATIVO", False) and analise and analise.get("score") is not None:
                limiar = float(os.environ.get("LIMIAR_CONFIANCA", "0.5"))
                if analise["score"] < limiar:
                    self.emit(f"  >> FILTRO bloqueou: score {analise['score']} < {limiar}; sinal pulado")
                    return

            use_gale = envbool("USE_GALE", False)
            max_gale = int(float(os.environ.get("MAX_GALE", "2")))
            gale_factor = float(os.environ.get("GALE_FACTOR", "2"))
            n_gale = min(len(sig.get("gales") or []), max_gale) if use_gale else 0

            for level in range(n_gale + 1):
                if self.halt or os.path.exists(STOP_FILE):
                    self.emit("  (STOP ativo; interrompendo)")
                    break
                b0 = ac.demo_balance() if conta_demo else ac.real_balance()
                tag = "ENTRADA" if level == 0 else f"GALE {level}"
                self.emit(f"  [{tag}] {symbol} {direction} ${amount:g} | saldo {b0}")
                res = ac.open_trade(symbol, amount, direction, is_demo=conta_demo, close_type=close_type)
                if not res["ok"]:
                    self.emit(f"  ORDEM REJEITADA {res['status']}: {json.dumps(res['body'], ensure_ascii=False)[:150]}")
                    if res["status"] == 401:
                        self.halt = True
                        self.emit("  >>> Falha de login. Verifique a senha no .env. <<<")
                    break
                body = res["body"] if isinstance(res["body"], dict) else {}
                close_ms = body.get("closeTime")
                during = (b0 or 0) - amount
                if close_ms:
                    w = close_ms / 1000 - time.time() + 3
                    if w > 0:
                        time.sleep(w)
                else:
                    time.sleep(mins * 60 + 3)
                b1 = during
                for _ in range(9):
                    cur = ac.demo_balance() if conta_demo else ac.real_balance()
                    if cur is not None:
                        b1 = cur
                        if cur > during + 0.001:
                            break
                    time.sleep(3)
                diff = (b1 or 0) - (b0 or 0)
                result = "WIN" if diff > 0.001 else ("DRAW" if diff > -0.001 else "LOSS")
                self.emit(f"    -> {result} ({diff:+.2f}) | saldo {b1}")
                _log_csv([datetime.now().isoformat(timespec="seconds"), symbol, direction,
                          amount, tag, result, round(diff, 2), b1])
                if result != "LOSS":
                    break
                amount = round(amount * gale_factor, 2)
        finally:
            if envbool("ONE_AT_A_TIME", True):
                self.busy.release()


def _log_csv(row):
    os.makedirs(os.path.dirname(CSV), exist_ok=True)
    novo = not os.path.exists(CSV)
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["quando", "ativo", "direcao", "valor", "nivel", "resultado", "pnl", "saldo_depois"])
        w.writerow(row)


def _log_analise(row):
    os.makedirs(os.path.dirname(ANALISES), exist_ok=True)
    novo = not os.path.exists(ANALISES)
    with open(ANALISES, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["quando", "ativo", "direcao", "horario_entrada", "score",
                        "favor", "total", "tendencia", "rsi", "streak", "razoes"])
        w.writerow(row)


engine = Engine()

# ------------------------------------------------------------------ web
app = Flask(__name__, static_folder=None)

# Protecao por senha (obrigatoria quando publicado). Local sem senha = livre.
PAINEL_USUARIO = os.environ.get("PAINEL_USUARIO", "admin").strip()
PAINEL_SENHA = os.environ.get("PAINEL_SENHA", "").strip()


@app.before_request
def _exige_senha():
    if not PAINEL_SENHA:
        return  # sem senha definida (uso local) -> acesso livre
    a = request.authorization
    if not a or a.username != PAINEL_USUARIO or a.password != PAINEL_SENHA:
        return ("Acesso restrito", 401, {"WWW-Authenticate": 'Basic realm="TRADE IA"'})

CONFIG_KEYS = ["CONTA_DEMO", "ENTRY_AMOUNT", "USE_GALE", "MAX_GALE", "GALE_FACTOR",
               "HORARIOS_PERMITIDOS", "STOP_WIN_DIA", "STOP_LOSS_DIA", "STOP_LOSS_SEMANA",
               "MAX_PERDAS_SEGUIDAS", "DEGRAD_JANELA", "SIZING", "MAX_TRADES_DAY"]


def _jwt_validade():
    try:
        token = ac.get_bearer()
        exp, _ = ac._decode(token)
        return datetime.fromtimestamp(exp).strftime("%d/%m/%Y %H:%M") if exp else None
    except Exception:
        return None


@app.get("/api/status")
def status():
    try:
        demo = ac.demo_balance()
        real = ac.real_balance()
        login_ok = True
    except Exception as e:
        demo = real = None
        login_ok = False
        engine.emit(f"(status) login/saldo indisponivel: {e}")
    return jsonify({
        "robo_ligado": engine.running,
        "canal": engine.canal,
        "login_ok": login_ok,
        "jwt_validade": _jwt_validade() if login_ok else None,
        "saldo_demo": demo,
        "saldo_real": real,
        "conta": "DEMO" if envbool("CONTA_DEMO", True) else "REAL",
        "risco": rm.resumo(),
    })


@app.get("/api/operacoes")
def operacoes():
    if not os.path.exists(CSV):
        return jsonify([])
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    return jsonify(rows[-40:][::-1])


@app.get("/api/log")
def log():
    return jsonify(list(engine.log)[-80:][::-1])


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
    return jsonify(notify.whatsapp("TRADE IA: teste de notificacao no WhatsApp funcionou! 🚀"))


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


@app.get("/api/relatorio")
def relatorio():
    base = float(os.environ.get("ENTRY_AMOUNT", "25"))
    try:
        return jsonify(analytics.relatorio(CSV, ANALISES, base=base))
    except Exception as e:
        return jsonify({"erro": str(e)})


@app.get("/api/config")
def get_config():
    return jsonify({k: os.environ.get(k, "") for k in CONFIG_KEYS})


@app.post("/api/config")
def set_config():
    updates = request.get_json(force=True) or {}
    lines = open(ENV_PATH, encoding="utf-8").read().splitlines()
    keys = {k: str(v) for k, v in updates.items() if k in CONFIG_KEYS}
    seen = set()
    for i, ln in enumerate(lines):
        if "=" in ln and not ln.strip().startswith("#"):
            k = ln.split("=", 1)[0].strip()
            if k in keys:
                lines[i] = f"{k}={keys[k]}"
                seen.add(k)
    for k, v in keys.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    open(ENV_PATH, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    reload_config()
    return jsonify({"ok": True})


@app.post("/api/robo/<acao>")
def robo(acao):
    if acao == "ligar":
        engine.start()
    elif acao == "desligar":
        engine.stop()
    elif acao == "panico":
        open(STOP_FILE, "w").close()
        engine.halt = True
        engine.stop()
    return jsonify({"ok": True, "ligado": engine.running})


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/style.css")
def _css():
    return send_from_directory(WEB, "style.css")


@app.get("/app.js")
def _js():
    return send_from_directory(WEB, "app.js")


def _auto_executor():
    """Roda o rebalance em PAPEL 1x por dia (forward-test automatico)."""
    ultimo = None
    while True:
        try:
            hoje = datetime.now().strftime("%Y-%m-%d")
            if hoje != ultimo:
                r = executor_crypto.rebalancear(dry=False)
                engine.emit(f"[executor papel] rebalance {hoje}: equity ${r['equity']} ({r['retorno_%']:+}%), {len(r['ordens'])} ordens")
                acao = f"{len(r['ordens'])} ordens" if r["ordens"] else "em caixa (sem operar)"
                notify.whatsapp(f"📊 TRADE IA {hoje}\nForward-test momentum: ${r['equity']} ({r['retorno_%']:+}%)\nHoje: {acao} | alvo {r['posicoes_alvo']} coins")
                ultimo = hoje
        except Exception as e:
            engine.emit(f"[executor papel] erro: {e}")
        time.sleep(3600)


if __name__ == "__main__":
    threading.Thread(target=_auto_executor, daemon=True).start()
    port = int(os.environ.get("PORT", 3000))
    print(f"\n  PAINEL TRADE IA -> http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, threaded=True)
