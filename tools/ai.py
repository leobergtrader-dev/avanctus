"""
ai.py — Camada de IA (opcional) que EXPLICA/pondera a analise tecnica.

Liga so se houver ANTHROPIC_API_KEY no .env (modelo rapido/barato). A IA NAO preve preco;
ela le os indicadores e da uma leitura curta. Sem chave, retorna "" (silencioso).
(Pode-se trocar por Gemini depois; aqui usamos Claude por padrao.)
"""
import os
import requests

MODEL = os.environ.get("AI_MODEL", "claude-haiku-4-5-20251001")


def explain(sig, analise, candles):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
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
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": MODEL, "max_tokens": 120, "messages": [{"role": "user", "content": prompt}]},
            timeout=20,
        )
        d = r.json()
        return (d.get("content") or [{}])[0].get("text", "").strip()
    except Exception as e:
        return f"(IA indisponivel: {e})"
