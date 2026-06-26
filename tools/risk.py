"""
risk.py — Gestao de risco (Layer 2). Decide SE pode operar e QUANTO apostar.

Tudo derivado de .tmp/operacoes.csv (robusto a reinicio) + config do .env.
Cobre: filtro de horario, stop diario/semanal, circuit breaker (perdas seguidas),
stop por degradacao, sizing flat/kelly e edge-gate para conta real.
"""
import os
import csv
from datetime import datetime


def _f(k, d):
    try:
        return float(os.environ.get(k, d))
    except ValueError:
        return float(d)


def _i(k, d):
    try:
        return int(float(os.environ.get(k, d)))
    except ValueError:
        return int(d)


ROOT = os.path.dirname(os.path.dirname(__file__))
CSV = os.path.join(ROOT, ".tmp", "operacoes.csv")
STOP_FILE = os.path.join(ROOT, ".tmp", "STOP")


def _parse_horarios(s):
    janelas = []
    for parte in (s or "").split(","):
        parte = parte.strip()
        if "-" in parte:
            a, b = parte.split("-")
            try:
                janelas.append((int(a), int(b)))
            except ValueError:
                pass
    return janelas


class RiskManager:
    def __init__(self):
        self.horarios = _parse_horarios(os.environ.get("HORARIOS_PERMITIDOS", ""))
        self.stop_win_dia = _f("STOP_WIN_DIA", 0)
        self.stop_loss_dia = _f("STOP_LOSS_DIA", 0)
        self.stop_loss_sem = _f("STOP_LOSS_SEMANA", 0)
        self.max_perdas = _i("MAX_PERDAS_SEGUIDAS", 0)
        self.degrad_janela = _i("DEGRAD_JANELA", 0)
        self.breakeven = _f("BREAKEVEN", 0.54)
        self.sizing = os.environ.get("SIZING", "flat").strip().lower()
        self.kelly_frac = _f("KELLY_FRACAO", 0.25)
        self.payout = _f("PAYOUT", 0.85)
        self.banca = _f("BANCA", 10000)
        self.min_stake = _f("MIN_STAKE", 5)
        self.max_stake = _f("MAX_STAKE", 200)
        self.kelly_min = _i("KELLY_MIN_AMOSTRA", 100)
        self.edge_min = _i("EDGE_MIN_AMOSTRA", 100)
        self.entry = _f("ENTRY_AMOUNT", 25)
        self.max_dia = _i("MAX_TRADES_DAY", 60)

    # ---------- leitura do historico ----------
    def _rows(self):
        if not os.path.exists(CSV):
            return []
        try:
            return list(csv.DictReader(open(CSV, encoding="utf-8")))
        except OSError:
            return []

    @staticmethod
    def _num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    def _seqs(self, rows):
        seqs, cur = [], None
        for r in rows:
            if r.get("nivel") == "ENTRADA":
                if cur:
                    seqs.append(cur)
                cur = [r]
            elif cur:
                cur.append(r)
        if cur:
            seqs.append(cur)
        return seqs

    def _pnl(self, rows, escopo):
        now = datetime.now()
        tot = 0.0
        for r in rows:
            q = r.get("quando", "")
            try:
                d = datetime.fromisoformat(q)
            except ValueError:
                continue
            if escopo == "dia" and d.date() != now.date():
                continue
            if escopo == "semana" and d.isocalendar()[:2] != now.isocalendar()[:2]:
                continue
            tot += self._num(r.get("pnl"))
        return tot

    def _trades_hoje(self, rows):
        now = datetime.now().date()
        n = 0
        for r in rows:
            try:
                if datetime.fromisoformat(r.get("quando", "")).date() == now:
                    n += 1
            except ValueError:
                pass
        return n

    def _consec_perdas(self, rows):
        # So conta perdas seguidas DENTRO do dia atual (circuit breaker "pausa o dia").
        hoje = datetime.now().date()
        rows_hoje = []
        for r in rows:
            try:
                if datetime.fromisoformat(r.get("quando", "")).date() == hoje:
                    rows_hoje.append(r)
            except ValueError:
                pass
        c = 0
        for s in reversed(self._seqs(rows_hoje)):
            if s[-1].get("resultado") in ("WIN", "DRAW"):
                break
            c += 1
        return c

    def _winrate_recente(self, rows, n):
        mains = [r for r in rows if r.get("nivel") == "ENTRADA"][-n:]
        if not mains:
            return None, 0
        w = sum(1 for r in mains if r.get("resultado") == "WIN")
        return w / len(mains), len(mains)

    # ---------- decisoes ----------
    def hora_permitida(self, hhmm):
        if not self.horarios:
            return True
        try:
            h = int(hhmm.split(":")[0])
        except (ValueError, AttributeError, IndexError):
            return True
        return any(a <= h <= b for a, b in self.horarios)

    def pode_operar(self, sig):
        """Retorna (ok, motivo)."""
        if os.path.exists(STOP_FILE):
            return False, "KILL SWITCH ativo (.tmp/STOP)"
        rows = self._rows()

        if self.max_dia and self._trades_hoje(rows) >= self.max_dia:
            return False, f"limite diario de {self.max_dia} entradas atingido"

        if sig.get("horario_entrada") and not self.hora_permitida(sig["horario_entrada"]):
            return False, f"fora das janelas de horario ({sig['horario_entrada']})"

        if self.stop_loss_sem and self._pnl(rows, "semana") <= -abs(self.stop_loss_sem):
            return False, f"STOP-LOSS SEMANAL atingido ({self._pnl(rows,'semana'):+.2f})"

        pnl_dia = self._pnl(rows, "dia")
        if self.stop_loss_dia and pnl_dia <= -abs(self.stop_loss_dia):
            return False, f"STOP-LOSS DIARIO atingido ({pnl_dia:+.2f})"
        if self.stop_win_dia and pnl_dia >= abs(self.stop_win_dia):
            return False, f"META DIARIA atingida ({pnl_dia:+.2f}) - parando p/ travar lucro"

        if self.max_perdas and self._consec_perdas(rows) >= self.max_perdas:
            return False, f"circuit breaker: {self.max_perdas} perdas seguidas"

        if self.degrad_janela:
            wr, n = self._winrate_recente(rows, self.degrad_janela)
            if wr is not None and n >= self.degrad_janela and wr < self.breakeven:
                return False, f"degradacao: acerto recente {wr*100:.0f}% < break-even {self.breakeven*100:.0f}%"

        return True, "ok"

    def tamanho(self):
        if self.sizing != "kelly":
            return self.entry
        rows = self._rows()
        wr, n = self._winrate_recente(rows, max(self.kelly_min, 30))
        if wr is None or n < self.kelly_min:
            return self.entry  # ainda medindo -> flat
        b = self.payout
        f = (wr * (b + 1) - 1) / b  # fracao de Kelly
        if f <= 0:
            return 0.0  # sem vantagem -> nao opera
        val = self.banca * f * self.kelly_frac
        return round(max(self.min_stake, min(val, self.max_stake)), 2)

    def resumo(self):
        rows = self._rows()
        n, wr, liberado = self.edge_status()
        return {
            "pnl_dia": round(self._pnl(rows, "dia"), 2),
            "pnl_semana": round(self._pnl(rows, "semana"), 2),
            "trades_hoje": self._trades_hoje(rows),
            "consec_perdas": self._consec_perdas(rows),
            "edge_amostra": n,
            "edge_winrate": round(wr * 100, 1) if wr is not None else None,
            "edge_liberado": liberado,
            "stop_loss_dia": self.stop_loss_dia,
            "stop_win_dia": self.stop_win_dia,
            "stop_loss_sem": self.stop_loss_sem,
            "sizing": self.sizing,
            "max_dia": self.max_dia,
        }

    def edge_status(self):
        """(amostra, winrate, liberado_para_real)."""
        rows = self._rows()
        mains = [r for r in rows if r.get("nivel") == "ENTRADA"]
        if not mains:
            return 0, None, False
        wr = sum(1 for r in mains if r.get("resultado") == "WIN") / len(mains)
        liberado = len(mains) >= self.edge_min and wr > self.breakeven
        return len(mains), wr, liberado
