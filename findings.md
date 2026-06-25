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

## Constraints de segurança / risco
- Plataforma OTC / opção binária = **altíssimo risco**. Automatizar não melhora a probabilidade.
- Recomendado embutir limites de proteção (perda diária, máx. trades) quando/se houver execução.
- Token de API é segredo (tratar como senha). O 1º token apareceu em tela → deve ser rotacionado.
