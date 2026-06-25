# findings.md — Pesquisa, Descobertas e Constraints

## Origem da plataforma
- **Avanctus** (`app.avanctus.com`) é um **white-label** da engine **mybroker / asapcode**.
- Frontend é um SPA (React/Vite). Bundle: `/new/assets/index-*.js`.

## Infra (extraída do bundle JS)
| Componente | Endereço |
|---|---|
| REST API | `https://broker-api.mybrokerdev.com` |
| WebSocket de trade | `wss://broker-api-websocket-proxy.asapcode.workers.dev` |
| WebSocket de preços | `wss://symbol-ws.mybrokerdev.com` |
| Agregador de preços | `https://symbol-prices-aggregator.mybrokerdev.com` (header `api-key` de tenant) |

## Autenticação
- Site loga via `POST /auth/login` (e-mail+senha, 2FA opcional) → **Bearer JWT**.
- Sistema de tokens de automação: `/user-api-tokens` (index/create/delete). É o token gerado no painel.
- Headers vistos no código: `Authorization` (Bearer), `api-token`, `api-key`, `x-api-key`.
- **CONSTRAINT:** o header exato do token de automação ainda **não confirmado** (teste real pendente).

## Fluxo de ordem (opção binária) — INFERIDO
- Via WebSocket: emite `buy` → respostas `buy-success` / `buy-failed` / `order-created` / `order-error`.
- Params: `amount`, `direction` (`BUY`/`SELL`), `isDemo`, `expirationType`/`closeType`, `symbol`.

## Limites/regras que a API impõe (das mensagens de erro do app)
- saldo insuficiente; valor mínimo e máximo por trade
- limite de trades por minuto; por dia; máx. trades pendentes
- "preço desatualizado"; "símbolo não ativo para abrir trade"
- recursos extras existentes: **futures**, **copy-trade**, **profit-zone**, **digits**

## Endpoints de leitura candidatos (a confirmar)
`/auth/me`, `/account/profile`, `/account/wallet`, `/account/security`,
`/symbols`, `/trades`, `/trades/info`, `/trades/payout`, `/user-api-tokens`, `/user-notifications`

## Candles (gráfico) — endpoint descoberto ✅
- O chart é TradingView (datafeed UDF, iframe). Endpoint de candles:
  `GET https://symbol-prices-aggregator.mybrokerdev.com/aggregated-prices/prices`
  header `api-key: Sl293kk22ss8` · params: `slot=default, pair=<ticker>, startTime, endTime(ms),
  type=otc, interval=1m, skip, limit`. Retorna OHLCV: {time, openPrice, closePrice, highPrice, lowPrice, volume}.
- WS de preço (`/ws`) usa protocolo {type:<acao>} desconhecido — não precisamos: REST de candles resolve.

## Integração Telegram (decisão: grupo de terceiros)
- O usuário só participa do grupo → **Bot API não funciona** (bots não leem grupos de terceiros).
- Solução: **userbot MTProto** (login como o usuário). Libs: **Telethon** (Python, padrão-ouro)
  ou GramJS (Node).
- **Credenciais necessárias:** `api_id` + `api_hash` de https://my.telegram.org (App configuration)
  + login (telefone → código) que gera uma **session string** reutilizável.
- **CONSTRAINT legal/ToS:** automação MTProto é tolerada para uso pessoal, mas envio em massa/spam
  viola os termos. Uso aqui = ler sinais de um grupo que o usuário já acompanha (uso pessoal).
- **Arquitetura provável:** listener Python (Telethon) → entrega sinal parseado → executor.
  Decidir na fase Architect se executor fica em Node (já temos a camada Avanctus) ou Python.

## TradingView
- Adiado. Entrará como 2ª fonte (webhook) numa fase futura, se desejado.

## Estatística do canal (auto-reportada) — 25/05 a 25/06 (32 dias)
- 427 operações, **89,0% declarado** (todas PUT). Por ativo: CARDANO 95%, SOLANA 91%, BTC 88%, XRP 84%.
- **CRÍTICO (análise matemática):** 89% é por SEQUÊNCIA (entrada + gales). Se 3 tentativas dão 89%,
  a taxa por ENTRADA implícita é ~52% → **abaixo do break-even (54%)**.
- EV com p=52%, payout 85%, gale 25/50/100 ≈ **−$2,74 por sinal** (a derrota total de 11% = −$175
  devora os ganhos). Martingale com p<break-even é NEGATIVO mesmo "ganhando" 89%.
- **Regra de ouro:** se taxa/entrada > 54% → lucra SEM gale; se < 54% → gale não resolve.
  ⇒ medir a taxa REAL por entrada na demo (FLAT, sem gale) é o que decide tudo.

## Constraints de segurança / risco
- Plataforma OTC / opção binária = **altíssimo risco**. Automatizar não melhora a probabilidade.
- Recomendado embutir limites de proteção (perda diária, máx. trades) quando/se houver execução.
- Token de API é segredo (tratar como senha). O 1º token apareceu em tela → deve ser rotacionado.
