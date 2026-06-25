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

async function loadStatus() {
  const r = await fetch("/api/status").then((x) => x.json());
  $("baseUrl").textContent = r.baseUrl || "—";
  $("tokenPreview").textContent = r.tokenConfigurado ? r.tokenPreview : "FALTANDO no .env";
  $("authScheme").textContent = r.authDescoberto || "—";
  if (r.authDescoberto) {
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
      $("authScheme").textContent = r.scheme;
      connectMsg.className = "msg ok";
      connectMsg.textContent = `✔ Autenticado via header "${r.scheme}" (testado em ${r.via}).`;
      btnExplore.disabled = false;
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
