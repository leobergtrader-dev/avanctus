"""
notify.py — Envia avisos pro WhatsApp. Prioriza o webhook do BotConversa (POST), com
fallback pro CallMeBot. Sem config, vira no-op (nao quebra nada).
Config .env: BOTCONVERSA_WEBHOOK_URL (preferido) | WHATS_PHONE + WHATS_APIKEY (CallMeBot).
"""
import os
import requests


def enviar(msg):
    """Tenta BotConversa (webhook); se nao tiver, cai pro CallMeBot."""
    url = os.environ.get("BOTCONVERSA_WEBHOOK_URL", "").strip()
    if url:
        phone = os.environ.get("WHATS_PHONE", "").strip()
        # envia varias chaves comuns p/ o fluxo do BotConversa ler a que usar
        payload = {"telefone": phone, "phone": phone, "mensagem": msg, "message": msg, "text": msg}
        try:
            r = requests.post(url, json=payload, timeout=20)
            return {"ok": r.status_code < 400, "via": "botconversa", "status": r.status_code, "resp": r.text[:160]}
        except Exception as e:
            return {"ok": False, "via": "botconversa", "motivo": str(e)}
    return whatsapp(msg)


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
