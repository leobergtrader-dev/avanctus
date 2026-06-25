"""
telegram_listen.py — Le o canal de sinais e parseia em tempo real (Layer 3 / fase Link).

NAO executa nenhuma ordem. Apenas:
  1) mostra as ultimas mensagens do canal,
  2) fica "ouvindo" sinais novos e imprime o JSON parseado.

Como rodar:
    py tools/telegram_listen.py
"""

import os
import sys
import json

# Garante emojis/acentos no console do Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    from dotenv import load_dotenv
except ImportError:
    print("Faltam dependencias. Rode:  pip install telethon python-dotenv")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))
from signal_parser import parse_signal

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_PATH)

api_id = int(os.environ["TELEGRAM_API_ID"])
api_hash = os.environ["TELEGRAM_API_HASH"]
session = os.environ.get("TELEGRAM_SESSION", "").strip()
grupo_raw = os.environ.get("TELEGRAM_GRUPO", "").strip()

if not session:
    print("Sem session. Rode primeiro:  py tools/telegram_login.py")
    sys.exit(1)

# O grupo pode ser ID numerico (-100...) ou @usuario
try:
    grupo = int(grupo_raw)
except ValueError:
    grupo = grupo_raw

client = TelegramClient(StringSession(session), api_id, api_hash)


def short(txt, n=70):
    txt = (txt or "").replace("\n", " ").strip()
    return (txt[:n] + "...") if len(txt) > n else txt


async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("Sessao invalida. Rode de novo:  py tools/telegram_login.py")
        return

    # Carrega dialogos para o Telethon achar o canal pelo ID
    await client.get_dialogs()
    entity = await client.get_entity(grupo)
    titulo = getattr(entity, "title", str(grupo))
    print(f"Canal conectado: {titulo}\n")

    print("=== Ultimas 15 mensagens (parse de teste) ===")
    async for msg in client.iter_messages(entity, limit=15):
        if not msg.text:
            continue
        sig = parse_signal(msg.text)
        if sig:
            print(f"[SINAL] {short(msg.text)}")
            print("        ->", json.dumps(sig, ensure_ascii=False))
        else:
            print(f"[ignor] {short(msg.text)}")

    print("\n=== Ouvindo novos sinais ao vivo (Ctrl+C para parar) ===")

    @client.on(events.NewMessage(chats=entity))
    async def handler(event):
        sig = parse_signal(event.message.text or "")
        if sig:
            print("\nNOVO SINAL:")
            print(json.dumps(sig, ensure_ascii=False, indent=2))
        else:
            print(f"(mensagem ignorada: {short(event.message.text)})")

    await client.run_until_disconnected()


with client:
    client.loop.run_until_complete(main())
