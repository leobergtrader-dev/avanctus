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
        f"Sinal de opcao binaria M{sig.get('expiracao_min')}: {sig.get('ativo_texto')} "
        f"direcao {sig.get('direcao')}. Analise tecnica: score {analise.get('score')}, "
        f"tendencia {analise.get('tendencia')}, RSI {analise.get('rsi')}, streak {analise.get('streak')}, "
        f"ultimos fechamentos {closes}. "
        "Responda em 1 frase curta: a tecnica apoia ou nao esse sinal, e por que."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
    try:
        r = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"maxOutputTokens": 200, "temperature": 0.3,
                                       "thinkingConfig": {"thinkingBudget": 0}}},
            timeout=25,
        )
        d = r.json()
        cand = (d.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        txt = " ".join(p.get("text", "") for p in parts if p.get("text")).strip()
        return txt or f"(IA sem texto: {str(d)[:150]})"
    except Exception as e:
        return f"(IA indisponivel: {e})"
