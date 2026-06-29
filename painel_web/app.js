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
    $("whatsBadge").className = "badge " + (s.whatsapp_ok ? "badge-on" : "badge-off");
    $("whatsBadge").textContent = s.whatsapp_ok ? "WhatsApp ligado" : "WhatsApp —";
  } catch (e) {}
}

async function refreshLog() {
  try {
    const lines = await api("/api/log");
    $("log").innerHTML = lines.length
      ? lines.map((l) => l.replace(/</g, "&lt;")).join("<br>")
      : '<span class="muted">Sem atividade ainda. O sistema rebalanceia 1×/dia.</span>';
  } catch (e) {}
}

// ---- Momentum (forward-test) ----
async function carregarExecutor() {
  try {
    const s = await api("/api/executor");
    if (s.erro) { $("execResumo").innerHTML = `<span class="neg">${s.erro}</span>`; return; }
    const last = s.hist && s.hist.length ? s.hist[s.hist.length - 1] : null;
    const eq = last ? last.equity : 1000;
    const ret = ((eq / 1000 - 1) * 100).toFixed(2);
    const pos = Object.keys(s.posicoes || {}).length;
    $("execResumo").innerHTML = `
      <div class="row">
        <div><div class="muted">Banca-papel</div><div class="big">${money(eq)}</div></div>
        <div><div class="muted">Retorno</div><div class="big">${signed(ret)}%</div></div>
        <div><div class="muted">Caixa</div><div class="big">${money(s.cash)}</div></div>
        <div><div class="muted">Posições</div><div class="big">${pos}</div></div>
        <div><div class="muted">Dias</div><div class="big">${(s.hist || []).length}</div></div>
      </div>
      ${pos ? `<p class="small muted">Comprado: ${Object.keys(s.posicoes).join(", ")}</p>`
            : '<p class="small muted">100% em caixa — mercado em baixa, estratégia protegendo o capital.</p>'}`;
  } catch (e) { $("execResumo").innerHTML = `<span class="neg">erro: ${e.message}</span>`; }
}

// ---- Grid (forward-test) ----
async function carregarGrid() {
  try {
    const s = await api("/api/grid");
    if (s.erro) { $("gridResumo").innerHTML = `<span class="neg">${s.erro}</span>`; return; }
    const last = s.hist && s.hist.length ? s.hist[s.hist.length - 1] : null;
    const eq = last ? last.equity : 1000;
    const ret = ((eq / 1000 - 1) * 100).toFixed(2);
    $("gridResumo").innerHTML = `
      <div class="row">
        <div><div class="muted">Banca-papel</div><div class="big">${money(eq)}</div></div>
        <div><div class="muted">Retorno</div><div class="big">${signed(ret)}%</div></div>
        <div><div class="muted">Caixa</div><div class="big">${money(s.cash)}</div></div>
        <div><div class="muted">Degraus comprados</div><div class="big">${s.niveis_comprados}/20</div></div>
        <div><div class="muted">Dias</div><div class="big">${(s.hist || []).length}</div></div>
      </div>
      ${s.parado ? `<p class="small neg">🛑 Parou pelo stop (caiu +${s.stop_pct || 10}%). Vendeu tudo, esperando o mercado virar.</p>`
        : s.niveis_comprados ? `<p class="small muted">Operando o vai-e-vem em ${s.niveis_comprados} degraus (compra na baixa, vende no repique).</p>`
                          : '<p class="small muted">Sem posições — esperando o preço cruzar os degraus.</p>'}`;
  } catch (e) { $("gridResumo").innerHTML = `<span class="neg">erro: ${e.message}</span>`; }
}

$("btnExec").onclick = async () => {
  $("btnExec").textContent = "Rebalanceando…"; $("btnExec").disabled = true;
  try {
    const r = await api("/api/executor/run", { method: "POST" });
    if (r.erro) alert("Erro: " + r.erro);
    else if (r.ordens && r.ordens.length) alert(`Executou ${r.ordens.length} ordem(ns). Banca: ${money(r.equity)}`);
    else alert("Sem ordens (já na carteira-alvo ou tudo em caixa).");
    carregarExecutor();
  } catch (e) { alert("erro: " + e.message); }
  finally { $("btnExec").textContent = "Rebalancear agora"; $("btnExec").disabled = false; }
};

$("btnWhats").onclick = async () => {
  $("btnWhats").disabled = true;
  try {
    const r = await api("/api/notify/test", { method: "POST" });
    alert(r.ok ? "✅ Enviado! Confira seu WhatsApp." : "✖ Não enviou: " + (r.motivo || r.resp || "verifique a config"));
  } catch (e) { alert("erro: " + e.message); }
  finally { $("btnWhats").disabled = false; }
};

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
      <p class="muted small">"Tamanho" = fração da banca por moeda (vol targeting). Caixa = fora do mercado.</p>`;
  } catch (e) { $("estratCarteira").innerHTML = "Erro: " + e.message; }
  finally { $("btnEstrat").textContent = "Atualizar"; $("btnEstrat").disabled = false; }
};

// ---- Abas ----
const ABAS = { tabForward: "view-forward", tabEstrategia: "view-estrategia" };
function trocarAba(ativo) {
  for (const [tab, view] of Object.entries(ABAS)) {
    $(view).style.display = tab === ativo ? "" : "none";
    $(tab).classList.toggle("active", tab === ativo);
  }
}
$("tabForward").onclick = () => { trocarAba("tabForward"); carregarExecutor(); carregarGrid(); };
$("tabEstrategia").onclick = () => trocarAba("tabEstrategia");

function tick() { refreshStatus(); refreshLog(); carregarExecutor(); carregarGrid(); }
tick();
setInterval(refreshStatus, 10000);
setInterval(refreshLog, 5000);
