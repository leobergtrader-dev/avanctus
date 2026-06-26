"""Lista os canais/grupos do Telegram (id + titulo) para acharmos um canal especifico."""
import os, sys
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
filtro = (sys.argv[1].lower() if len(sys.argv) > 1 else "")

client = TelegramClient(StringSession(session), api_id, api_hash)

async def main():
    await client.connect()
    async for d in client.iter_dialogs():
        if d.is_channel or d.is_group:
            t = d.name or ""
            if not filtro or filtro in t.lower():
                print(f"{d.id}\t{t}")

with client:
    client.loop.run_until_complete(main())
