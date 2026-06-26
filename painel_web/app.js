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
const ABAS = { tabPainel: "view-painel", tabRelatorio: "view-relatorio", tabEstrategia: "view-estrategia" };
function trocarAba(ativo) {
  for (const [tab, view] of Object.entries(ABAS)) {
    $(view).style.display = tab === ativo ? "" : "none";
    $(tab).classList.toggle("active", tab === ativo);
  }
}
$("tabPainel").onclick = () => trocarAba("tabPainel");
$("tabRelatorio").onclick = () => { trocarAba("tabRelatorio"); renderRelatorio(); };
$("tabEstrategia").onclick = () => trocarAba("tabEstrategia");

$("btnEstrat").onclick = async () => {
  $("btnEstrat").textContent = "Calculando…"; $("btnEstrat").disabled = true;
  try {
    const r = await api("/api/estrategia");
    if (r.erro) { $("estratCarteira").innerHTML = "Erro: " + r.erro; return; }
    const c = r.carteira, f = r.forward;
    const fwd = f.retorno_total == null
      ? `<span class="muted">Forward-test: ${f.obs || "iniciando"} (${f.dias || 0} dia(s))</span>`
      : `Forward-test desde ${f.inicio}: <b class="${f.retorno_total >= 0 ? "pos" : "neg"}">${f.retorno_total >= 0 ? "+" : ""}${f.retorno_total}%</b> em ${f.dias} dias`;
    $("estratResumo").innerHTML = `
      <div class="row">
        <div><div class="muted">Comprado</div><div class="big">${c.n_comprado}/${c.n_total}</div></div>
        <div><div class="muted">Exposição média</div><div class="big">${c.exposicao_media}</div></div>
        <div style="flex:1">${fwd}</div>
      </div>`;
    $("estratCarteira").innerHTML = `<table class="rep">
      <tr><th>moeda</th><th>ação</th><th>tamanho</th><th>tendência</th><th>vol anual</th></tr>` +
      c.itens.map(i => `<tr><td>${i.coin}</td>
        <td class="${i.acao === "COMPRADO" ? "pos" : "muted"}">${i.acao}</td>
        <td>${i.tamanho}</td><td>${i.tendencia}</td><td>${i.vol_anual}%</td></tr>`).join("") + `</table>
      <p class="muted small">"Tamanho" = fração da banca por moeda (vol targeting). Caixa = fora do mercado.
      Hoje em caixa = mercado em baixa, estratégia protegendo capital.</p>`;
  } catch (e) { $("estratCarteira").innerHTML = "Erro: " + e.message; }
  finally { $("btnEstrat").textContent = "Atualizar carteira de hoje"; $("btnEstrat").disabled = false; }
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
  // Backtest histórico
  const bt = r.backtest;
  if (bt) {
    const acima = bt.acerto_entrada > bt.breakeven;
    $("relBacktest").innerHTML = `
      <p class="small muted">${bt.n_sinais} sinais reais · validação de fuso ${bt.validacao_fuso_concordancia}% (confiável)</p>
      <table class="rep">
        <tr><th>métrica</th><th>valor</th></tr>
        <tr><td>Acerto por ENTRADA (1 vela)</td><td class="${acima ? "pos" : "neg"}"><b>${bt.acerto_entrada}%</b></td></tr>
        <tr><td>Acerto até 2 velas (1 gale)</td><td>${bt.acerto_ate_2_velas}%</td></tr>
        <tr><td>Acerto até 3 velas (2 gales)</td><td>${bt.acerto_ate_3_velas}%</td></tr>
        <tr><td>O canal declarou</td><td>${bt.canal_declarou_gain}%</td></tr>
        <tr><td>Break-even necessário</td><td>${bt.breakeven}%</td></tr>
      </table>
      <p class="${acima ? "pos" : "neg"}">${acima
        ? "✔ Acerto por entrada ACIMA do break-even"
        : `✖ Acerto por entrada (${bt.acerto_entrada}%) ABAIXO do break-even (${bt.breakeven}%) — sem vantagem. O "${bt.canal_declarou_gain}%" do canal é só o efeito do gale.`}</p>
      <table class="rep">
        <tr><th>estratégia</th><th>resultado (32 dias)</th><th>drawdown máx</th><th>pior sequência</th></tr>
        ${bt.estrategias.map(s => `<tr><td>${s.estrategia}</td>
          <td class="${s.pnl_total >= 0 ? "pos" : "neg"}"><b>${signed(s.pnl_total)}</b></td>
          <td class="neg">−$${Math.abs(s.drawdown_max)}</td>
          <td>${s.pior_sequencia || "—"}</td></tr>`).join("")}
      </table>`;
  } else {
    $("relBacktest").innerHTML = '<span class="muted">Backtest não gerado ainda.</span>';
  }
  // Avalon / outros canais
  const av = r.avalon;
  if (av) {
    const ok = av.ci_entrada[1] > av.breakeven;
    $("relAvalon").innerHTML = `
      <p class="small muted">${av.fonte} · ${av.n_sinais} sinais · candles reais (Binance)</p>
      <table class="rep">
        <tr><th>métrica</th><th>valor</th></tr>
        <tr><td>Acerto por entrada</td><td class="${ok ? "pos" : "neg"}"><b>${av.acerto_entrada}%</b> (CI ${av.ci_entrada[0]}–${av.ci_entrada[1]})</td></tr>
        <tr><td>Break-even</td><td>${av.breakeven}%</td></tr>
      </table>
      <table class="rep"><tr><th>estratégia</th><th>resultado</th><th>drawdown</th></tr>
        ${av.estrategias.map(s => `<tr><td>${s.estrategia}</td>
          <td class="${s.pnl >= 0 ? "pos" : "neg"}">${signed(s.pnl)}</td><td class="neg">−$${Math.abs(s.drawdown_max)}</td></tr>`).join("")}</table>
      <p class="neg small">Mesmo veredito da Avanctus: ${av.acerto_entrada}% < ${av.breakeven}% = sem edge.
      Atenção: se alguma estratégia de gale aparecer positiva, é sorte de amostra (EV negativo garante prejuízo no longo prazo).</p>`;
  } else { $("relAvalon").innerHTML = '<span class="muted">Sem análise de outros canais.</span>'; }
  // Tio Huli (swing) — anexa ao mesmo card
  const sw = r.swing;
  if (sw) {
    const rows = Object.entries(sw.rr).map(([k, v]) =>
      `<tr><td>Alvo ${k}R</td><td>${v.winrate}%</td><td class="${v.expectancia_R >= 0 ? "pos" : "neg"}">${v.expectancia_R >= 0 ? "+" : ""}${v.expectancia_R}R</td><td>${v.profit_factor ?? "—"}</td></tr>`).join("");
    $("relAvalon").innerHTML += `
      <hr style="border-color:var(--line);margin:14px 0">
      <p class="small muted">${sw.fonte} · ${sw.n_sinais} sinais (swing/spot) · candles reais (Binance)</p>
      <table class="rep"><tr><th>saída</th><th>win</th><th>expectância</th><th>profit factor</th></tr>${rows}</table>
      <p class="neg small">Expectância negativa e profit factor < 1 em todas as regras = sem edge (entradas se comportam como aleatórias). Métrica de swing é R, não 54%.</p>`;
  }
  // Grid trading
  const gr = r.grid;
  if (gr) {
    const s = gr.resumo;
    $("relAvalon").innerHTML += `
      <hr style="border-color:var(--line);margin:14px 0">
      <p class="small muted">Grid Trading (estilo WunderTrading) · ${s.n_janelas} janelas de ${gr.config.janela_dias}d · BTC+ETH · com taxas</p>
      <table class="rep">
        <tr><th>métrica</th><th>valor</th></tr>
        <tr><td>Grid médio (por trimestre)</td><td class="${s.grid_medio >= 0 ? "pos" : "neg"}">${s.grid_medio}%</td></tr>
        <tr><td>Janelas positivas</td><td>${s.grid_positivas}/${s.n_janelas}</td></tr>
        <tr><td>Pior janela</td><td class="neg">${s.pior_grid}%</td></tr>
        <tr><td>Buy & Hold médio (referência)</td><td class="pos">${s.buyhold_medio}%</td></tr>
      </table>
      <p class="neg small">Grid lucra em mercado lateral, mas perde a alta nos rallies e fica "ensacado" nos crashes (médio negativo, batido pelo buy&hold). "Ganha na variação" só vale na calmaria.</p>`;
    const gsm = r.grid_smart;
    if (gsm) {
      const s2 = gsm.resumo;
      $("relAvalon").innerHTML += `
        <table class="rep"><tr><th>Grid inteligente (com filtro anti-crash)</th><th>médio</th><th>pior</th></tr>
          <tr><td>Grid puro</td><td class="neg">${s2.puro_medio}%</td><td class="neg">${s2.puro_pior}%</td></tr>
          <tr><td>Grid inteligente</td><td>${s2.smart_medio}%</td><td class="pos">${s2.smart_pior}%</td></tr></table>
        <p class="muted small">O filtro de regime eliminou o risco de crash (pior −23,5% → ${s2.smart_pior}%), mas o lucro também sumiu (~zero). Lição: o "lucro" do grid era o prêmio de risco do crash. Sem almoço grátis.</p>`;
    }
  }
  // Edge Scanner
  const ed = r.edge;
  if (ed) {
    const micro = (ed.edge3_microestrutura && ed.edge3_microestrutura.train) || {};
    const microRows = Object.entries(micro).map(([k, v]) =>
      `<tr><td>${k}</td><td class="${v.reversao_wr > 54 ? "pos" : ""}">${v.reversao_wr}%</td>
       <td>[${v.ci[0]}–${v.ci[1]}]</td><td>${v.n}</td></tr>`).join("");
    const cands = ed.candidatos || [];
    const candHtml = cands.length
      ? `<table class="rep"><tr><th>hipótese</th><th>condição</th><th>treino</th><th>teste</th><th>sobrevive?</th></tr>` +
        cands.map(c => `<tr><td>${c.hipotese}</td><td>${c.condicao}</td><td>${c.train_wr}% (CI ${c.train_ci_inf})</td>
          <td>${c.test_wr ?? "—"}%</td><td class="${c.sobrevive ? "pos" : "neg"}">${c.sobrevive ? "SIM" : "não"}</td></tr>`).join("") + `</table>`
      : `<p class="neg">✖ Nenhum edge robusto encontrado (nenhuma condição com CI-inferior > 54% e n≥20).</p>`;
    $("relEdge").innerHTML = `
      <p class="small muted">${ed.n_sinais} sinais · break-even ${ed.breakeven}% · validação out-of-sample (treino 70% / teste 30%)</p>
      <b>Candidatos a edge</b> ${candHtml}
      <b>#3 Micro-estrutura — reversão após sequência de cor (n grande)</b>
      <table class="rep"><tr><th>após</th><th>reverte</th><th>conf. 95%</th><th>amostra</th></tr>${microRows}</table>
      <p class="muted small">Existe viés de reversão real (~52% após 4 velas), mas <b>abaixo dos 54%</b> de break-even.
      Seria lucrativo só com payout ≥ ~92%. Conclusão: sem edge vencível neste payout.</p>`;
  } else {
    $("relEdge").innerHTML = '<span class="muted">Edge Scanner não gerado ainda.</span>';
  }
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
