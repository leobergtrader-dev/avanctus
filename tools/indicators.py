"""
indicators.py — Analise tecnica deterministica sobre candles reais.

Calcula EMA(tendencia), RSI, momentum e sequencia de cor de velas; mede o quanto
os indicadores CONCORDAM com a direcao do sinal e devolve um score de confianca 0..1.

IMPORTANTE: heuristica de PARTIDA. So vale depois de comprovada em MODO SOMBRA
(ver se os sinais 'ENTRAR' ganham mais que os 'PULAR' nos nossos dados).
"""


def ema(vals, period):
    if not vals:
        return None
    k = 2 / (period + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def rsi(closes, period=14):
    if len(closes) <= period:
        return None
    ganhos, perdas = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        ganhos.append(max(d, 0))
        perdas.append(max(-d, 0))
    ag = sum(ganhos[-period:]) / period
    ap = sum(perdas[-period:]) / period
    if ap == 0:
        return 100.0
    rs = ag / ap
    return 100 - (100 / (1 + rs))


def streak_cor(candles):
    """Quantas velas seguidas da mesma cor no fim (positivo=verde, negativo=vermelho)."""
    if not candles:
        return 0
    def cor(c):
        return 1 if c["close"] >= c["open"] else -1
    ult = cor(candles[-1])
    n = 0
    for c in reversed(candles):
        if cor(c) == ult:
            n += 1
        else:
            break
    return n * ult


def analisar(candles, direcao):
    """direcao: 'BUY' (CALL/alta) ou 'SELL' (PUT/baixa).
    Retorna dict com score (0..1), recomendacao, e razoes legiveis."""
    closes = [c["close"] for c in candles if c["close"] is not None]
    if len(closes) < 22:
        return {"score": None, "recomendacao": "SEM_DADOS", "razoes": ["poucos candles"]}

    quer_alta = direcao == "BUY"
    e9, e21 = ema(closes[-30:], 9), ema(closes[-30:], 21)
    r = rsi(closes, 14)
    mom = closes[-1] - closes[-4]            # momentum 3 velas
    st = streak_cor(candles)                  # sequencia de cor

    checks = []  # (concorda?, descricao)
    # 1) Tendencia (EMA9 vs EMA21)
    tend_alta = e9 >= e21
    checks.append((tend_alta == quer_alta, f"tendencia {'alta' if tend_alta else 'baixa'}"))
    # 2) RSI alinhado ao lado (acima/abaixo de 50) sem extremo contra
    rsi_alta = r >= 50
    rsi_ok = (rsi_alta == quer_alta) and (r < 72 if quer_alta else r > 28)
    checks.append((rsi_ok, f"RSI {r:.0f}"))
    # 3) Momentum a favor
    mom_ok = (mom > 0) == quer_alta
    checks.append((mom_ok, f"momentum {'+' if mom > 0 else '-'}"))
    # 4) Ultima vela a favor
    vela_alta = candles[-1]["close"] >= candles[-1]["open"]
    checks.append((vela_alta == quer_alta, f"ultima vela {'verde' if vela_alta else 'vermelha'}"))

    favor = sum(1 for ok, _ in checks if ok)
    score = favor / len(checks)
    razoes = [("OK " if ok else "x  ") + d for ok, d in checks]
    return {
        "score": round(score, 2),
        "favor": favor,
        "total": len(checks),
        "rsi": round(r, 1),
        "tendencia": "alta" if tend_alta else "baixa",
        "streak": st,
        "razoes": razoes,
    }
