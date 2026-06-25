"""
signal_parser.py — Layer 3 (Tool determinística)

Converte a mensagem CRUA do canal de sinais em um dicionário estruturado.
Baseado no formato real do canal "VIVA DE RENDA - AVANCTUS".

Exemplo de entrada:
    Corretora: Avanctus
    1 Minutos de OPERACAO
    SOLANA (OTC) - 15:49 PUT
    TERMINA EM: 15:50h
    1o GALE: TERMINA EM: 15:51h
    2o GALE: TERMINA EM: 15:52h

Regra: se a mensagem NAO tiver direcao (CALL/PUT/COMPRA/VENDA) + ativo, retorna None
(ou seja, ignoramos promos, imagens, textos soltos).
"""

import re

# Direcao -> normalizacao. CALL = alta/compra, PUT = baixa/venda.
DIRECTION_MAP = {
    "CALL":   {"direcao": "CALL", "acao": "COMPRA", "lado_api": "BUY"},
    "PUT":    {"direcao": "PUT",  "acao": "VENDA",  "lado_api": "SELL"},
    "COMPRA": {"direcao": "CALL", "acao": "COMPRA", "lado_api": "BUY"},
    "VENDA":  {"direcao": "PUT",  "acao": "VENDA",  "lado_api": "SELL"},
}

# Mapa nome-do-ativo -> base do ticker. Sera confirmado/expandido com /symbols da Avanctus.
ASSET_BASE_MAP = {
    "SOLANA": "SOL", "SOL": "SOL",
    "BITCOIN": "BTC", "BTC": "BTC",
    "ETHEREUM": "ETH", "ETH": "ETH",
    "CARDANO": "ADA", "ADA": "ADA",
    "RIPPLE": "XRP", "XRP": "XRP",
    "DOGECOIN": "DOGE", "DOGE": "DOGE",
    "BNB": "BNB",
    "LITECOIN": "LTC", "LTC": "LTC",
    "POLKADOT": "DOT", "DOT": "DOT",
    "AVALANCHE": "AVAX", "AVAX": "AVAX",
    "CHAINLINK": "LINK", "LINK": "LINK",
    "TRON": "TRX", "TRX": "TRX",
    "POLYGON": "MATIC", "MATIC": "MATIC",
}

TIME = r"(\d{1,2}:\d{2})"


def _resolve_ticker(asset_text):
    """Tenta resolver 'SOLANA (OTC)' -> 'SOLUSDT.OTC'. Confirmar com /symbols depois."""
    upper = asset_text.upper()
    is_otc = "OTC" in upper
    core = re.sub(r"\(.*?\)", "", asset_text).strip()      # remove "(OTC)"
    core_up = core.upper().replace(" ", "")
    suffix = ".OTC" if is_otc else ""
    if "/" in core_up:                                     # par forex tipo EUR/USD
        return core_up.replace("/", "") + suffix
    base = ASSET_BASE_MAP.get(core_up)
    if base:
        return f"{base}USDT" + suffix
    return core_up + suffix                                # desconhecido: confirmar manualmente


def parse_signal(text):
    """Retorna dict do sinal, ou None se a mensagem nao for um sinal valido."""
    if not text:
        return None
    t = text.replace("\xa0", " ")
    up = t.upper()

    direction_hit = re.search(r"\b(CALL|PUT|COMPRA|VENDA)\b", up)
    if not direction_hit:
        return None
    direction = DIRECTION_MAP[direction_hit.group(1)]

    # Linha principal: "ATIVO - HH:MM DIRECAO"
    line = re.search(r"(.+?)\s*[-–]\s*" + TIME + r"\s*(CALL|PUT|COMPRA|VENDA)", t, re.I)
    if not line:
        return None
    ativo_texto = line.group(1).strip()
    horario_entrada = line.group(2)

    exp = re.search(r"(\d+)\s*MINUTO", up)
    expiracao_min = int(exp.group(1)) if exp else None

    # Todos os "TERMINA EM HH:MM"; o 1o e o fim principal, os de GALE sao os gales.
    todos_fim = re.findall(r"TERMINA EM[:\s]*" + TIME, up)
    fim_principal = todos_fim[0] if todos_fim else None
    gales = re.findall(r"GALE[:\s]*TERMINA EM[:\s]*" + TIME, up)

    return {
        "corretora": "Avanctus",
        "ativo_texto": ativo_texto,
        "ativo_ticker": _resolve_ticker(ativo_texto),
        "expiracao_min": expiracao_min,
        "horario_entrada": horario_entrada,
        "direcao": direction["direcao"],
        "acao": direction["acao"],
        "lado_api": direction["lado_api"],
        "fim_principal": fim_principal,
        "gales": gales,
    }


# Teste rapido com a amostra real (rode: py tools/signal_parser.py)
if __name__ == "__main__":
    import json
    exemplo = (
        "Corretora: Avanctus\n"
        "1 Minutos de OPERACAO\n"
        "SOLANA (OTC) - 15:49 PUT\n"
        "TERMINA EM: 15:50h\n"
        "1o GALE: TERMINA EM: 15:51h\n"
        "2o GALE: TERMINA EM: 15:52h\n"
    )
    print(json.dumps(parse_signal(exemplo), ensure_ascii=False, indent=2))
