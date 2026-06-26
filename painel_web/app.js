const $ = (id) => document.getElementById(id);
const api = (u, opt) => fetch(u, opt).then((r) => r.json());

function money(v) {
  if (v === null || v === undefined) return "—";
  return "$" + Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function signed(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  const s = (n >= 0 ? "+" : "") + n.toFixed(2);
  return `<span class="${n >= 0 ? "pos" : "neg"}">${s}</span>`;
}

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    $("canal").textContent = s.canal || "—";
    $("roboBadge").className = "badge " + (s.robo_ligado ? "badge-on" : "badge-off");
    $("roboBadge").textContent = s.robo_ligado ? "robô ligado" : "robô desligado";
    $("conta").textContent = s.conta;
    $("saldoDemo").textContent = money(s.saldo_demo);
    $("saldoReal").textContent = money(s.saldo_real);
    $("pnlDia").innerHTML = signed(s.risco?.pnl_dia);
    $("tradesDia").textContent = s.risco?.trades_hoje ?? "—";
    $("login").innerHTML = s.login_ok
      ? `<span class="pos">OK</span> <span class="muted">até ${s.jwt_validade || "?"}</span>`
      : `<span class="neg">falha</span>`;
    const r = s.risco || {};
    const wr = r.edge_winrate == null ? "sem dados" : r.edge_winrate + "%";
    $("edge").innerHTML = `amostra <b>${r.edge_amostra}</b> / ${100} · acerto <b>${wr}</b> · ` +
      (r.edge_liberado ? `<span class="pos">LIBERADO p/ real</span>` : `<span class="neg">BLOQUEADO</span> (precisa demo validada)`);
  } catch (e) {}
}

async function refreshOps() {
  const rows = await api("/api/operacoes");
  $("opCount").textContent = rows.length ? rows.length + " recentes" : "";
  const tb = $("ops").querySelector("tbody");
  tb.innerHTML = rows.map((o) => {
    const cls = o.resultado === "WIN" ? "win" : o.resultado === "LOSS" ? "loss" : "draw";
    const hora = (o.quando || "").slice(11, 19);
    return `<tr><td>${hora}</td><td>${o.ativo}</td><td>${o.direcao}</td><td>${o.valor}</td>
      <td>${o.nivel}</td><td class="${cls}">${o.resultado}</td><td>${signed(o.pnl)}</td></tr>`;
  }).join("");
}

async function refreshLog() {
  const lines = await api("/api/log");
  $("log").innerHTML = lines.map((l) => l.replace(/</g, "&lt;")).join("<br>");
}

async function loadConfig() {
  const c = await api("/api/config");
  for (const k in c) { const el = $(k); if (el) el.value = c[k]; }
}

$("btnLigar").onclick = async () => { await api("/api/robo/ligar", { method: "POST" }); refreshStatus(); };
$("btnDesligar").onclick = async () => { await api("/api/robo/desligar", { method: "POST" }); refreshStatus(); };
$("btnPanico").onclick = async () => {
  if (confirm("Parar tudo imediatamente?")) { await api("/api/robo/panico", { method: "POST" }); refreshStatus(); }
};
$("btnSalvar").onclick = async () => {
  const keys = ["CONTA_DEMO","ENTRY_AMOUNT","SIZING","USE_GALE","MAX_GALE","HORARIOS_PERMITIDOS",
    "STOP_WIN_DIA","STOP_LOSS_DIA","STOP_LOSS_SEMANA","MAX_PERDAS_SEGUIDAS","MAX_TRADES_DAY"];
  const body = {};
  keys.forEach((k) => { const el = $(k); if (el) body[k] = el.value; });
  await api("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  $("cfgMsg").textContent = "✔ Salvo. (vale para os próximos sinais)";
  setTimeout(() => ($("cfgMsg").textContent = ""), 4000);
};

// ---- Abas ----
$("tabPainel").onclick = () => {
  $("view-painel").style.display = "";
  $("view-relatorio").style.display = "none";
  $("tabPainel").classList.add("active"); $("tabRelatorio").classList.remove("active");
};
$("tabRelatorio").onclick = () => {
  $("view-painel").style.display = "none";
  $("view-relatorio").style.display = "";
  $("tabRelatorio").classList.add("active"); $("tabPainel").classList.remove("active");
  renderRelatorio();
};

function tabelaWR(obj) {
  const rows = Object.entries(obj || {}).sort((a, b) => b[1].total - a[1].total);
  return `<table class="rep"><tr><th></th><th>acerto</th><th>amostra</th><th>pnl</th></tr>` +
    rows.map(([k, v]) => `<tr><td>${k}</td><td>${v.winrate ?? "—"}%</td><td>${v.total}</td><td>${signed(v.pnl)}</td></tr>`).join("") +
    `</table>`;
}

async function renderRelatorio() {
  const r = await api("/api/relatorio");
  if (r.erro) { $("relResumo").innerHTML = "Erro: " + r.erro; return; }
  const wr = r.winrate == null ? "sem dados" : r.winrate + "%";
  const acima = r.winrate != null && r.winrate > r.breakeven;
  $("relResumo").innerHTML = `
    <div class="row">
      <div><div class="muted">Sinais</div><div class="big">${r.amostra}</div></div>
      <div><div class="muted">Acerto (entrada)</div><div class="big">${wr}</div></div>
      <div><div class="muted">PnL total</div><div class="big">${signed(r.pnl_total)}</div></div>
      <div><div class="muted">Payout medido</div><div class="big">${r.payout_medido ? r.payout_medido + "%" : "—"}</div></div>
      <div><div class="muted">Break-even</div><div class="big">${r.breakeven}%</div></div>
    </div>
    <p class="${acima ? "pos" : "neg"}">${r.winrate == null ? "Coletando dados…" :
      (acima ? "✔ Acima do break-even — promissor" : "✖ Abaixo do break-even — sem vantagem ainda")}</p>`;
  $("relAtivo").innerHTML = tabelaWR(r.por_ativo);
  $("relHora").innerHTML = tabelaWR(r.por_hora);
  if (r.filtro_ia) {
    const f = r.filtro_ia;
    $("relFiltro").innerHTML = `<table class="rep">
      <tr><th>grupo</th><th>acerto</th><th>amostra</th></tr>
      <tr><td>score alto (≥0,5)</td><td>${f.score_alto.winrate ?? "—"}%</td><td>${f.score_alto.total}</td></tr>
      <tr><td>score baixo (&lt;0,5)</td><td>${f.score_baixo.winrate ?? "—"}%</td><td>${f.score_baixo.total}</td></tr></table>
      <p class="muted small">Se "score alto" ganhar bem mais que "score baixo", o filtro tem valor — aí vale ligar.</p>`;
  } else { $("relFiltro").innerHTML = '<span class="muted">Sem análises registradas ainda.</span>'; }
  $("relP").textContent = "taxa usada no cálculo: " + r.p_usado + "%";
  $("relSim").innerHTML = `<table class="rep">
    <tr><th>estratégia</th><th>EV/ciclo</th><th>perda máx</th><th>risco estouro/dia</th><th>veredito</th></tr>` +
    r.simulador.map(s => `<tr><td>${s.estrategia}</td>
      <td class="${s.ev_por_ciclo >= 0 ? "pos" : "neg"}">${signed(s.ev_por_ciclo)}</td>
      <td>$${s.perda_maxima}</td><td>${(s.risco_estouro_dia * 100).toFixed(1)}%</td>
      <td class="${s.veredito === "POSITIVO" ? "pos" : "neg"}">${s.veredito}</td></tr>`).join("") + `</table>`;
}

function tick() { refreshStatus(); refreshOps(); refreshLog(); }
loadConfig(); tick();
setInterval(refreshStatus, 6000);
setInterval(refreshOps, 8000);
setInterval(refreshLog, 3000);
