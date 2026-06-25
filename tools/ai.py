"""
ai.py — Camada de IA (Gemini) que EXPLICA/pondera a analise tecnica.

Liga so se houver GEMINI_API_KEY no .env. A IA NAO preve preco; ela le os indicadores
e da uma leitura curta e honesta. Sem chave, retorna "" (silencioso).

Chave: https://aistudio.google.com/app/apikey
"""
import os
import requests

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


def explain(sig, analise, candles):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return ""
    closes = [c["close"] for c in candles[-12:]]
    prompt = (
        f"Opcao binaria M{sig.get('expiracao_min')} no ativo {sig.get('ativo_texto')}, "
        f"direcao do sinal: {sig.get('direcao')} ({sig.get('lado_api')}).\n"
        f"Analise tecnica: score {analise.get('score')} ({analise.get('favor')}/{analise.get('total')}), "
        f"tendencia {analise.get('tendencia')}, RSI {analise.get('rsi')}, "
        f"sequencia de cor {analise.get('streak')}.\n"
        f"Ultimos fechamentos (1m): {closes}.\n"
        "Em UMA frase curta e honesta (sem fingir prever o futuro), diga se a tecnica APOIA "
        "ou NAO esse sinal e o motivo principal."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
    try:
        r = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"maxOutputTokens": 120, "temperature": 0.3}},
            timeout=20,
        )
        d = r.json()
        cand = (d.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or [{}]
        txt = parts[0].get("text", "").strip()
        return txt or f"(IA sem resposta: {str(d)[:120]})"
    except Exception as e:
        return f"(IA indisponivel: {e})"
