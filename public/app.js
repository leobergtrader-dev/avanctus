// Frontend do painel espelho. Só conversa com o nosso backend (/api/*),
// nunca direto com a corretora — e o token nunca chega aqui.

const $ = (id) => document.getElementById(id);

const badge = $("statusBadge");
const btnConnect = $("btnConnect");
const btnExplore = $("btnExplore");
const explorer = $("explorer");
const connectMsg = $("connectMsg");

function setBadge(state, text) {
  badge.className = "badge " + (state === "on" ? "badge-on" : state === "err" ? "badge-err" : "badge-off");
  badge.textContent = text;
}

function fmtExp(jwt) {
  if (!jwt || !jwt.expira_em) return "—";
  const d = new Date(jwt.expira_em);
  const txt = d.toLocaleString("pt-BR");
  return jwt.expirado ? `EXPIRADO (${txt})` : `válido até ${txt}`;
}

async function loadStatus() {
  const r = await fetch("/api/status").then((x) => x.json());
  $("baseUrl").textContent = r.baseUrl || "—";
  $("tokenPreview").textContent = r.tenant || "FALTANDO (.tmp/captura.txt)";
  $("authScheme").textContent = r.temAuth ? fmtExp(r.jwt) : "—";
  if (r.conectado) {
    setBadge("on", "conectado");
    btnExplore.disabled = false;
  }
}

btnConnect.addEventListener("click", async () => {
  connectMsg.textContent = "Descobrindo autenticação…";
  connectMsg.className = "msg";
  btnConnect.disabled = true;
  try {
    const r = await fetch("/api/connect", { method: "POST" }).then((x) => x.json());
    if (r.ok) {
      setBadge("on", "conectado");
      const nome = r.perfil?.name || r.perfil?.email || "conta";
      connectMsg.className = "msg ok";
      connectMsg.textContent = `✔ Conectado como ${nome}.`;
      btnExplore.disabled = false;
      loadStatus();
    } else {
      setBadge("err", "falha");
      connectMsg.className = "msg err";
      connectMsg.textContent = "✖ " + (r.error || "Não foi possível autenticar.");
    }
  } catch (e) {
    setBadge("err", "erro");
    connectMsg.className = "msg err";
    connectMsg.textContent = "✖ Erro de rede: " + e.message;
  } finally {
    btnConnect.disabled = false;
  }
});

btnExplore.addEventListener("click", async () => {
  btnExplore.disabled = true;
  btnExplore.textContent = "Explorando…";
  explorer.innerHTML = "";
  try {
    const r = await fetch("/api/explore").then((x) => x.json());
    if (r.error) {
      explorer.innerHTML = `<div class="msg err">${r.error}</div>`;
      return;
    }
    for (const key of Object.keys(r.results)) {
      explorer.appendChild(renderEndpoint(r.results[key]));
    }
  } catch (e) {
    explorer.innerHTML = `<div class="msg err">Erro: ${e.message}</div>`;
  } finally {
    btnExplore.disabled = false;
    btnExplore.textContent = "Explorar tudo";
  }
});

// Mostra o diagnóstico de autenticação: status sem-auth de cada endpoint
// e o melhor (menor) status obtido por cada esquema de header.
function renderDiag(r) {
  const diag = document.getElementById("diag");
  if (!r || !r.attempts) { diag.innerHTML = ""; return; }

  // baseline por endpoint
  let html = '<div class="diag-box"><h3>Diagnóstico (sem autenticação)</h3><table class="diag">';
  html += "<tr><th>endpoint</th><th>status sem-auth</th></tr>";
  for (const p of Object.keys(r.baseline || {})) {
    html += `<tr><td class="mono">${p}</td><td class="mono">${r.baseline[p]}</td></tr>`;
  }
  html += "</table>";

  // melhor status por esquema (queremos achar algum 200/2xx)
  const best = {};
  const sample = {};
  for (const a of r.attempts) {
    if (best[a.scheme] === undefined || a.status < best[a.scheme]) {
      best[a.scheme] = a.status;
    }
    if (a.status >= 200 && a.status < 300) sample[a.scheme] = `${a.path} → ${a.preview}`;
  }
  html += '<h3>Por esquema de header (menor status obtido)</h3><table class="diag">';
  html += "<tr><th>header</th><th>melhor status</th></tr>";
  for (const s of Object.keys(best)) {
    const hit = best[s] >= 200 && best[s] < 300;
    html += `<tr><td class="mono">${s}</td><td class="mono ${hit ? "good" : "bad"}">${best[s]}${hit ? " ✓" : ""}</td></tr>`;
  }
  html += "</table>";
  if (Object.keys(sample).length) {
    html += "<p class='small muted'>Respostas 2xx encontradas — provável header correto acima.</p>";
  }
  html += "</div>";
  diag.innerHTML = html;
}

function renderEndpoint(ep) {
  const wrap = document.createElement("div");
  wrap.className = "ep";
  const ok = ep.ok;
  wrap.innerHTML = `
    <div class="ep-head">
      <span class="dot ${ok ? "ok" : "err"}"></span>
      <span class="ep-label">${ep.label}</span>
      <span class="ep-path mono">${ep.path}</span>
      <span class="ep-status">${ep.status || "—"}</span>
    </div>
    <div class="ep-body">
      <pre>${escapeHtml(JSON.stringify(ep.body, null, 2))}</pre>
    </div>`;
  wrap.querySelector(".ep-head").addEventListener("click", () => wrap.classList.toggle("open"));
  return wrap;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

loadStatus();
