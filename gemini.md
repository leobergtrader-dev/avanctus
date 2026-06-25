# gemini.md — Project Constitution (LAW)

> Este arquivo é **lei**. Os demais (`task_plan.md`, `findings.md`, `progress.md`) são **memória**.
> Só atualize aqui quando: um schema mudar, uma regra for adicionada, ou a arquitetura mudar.

## Projeto
**TRADE IA** — automação para operar a corretora **Avanctus** (engine white-label *mybroker*).
Fase atual: **1 — Espelho (somente leitura), conta DEMO** (validação antes de executar).

## North Star (objetivo máximo)
Receber **sinais prontos de um grupo do Telegram**, **interpretar** cada sinal, aplicar uma
**estratégia configurável** (regras de risco/estatística definidas com o usuário) e **executar a
operação na Avanctus**. **TradingView** pode ser uma 2ª fonte de sinal (webhook). Entrega/controle
num **dashboard web local**.

Pipeline alvo:
`Telegram (sinal) → Parser → Motor de Estratégia (filtros/risco) → Executor (ordem) → Avanctus`
`Dashboard ← monitora tudo`

## Architectural Invariants (não podem ser violados)
1. **Validação read-only antes de executar.** A execução só é ligada após a leitura estar confirmada.
2. **Token nunca chega ao frontend.** Vive só no `.env` e no processo servidor.
3. **DEMO antes de REAL.** `isDemo=true` é o default; conta real exige decisão explícita do usuário
   E um período de validação em demo com resultados registrados.
4. **Business logic é determinística.** O parser e o motor de estratégia são regras explícitas,
   não "achismo" de LLM. Nenhuma ordem é inventada — toda ordem vem de um sinal + regra.
5. **Kill switch.** Sempre deve existir um jeito de parar tudo imediatamente (botão no dashboard).
6. **Self-Annealing:** todo erro corrigido vira aprendizado registrado em `architecture/`.
7. **Sem PII em arquivo.** CPF e documentos do usuário não são gravados no projeto.

## Behavioral Rules / Estratégia (definida com o usuário) — config-driven (.env)
**Fundação:** o jogo só é +EV se a taxa REAL por entrada > break-even (~54% p/ payout 85%).
Gestão de risco protege/otimiza vantagem, NÃO cria vantagem. Por isso: medir na demo (flat) primeiro.

Regras ativas (módulo tools/risk.py, derivado de .tmp/operacoes.csv):
1. **Filtro de horário** (`HORARIOS_PERMITIDOS`): opera só nas janelas escolhidas (após dados).
2. **Limites diários/semanais** (`STOP_WIN_DIA`, `STOP_LOSS_DIA`, `STOP_LOSS_SEMANA`): atingiu → para.
3. **Disciplina de capital:** float de trabalho no broker = N×custo máx/sinal; sacar acima, cadência
   semanal (saque exige KYC; evitar saca/redeposita frequente — chama atenção).
4. **Edge-gate** (`EDGE_MIN_AMOSTRA`): conta REAL só se demo tiver amostra suficiente e acerto>break-even.
5. **Sizing** (`SIZING=flat|kelly`): flat na medição; Kelly fracionário (ótimo) após validar vantagem.
6. **Circuit breaker** (`MAX_PERDAS_SEGUIDAS`): pausa o dia após N sequências perdidas seguidas.
7. **Stop por degradação** (`DEGRAD_JANELA`,`BREAKEVEN`): pausa se acerto recente cair < break-even.
- Gale: desligado por padrão na fase de medição (a matemática mostrou EV<0 com p~52%).

## Data Schemas

### Schema do SINAL (Input ← Telegram) — **CONFIRMADO (1 exemplo real)**
Fonte: canal **VIVA DE RENDA · AVANCTUS** (ID `-1002835208093`).

Exemplo bruto recebido:
```
📊 Corretora: Avanctus
🕐 1 Minutos de OPERAÇÃO
SOLANA (OTC) - 15:49 PUT 🔴
⏰ TERMINA EM: 15:50h
1º GALE: TERMINA EM: 15:51h
2º GALE: TERMINA EM: 15:52h
```

Shape parseado (output do parser):
```json
{
  "corretora": "Avanctus",
  "ativo_texto": "SOLANA (OTC)",
  "ativo_ticker": "SOLUSDT.OTC",   // resolvido via mapa nome->ticker (de /symbols)
  "expiracao_min": 1,
  "horario_entrada": "15:49",
  "direcao": "PUT",                // "CALL" = COMPRA/alta | "PUT" = VENDA/baixa
  "fim_principal": "15:50",
  "gales": ["15:51", "15:52"],     // níveis de martingale (0..2)
  "origem": "telegram:-1002835208093"
}
```
> PENDENTE: confirmar 1 exemplo de **CALL** (verde) e variações de ativo para robustez do parser.
> PENDENTE: mapa "nome do ativo" -> ticker da Avanctus (construir a partir de /symbols).

### Regra de GALE / Martingale (decisão de estratégia)
- Sinal traz até 2 gales. Entrar no gale é OPCIONAL e CONFIGURÁVEL (é o fator de maior risco).
- Default seguro: **gale desligado** (só entrada principal) até validarmos estatística em demo.

### Endpoints mapeados (a CONFIRMAR via Explorador da API)
| Recurso | Método | Caminho | Status |
|---|---|---|---|
| Perfil | GET | `/auth/me` | a confirmar |
| Perfil (alt) | GET | `/account/profile` | a confirmar |
| Carteira/saldo | GET | `/account/wallet` | a confirmar |
| Símbolos | GET | `/symbols` | a confirmar |
| Histórico de trades | GET | `/trades` | a confirmar |
| Tokens de API | GET | `/user-api-tokens` | a confirmar |

### Schema de Ordem (Output → API) — **CONFIRMADO no bundle**
- **Endpoint:** `POST /trades/open-async`  (auth: Bearer JWT + x-tenant-id + Origin)
- **Corpo:**
```json
{
  "symbol": "SOLUSDT.OTC",        // ticker do mapa oficial (tools/symbols_otc.json)
  "amount": 10,
  "direction": "BUY",             // "BUY" (CALL/alta) | "SELL" (PUT/baixa)
  "isDemo": true,                 // true = conta DEMO (controla a conta; sem wallet id)
  "expirationType": "CANDLE_CLOSE", // CANDLE_CLOSE | TIME_FIXED | NEXT_CANDLE
  "closeType": "01:00",           // duração: "00:30"=30s, "01:00"=1m, "05:00"=5m, "15:00"=15m
  "nitro": false
}
```
- Para os sinais do canal (ex.: "1 Minuto", CANDLE_CLOSE): `closeType="01:00"`, `expirationType="CANDLE_CLOSE"`.

### Schema de Saldo/Conta (Input ← /auth/me) — CONFIRMADO
- `wallets[]` traz: `{type:"REAL"|"BONUS"|"DEMO", id, balance}`. DEMO inicia em 10000.
- Histórico de operações: `GET /trades?page&limit`. Estatísticas: `GET /trades/info`.
- Recarregar demo: `POST users/recharge-demo-balance`.

## Deployment (decisão de arquitetura)
- **Motor (Telegram listener + estratégia + executor) exige processo SEMPRE LIGADO.**
  Vercel/serverless **NÃO serve** (não mantém conexão persistente do userbot). 
- Fases: **agora** roda no PC do usuário (`.bat`); **produção 24h** = VPS sempre-ligado
  (Railway/Render/Fly/VPS Linux), nunca Vercel.
- **Dashboard** (frontend estático) pode ficar no Vercel (`avanctus.vercel.app`) só pra exibição.
- **INVARIANTE:** segredos (token/api_hash) e o executor NUNCA num endpoint público sem autenticação.
  Hoje o deploy do Vercel está inofensivo porque está sem `.env` (não consegue operar).

## Autenticação REAL (descoberto via diagnóstico + bundle) — DECIDIDO
- **O "API Token" da Avanctus NÃO autentica a API REST.** Diagnóstico: 401 em todos os 10 headers,
  com token novo. Recurso inativo/para outro fim no white-label. ABANDONADO.
- **Auth real (interceptor do app):** `Authorization: Bearer <JWT>` **+** `x-tenant-id: <id>`.
  - JWT vem de `POST /auth/login` (email+senha, +2FA), enviado com `Origin: https://app.avanctus.com`.
  - `x-tenant-id` identifica o tenant Avanctus (white-label multi-inquilino).
  - Sem `x-tenant-id`, endpoints dão 401/404 (ex.: /symbols deu 404 sem ele).
- **Caminhos reais (do bundle):** `/symbols`, `/trades`, `/trades/info`, `/trades/payout`,
  `/futures`, `/digits`, `/user-wallets/crypto`, `/tenant-config`, `/auth/me`, `/auth/login`.
  (Os que eu havia chutado — /account/profile, /account/wallet — não existem.)
- **Login automático (24h) — IMPLEMENTADO:** `POST /auth/login` {email, password} (+ `token`=código
  se 2FA), headers Origin + x-tenant-id. Resposta traz `token` (JWT). Cache em `.tmp/jwt.json`,
  renova sozinho ao expirar ou em 401. Suporta 2FA via TOTP (AVANCTUS_2FA_SECRET + pyotp).
  Config: AVANCTUS_EMAIL/PASSWORD/2FA_SECRET, TENANT_ID no .env (gitignored).
- **SEGREDO:** .env (senha) e .tmp/jwt.json (JWT) nunca vão ao git.
- **/auth/login exige no corpo:** email, password, **tenantId** (string), **recaptchaToken** (string).
  DESCOBERTA: o `recaptchaToken` **NÃO é verificado** pelo servidor — um valor qualquer ("x") passa.
  ⇒ **login automático 24h funciona sem resolver captcha.** Sem endpoint de refresh; re-loga ao expirar.
- get_bearer reaproveita JWT válido (cache/captura) antes de logar (evita logins desnecessários).

## Infra descoberta
- REST: `https://broker-api.mybrokerdev.com`
- WS trade: `wss://broker-api-websocket-proxy.asapcode.workers.dev`
- WS preços: `wss://symbol-ws.mybrokerdev.com`
- Agregador preços: `https://symbol-prices-aggregator.mybrokerdev.com` (api-key de tenant)

## Maintenance Log
- _(vazio — preenchido na fase Trigger)_
