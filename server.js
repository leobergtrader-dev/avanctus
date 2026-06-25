// =====================================================================
//  TRADE IA - Painel Espelho (somente leitura)
//  Backend proxy para a API da Avanctus / mybroker (broker-api.mybrokerdev.com)
//
//  O que ele faz:
//   - Guarda o token de API no servidor (nunca exposto ao navegador)
//   - Descobre automaticamente em qual header o token autentica
//   - Proxia uma lista de endpoints de LEITURA (GET) e devolve o JSON real
//
//  Ele NÃO abre, fecha nem cancela nenhuma operação. É 100% leitura.
// =====================================================================

import express from "express";
import dotenv from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";

dotenv.config();

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();

const TOKEN = process.env.API_TOKEN || "";
const BASE_URL = (process.env.BASE_URL || "https://broker-api.mybrokerdev.com").replace(/\/$/, "");
const PORT = process.env.PORT || 3000;

// Header de autenticação que funcionou (descoberto em runtime e guardado aqui).
let authScheme = null; // ex.: { name: "api-token", build: (t) => ({ "api-token": t }) }

// Esquemas de autenticação candidatos. O app testa um a um até achar o que responde 200.
const AUTH_SCHEMES = [
  { name: "api-token",            build: (t) => ({ "api-token": t }) },
  { name: "Authorization Bearer", build: (t) => ({ Authorization: `Bearer ${t}` }) },
  { name: "x-api-token",          build: (t) => ({ "x-api-token": t }) },
  { name: "api-key",              build: (t) => ({ "api-key": t }) },
  { name: "x-api-key",            build: (t) => ({ "x-api-key": t }) },
  { name: "Authorization raw",    build: (t) => ({ Authorization: t }) },
];

// Endpoints SOMENTE LEITURA mapeados a partir do app da Avanctus.
// Como os caminhos foram deduzidos do código, alguns podem precisar de ajuste.
// Por isso o painel mostra o status de cada um — assim descobrimos o que é real.
const READ_ENDPOINTS = [
  { key: "perfil",        label: "Perfil / conta",        path: "/auth/me" },
  { key: "perfil2",       label: "Perfil (account)",      path: "/account/profile" },
  { key: "carteira",      label: "Carteira / saldo",      path: "/account/wallet" },
  { key: "seguranca",     label: "Segurança da conta",    path: "/account/security" },
  { key: "simbolos",      label: "Símbolos disponíveis",  path: "/symbols" },
  { key: "trades",        label: "Operações (histórico)", path: "/trades" },
  { key: "trades_info",   label: "Info de trades",        path: "/trades/info" },
  { key: "payout",        label: "Payout dos trades",     path: "/trades/payout" },
  { key: "api_tokens",    label: "Meus tokens de API",    path: "/user-api-tokens" },
  { key: "notificacoes",  label: "Notificações",          path: "/user-notifications" },
];

// Faz uma requisição GET na API usando um conjunto de headers.
async function apiGet(endpointPath, headers) {
  const url = BASE_URL + endpointPath;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json", ...headers },
      signal: controller.signal,
    });
    const text = await res.text();
    let body;
    try { body = JSON.parse(text); } catch { body = text.slice(0, 500); }
    return { ok: res.ok, status: res.status, body };
  } catch (err) {
    return { ok: false, status: 0, body: `erro de rede: ${err.message}` };
  } finally {
    clearTimeout(timer);
  }
}

// Descobre qual esquema de autenticação funciona, testando contra endpoints de perfil.
async function discoverAuth() {
  if (!TOKEN) return { ok: false, error: "API_TOKEN não configurado no arquivo .env" };

  const probePaths = ["/auth/me", "/account/profile"];
  for (const scheme of AUTH_SCHEMES) {
    for (const p of probePaths) {
      const headers = scheme.build(TOKEN);
      const r = await apiGet(p, headers);
      // Consideramos sucesso quando NÃO é 401/403 e veio um JSON (objeto).
      const looksAuthed = r.ok && typeof r.body === "object" && r.body !== null;
      if (looksAuthed) {
        authScheme = scheme;
        return { ok: true, scheme: scheme.name, via: p, sample: r.body };
      }
    }
  }
  return { ok: false, error: "Nenhum esquema de autenticação funcionou. Token inválido/expirado ou header diferente." };
}

// ---------------------- Rotas do painel ----------------------

// Status básico: token configurado? base? esquema descoberto?
app.get("/api/status", (req, res) => {
  res.json({
    tokenConfigurado: Boolean(TOKEN),
    tokenPreview: TOKEN ? TOKEN.slice(0, 3) + "•••" + TOKEN.slice(-2) : null,
    baseUrl: BASE_URL,
    authDescoberto: authScheme?.name || null,
  });
});

// Conecta = descobre o header de autenticação.
app.post("/api/connect", async (req, res) => {
  const result = await discoverAuth();
  res.status(result.ok ? 200 : 400).json(result);
});

// Explora todos os endpoints de leitura e devolve o resultado de cada um.
app.get("/api/explore", async (req, res) => {
  if (!authScheme) {
    return res.status(400).json({ error: "Conecte primeiro (descobrir autenticação)." });
  }
  const headers = authScheme.build(TOKEN);
  const results = {};
  for (const ep of READ_ENDPOINTS) {
    const r = await apiGet(ep.path, headers);
    results[ep.key] = { label: ep.label, path: ep.path, status: r.status, ok: r.ok, body: r.body };
  }
  res.json({ scheme: authScheme.name, results });
});

// Proxy genérico de leitura (para um caminho específico, só GET).
app.get("/api/get", async (req, res) => {
  if (!authScheme) return res.status(400).json({ error: "Conecte primeiro." });
  const p = String(req.query.path || "");
  if (!p.startsWith("/")) return res.status(400).json({ error: "path deve começar com /" });
  const r = await apiGet(p, authScheme.build(TOKEN));
  res.status(r.status || 502).json(r);
});

// Arquivos estáticos do frontend
app.use(express.static(path.join(__dirname, "public")));

app.listen(PORT, () => {
  console.log("\n  TRADE IA — Painel Espelho (somente leitura)");
  console.log(`  Rodando em:  http://localhost:${PORT}`);
  console.log(`  API base:    ${BASE_URL}`);
  console.log(`  Token:       ${TOKEN ? "configurado ✔" : "FALTANDO ✖  (preencha o .env)"}\n`);
});
