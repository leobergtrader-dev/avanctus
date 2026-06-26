"""
historico_dump.py — Baixa o historico de mensagens do canal para analise (read-only).
Usa a sessao ja salva no .env. Salva texto cru em .tmp/historico_raw.txt.

Uso: py tools/historico_dump.py [quantidade]   (padrao 500)
"""
import os, sys, json
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(os.environ["TELEGRAM_API_ID"])
api_hash = os.environ["TELEGRAM_API_HASH"]
session = os.environ["TELEGRAM_SESSION"].strip()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 500
grupo = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ["TELEGRAM_GRUPO"])
sufixo = f"_{abs(grupo)}" if len(sys.argv) > 2 else ""

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT_TXT = os.path.join(ROOT, ".tmp", f"historico{sufixo}.txt")
OUT_JSON = os.path.join(ROOT, ".tmp", f"historico{sufixo}.json")

client = TelegramClient(StringSession(session), api_id, api_hash)

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("Sessao invalida; rode telegram_login.py"); return
    await client.get_dialogs()
    ent = await client.get_entity(grupo)
    msgs = []
    async for m in client.iter_messages(ent, limit=N):
        if m.text:
            msgs.append({"id": m.id, "date": m.date.isoformat(), "text": m.text})
    msgs.reverse()  # ordem cronologica
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        for m in msgs:
            f.write(f"\n----- [{m['id']}] {m['date']} -----\n{m['text']}\n")
    json.dump(msgs, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Baixadas {len(msgs)} mensagens com texto -> .tmp/historico_raw.txt")

with client:
    client.loop.run_until_complete(main())
