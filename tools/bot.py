"""
bot.py — Robo executor (Layer 2/3): Telegram -> parser -> estrategia -> ordem na Avanctus.

Fluxo: ouve o canal -> parseia o sinal -> agenda a entrada no horario -> abre na DEMO ->
detecta WIN/LOSS pelo SALDO -> se LOSS, faz GALE ate o limite -> registra tudo.

SEGURANCA:
 - Conta DEMO por padrao (real exige CONTA_DEMO=false E REAL_TRADING_ENABLED=yes).
 - Uma operacao por vez (ONE_AT_A_TIME).
 - Limite diario de trades (MAX_TRADES_DAY).
 - KILL SWITCH: crie um arquivo .tmp/STOP (ou Ctrl+C) para parar de abrir ordens.
"""

import os
import sys
import json
import csv
import time
import threading
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import avanctus_client as ac
from signal_parser import parse_signal
from risk import RiskManager
from telethon import TelegramClient, events
from telethon.sessions import StringSession


def envbool(k, d=False):
    return os.environ.get(k, str(d)).strip().lower() in ("1", "true", "yes", "sim")


# ----- Config (do .env) -----
CONTA_DEMO = envbool("CONTA_DEMO", True)
ENTRY = float(os.environ.get("ENTRY_AMOUNT", "25"))
USE_GALE = envbool("USE_GALE", True)
GALE_FACTOR = float(os.environ.get("GALE_FACTOR", "2"))
MAX_GALE = int(os.environ.get("MAX_GALE", "2"))
MAX_TRADES_DAY = int(os.environ.get("MAX_TRADES_DAY", "60"))
ONE_AT_A_TIME = envbool("ONE_AT_A_TIME", True)

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION = os.environ.get("TELEGRAM_SESSION", "").strip()
GRUPO = int(os.environ["TELEGRAM_GRUPO"])

ROOT = os.path.dirname(os.path.dirname(__file__))
STOP_FILE = os.path.join(ROOT, ".tmp", "STOP")
LOG_CSV = os.path.join(ROOT, ".tmp", "operacoes.csv")

busy = threading.Lock()
state = {"halt": False}
rm = RiskManager()


def stop_requested():
    return state["halt"] or os.path.exists(STOP_FILE)


def saldo():
    try:
        return ac.demo_balance() if CONTA_DEMO else None
    except Exception as e:
        print("  (erro ao ler saldo:", e, ")")
        return None


def log_op(row):
    novo = not os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["quando", "ativo", "direcao", "valor", "nivel", "resultado", "pnl", "saldo_depois"])
        w.writerow(row)


def alvo_entrada(hhmm):
    now = datetime.now()
    h, m = map(int, hhmm.split(":"))
    return now.replace(hour=h, minute=m, second=1, microsecond=0)


def run_sequence(sig):
    if ONE_AT_A_TIME and not busy.acquire(blocking=False):
        print("  (ja ha uma operacao em andamento; sinal ignorado)")
        return
    try:
        if state["halt"]:
            print("  (robo em HALT; reinicie apos resolver)")
            return
        ok, motivo = rm.pode_operar(sig)
        if not ok:
            print(f"  (sinal ignorado: {motivo})")
            return
        if not CONTA_DEMO:
            n, wr, liberado = rm.edge_status()
            if not liberado:
                wrtxt = f"{wr*100:.0f}%" if wr is not None else "s/dados"
                print(f"  (REAL bloqueado pelo edge-gate: amostra {n}, acerto {wrtxt}; precisa demo validada)")
                return

        amount = rm.tamanho()
        if amount <= 0:
            print("  (sizing Kelly=0: sem vantagem medida; sinal ignorado)")
            return

        symbol = sig["ativo_ticker"]
        direction = sig["lado_api"]
        mins = int(sig["expiracao_min"] or 1)
        close_type = f"{mins:02d}:00"

        # Agenda para o horario de entrada do sinal
        if sig.get("horario_entrada"):
            alvo = alvo_entrada(sig["horario_entrada"])
            wait = (alvo - datetime.now()).total_seconds()
            if wait < -45:
                print(f"  (sinal vencido: entrada {sig['horario_entrada']} ja passou; ignorado)")
                return
            if wait > 0:
                print(f"  aguardando ate {sig['horario_entrada']} ({int(wait)}s)...")
                time.sleep(wait)

        n_gale = min(len(sig.get("gales") or []), MAX_GALE) if USE_GALE else 0

        for level in range(n_gale + 1):
            if stop_requested():
                print("  (STOP ativo; interrompendo sequencia)")
                break
            b0 = saldo()
            tag = "ENTRADA" if level == 0 else f"GALE {level}"
            print(f"  [{tag}] {symbol} {direction} ${amount:g} exp {close_type} | saldo={b0}")

            res = ac.open_trade(symbol, amount, direction, is_demo=CONTA_DEMO, close_type=close_type)
            if not res["ok"]:
                print("  ORDEM REJEITADA:", res["status"], json.dumps(res["body"], ensure_ascii=False)[:200])
                if res["status"] == 401:
                    state["halt"] = True
                    print("  >>> JWT expirou. Recapture .tmp/captura.txt e reinicie o robo. <<<")
                break

            body = res["body"] if isinstance(res["body"], dict) else {}
            close_ms = body.get("closeTime")
            during = (b0 or 0) - amount

            # espera o fechamento
            if close_ms:
                w = close_ms / 1000 - time.time() + 3
                if w > 0:
                    time.sleep(w)
            else:
                time.sleep(mins * 60 + 3)

            # detecta resultado pelo saldo (com tolerancia a atraso de liquidacao)
            b1 = during
            for _ in range(9):
                cur = saldo()
                if cur is not None:
                    b1 = cur
                    if cur > during + 0.001:   # subiu = win/draw liquidado
                        break
                time.sleep(3)

            diff = (b1 or 0) - (b0 or 0)
            result = "WIN" if diff > 0.001 else ("DRAW" if diff > -0.001 else "LOSS")
            print(f"    -> {result} | saldo {b0} -> {b1} ({diff:+.2f})")
            log_op([datetime.now().isoformat(timespec="seconds"), symbol, direction, amount, tag, result, round(diff, 2), b1])

            if result != "LOSS":
                break
            amount = round(amount * GALE_FACTOR, 2)

        print("  sequencia encerrada.\n")
    finally:
        if ONE_AT_A_TIME:
            busy.release()


client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)


@client.on(events.NewMessage(chats=GRUPO))
async def handler(event):
    sig = parse_signal(event.message.text or "")
    if not sig:
        return
    print("SINAL:", json.dumps(sig, ensure_ascii=False))
    threading.Thread(target=run_sequence, args=(sig,), daemon=True).start()


async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("Sessao invalida. Rode py tools/telegram_login.py")
        return
    await client.get_dialogs()
    ent = await client.get_entity(GRUPO)
    n, wr, liberado = rm.edge_status()
    wrtxt = f"{wr*100:.1f}%" if wr is not None else "sem dados"
    print("=" * 54)
    print("ROBO ATIVO - canal:", getattr(ent, "title", GRUPO))
    print(f"Conta: {'DEMO' if CONTA_DEMO else 'REAL'} | Sizing: {rm.sizing} | "
          f"Entrada base: ${ENTRY:g} | Gale: {'ON x'+str(MAX_GALE) if USE_GALE else 'OFF'}")
    print(f"Saldo: {saldo()} | Stop dia: -${rm.stop_loss_dia:g}/+${rm.stop_win_dia:g} | "
          f"Stop semana: -${rm.stop_loss_sem:g}")
    print(f"Risco: max {rm.max_perdas} perdas seguidas | degradacao janela {rm.degrad_janela} | "
          f"horarios: {os.environ.get('HORARIOS_PERMITIDOS') or 'todos'}")
    print(f"Edge-gate (p/ real): amostra {n}/{rm.edge_min}, acerto {wrtxt} -> "
          f"{'LIBERADO' if liberado else 'BLOQUEADO'}")
    print("KILL SWITCH: crie o arquivo .tmp/STOP ou aperte Ctrl+C")
    print("=" * 54)
    print("Aguardando sinais...\n")
    await client.run_until_disconnected()


with client:
    client.loop.run_until_complete(main())
