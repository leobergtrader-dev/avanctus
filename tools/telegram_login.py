"""
telegram_login.py — Login UNICO no Telegram (Layer 3 / fase Link).

Roda UMA vez. Voce digita o codigo que chega no seu Telegram (e a senha 2FA, se tiver).
No fim, salva a "session string" no .env para os proximos scripts conectarem sozinhos.

Como rodar (no terminal, dentro da pasta do projeto):
    py tools/telegram_login.py
"""

import os
import re
import sys

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from dotenv import load_dotenv
except ImportError:
    print("Faltam dependencias. Rode:  pip install telethon python-dotenv")
    sys.exit(1)

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_PATH)

api_id = os.environ.get("TELEGRAM_API_ID", "").strip()
api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
phone = os.environ.get("TELEGRAM_PHONE", "").strip()

if not api_id or not api_hash or not phone:
    print("Preencha TELEGRAM_API_ID, TELEGRAM_API_HASH e TELEGRAM_PHONE no .env primeiro.")
    sys.exit(1)

print("Conectando ao Telegram... (vai chegar um codigo no seu app Telegram)\n")

client = TelegramClient(StringSession(), int(api_id), api_hash)
client.start(phone=lambda: phone)   # pede o codigo (e senha 2FA, se houver) no terminal

me = client.get_me()
session_str = client.session.save()
client.disconnect()

# Salva a session no .env (substitui a linha TELEGRAM_SESSION=)
with open(ENV_PATH, "r", encoding="utf-8") as f:
    content = f.read()
if re.search(r"^TELEGRAM_SESSION=.*$", content, flags=re.M):
    content = re.sub(r"^TELEGRAM_SESSION=.*$", f"TELEGRAM_SESSION={session_str}", content, flags=re.M)
else:
    content = content.rstrip() + f"\nTELEGRAM_SESSION={session_str}\n"
with open(ENV_PATH, "w", encoding="utf-8") as f:
    f.write(content)

nome = (me.first_name or "") + (" @" + me.username if me.username else "")
print(f"\nLogin OK: {nome}")
print("Session salva no .env. Pode rodar:  py tools/telegram_listen.py")
