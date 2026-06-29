"""
notify.py — Envia avisos pro seu WhatsApp via CallMeBot (gratis, pra uso pessoal).
Configurar no .env: WHATS_PHONE (+5548...) e WHATS_APIKEY (obtida no CallMeBot).
Sem config, vira no-op (nao quebra nada).
"""
import os
import requests


def whatsapp(msg):
    phone = os.environ.get("WHATS_PHONE", "").strip()
    key = os.environ.get("WHATS_APIKEY", "").strip()
    if not phone or not key:
        return {"ok": False, "motivo": "WHATS_PHONE/WHATS_APIKEY nao configurados"}
    try:
        r = requests.get("https://api.callmebot.com/whatsapp.php",
                         params={"phone": phone, "text": msg, "apikey": key}, timeout=20)
        ok = r.status_code < 400 and "ERROR" not in r.text.upper()
        return {"ok": ok, "status": r.status_code, "resp": r.text[:160]}
    except Exception as e:
        return {"ok": False, "motivo": str(e)}
