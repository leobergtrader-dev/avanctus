// =====================================================================
//  TRADE IA - Painel Espelho (somente leitura)
//  Autentica como o site da Avanctus: Bearer JWT + x-tenant-id.
//
//  De onde vem a autenticacao (nesta ordem):
//   1) .env  -> AUTH_BEARER + TENANT_ID
//   2) .tmp/captura.txt  -> extrai do "Copy as cURL" colado pelo usuario
//
//  O JWT expira (~48h). Para 24h reais, faremos login automatico depois.
//  Este painel so LE dados. Nao abre/fecha/cancela nada.
// =====================================================================

import express from "express";
import dotenv from "dotenv";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

dotenv.config();

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();

const BASE_URL = (process.env.BASE_URL || "https://broker-api.mybrokerdev.com").replace(/\/$/, "");
const PORT = process.env.PORT || 3000;
const ORIGIN = "https://app.avanctus.com";
const CAPTURE_PATH = path.join(__dirname, ".tmp", "captura.txt");

let connected = false;       // virou true depois de validar /auth/me
let profile = null;          // dados do /auth/me

// Le Bearer + tenant do .env ou da captura do navegador.
function loadAuth() {
  let bearer = (process.env.AUTH_BEARER || "").trim();
  let tenant = (process.env.TENANT_ID || "").trim();
  if ((!bearer || !tenant) && fs.existsSync(CAPTURE_PATH)) {
    const txt = fs.readFileSync(CAPTURE_PATH, "utf8");
    const b = txt.match(/authorization:\s*Bearer\s+([A-Za-z0-9._\-]+)/i);
    const t = txt.match(/x-tenant-id:\s*([A-Za-z0-9]+)/i);
    if (!bearer && b) bearer = b[1];
    if (!tenant && t) tenant = t[1];
  }
  return { bearer, tenant };
}

function authHeaders() {
  const { bearer, tenant } = loadAuth();
  if (!bearer || !tenant) return null;
  return {
    Authorization: `Bearer ${bearer}`,
    "x-tenant-id": tenant,
    Origin: ORIGIN,
    Referer: ORIGIN + "/",
    Accept: "application/json, text/plain, */*",
  };
}

// Decodifica o payload do JWT (nao e segredo decodificar) p/ saber validade/nome.
function jwtInfo(bearer) {
  try {
    const payload = JSON.parse(Buffer.from(bearer.split(".")[1], "base64").toString("utf8"));
    return {
      nome: payload.name,
      expira_em: payload.exp ? new Date(payload.exp * 1000).toISOString() : null,
      expirado: payload.exp ? payload.exp * 1000 < Date.now() : null,
    };
  } catch {
    return null;
  }
}

const AGGREGATOR = "https://symbol-prices-aggregator.mybrokerdev.com";

// Endpoints de LEITURA reais. Alguns pedem params; simbolos vem de outro host.
const READ_ENDPOINTS = [
  { key: "perfil",     label: "Perfil (auth/me)",      path: "/auth/me" },
  { key: "tenant",     label: "Config do tenant",      path: "/tenant-config" },
  { key: "trades_info",label: "Info de trades",        path: "/trades/info" },
  { key: "wallets",    label: "Carteiras cripto",      path: "/user-wallets/crypto" },
  { key: "trades",     label: "Operacoes (historico)", path: "/trades", params: { page: 1, limit: 20 } },
  { key: "payout",     label: "Payout dos trades",     path: "/trades/payout" },
  { key: "symbols",    label: "Simbolos (aggregator)", path: "/symbols", base: AGGREGATOR,
                       params: { active: true }, headers: { "api-key": "Sl293kk22ss8" } },
];

async function apiGet(endpointPath, headers, opts = {}) {
  const base = (opts.base || BASE_URL).replace(/\/$/, "");
  let url = base + endpointPath;
  if (opts.params) {
    const qs = new URLSearchParams(opts.params).toString();
    url += (url.includes("?") ? "&" : "?") + qs;
  }
  const hdrs = { ...headers, ...(opts.headers || {}) };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const res = await fetch(url, { method: "GET", headers: hdrs, signal: controller.signal });
    const text = await res.text();
    let body;
    try { body = JSON.parse(text); } catch { body = text.slice(0, 400); }
    return { ok: res.ok, status: res.status, body };
  } catch (err) {
    return { ok: false, status: 0, body: `erro de rede: ${err.message}` };
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------- Rotas ----------------------

app.get("/api/status", (req, res) => {
  const { bearer, tenant } = loadAuth();
  res.json({
    baseUrl: BASE_URL,
    temAuth: Boolean(bearer && tenant),
    tenant: tenant || null,
    jwt: bearer ? jwtInfo(bearer) : null,
    conectado: connected,
  });
});

// Conectar = validar o JWT chamando /auth/me
app.post("/api/connect", async (req, res) => {
  const headers = authHeaders();
  if (!headers) {
    return res.status(400).json({ ok: false, error: "Sem autenticacao. Cole a captura em .tmp/captura.txt ou preencha AUTH_BEARER+TENANT_ID no .env." });
  }
  const r = await apiGet("/auth/me", headers);
  if (r.ok && typeof r.body === "object") {
    connected = true;
    profile = r.body;
    return res.json({ ok: true, perfil: r.body });
  }
  connected = false;
  const dica = r.status === 401 ? " (JWT expirou? Capture de novo no navegador.)" : "";
  res.status(400).json({ ok: false, error: `Falha ao validar (status ${r.status})${dica}`, body: r.body });
});

// Explora os endpoints de leitura reais
app.get("/api/explore", async (req, res) => {
  const headers = authHeaders();
  if (!headers) return res.status(400).json({ error: "Conecte primeiro." });
  const results = {};
  for (const ep of READ_ENDPOINTS) {
    const r = await apiGet(ep.path, headers, { base: ep.base, params: ep.params, headers: ep.headers });
    results[ep.key] = { label: ep.label, path: ep.path, status: r.status, ok: r.ok, body: r.body };
  }
  // Salva o JSON real em .tmp para análise (ajuda a calibrar o sistema).
  try {
    fs.mkdirSync(path.join(__dirname, ".tmp"), { recursive: true });
    fs.writeFileSync(path.join(__dirname, ".tmp", "explore.json"), JSON.stringify(results, null, 2), "utf8");
  } catch {}
  res.json({ results });
});

// Proxy de leitura para um caminho especifico (GET)
app.get("/api/get", async (req, res) => {
  const headers = authHeaders();
  if (!headers) return res.status(400).json({ error: "Sem autenticacao." });
  const p = String(req.query.path || "");
  if (!p.startsWith("/")) return res.status(400).json({ error: "path deve comecar com /" });
  const r = await apiGet(p, headers);
  res.status(r.status || 502).json(r);
});

app.use(express.static(path.join(__dirname, "public")));

app.listen(PORT, () => {
  const { bearer, tenant } = loadAuth();
  console.log("\n  TRADE IA - Painel Espelho (somente leitura)");
  console.log(`  http://localhost:${PORT}`);
  console.log(`  Auth: ${bearer && tenant ? "JWT + tenant carregados (" + tenant + ")" : "FALTANDO (.tmp/captura.txt)"}\n`);
});
