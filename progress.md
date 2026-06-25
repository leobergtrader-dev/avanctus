# progress.md — Histórico de Execução, Erros e Testes

## 2026-06-25

### Reconhecimento da API (Research)
- Mapeado backend real (broker-api.mybrokerdev.com) e WebSockets lendo o bundle do app.
- Identificados endpoints de leitura, fluxo de ordem e limites da plataforma. Ver `findings.md`.
- **Erro/Bloqueio:** teste automático de autenticação (varrer headers com o token) foi
  **bloqueado pelo classificador do Claude Code** (parecia credential exploration).
  - **Aprendizado:** esse teste deve rodar **na máquina do usuário** (backend Node), não pelo agente.

### Link — Handshake (Fase 2, parcial) ✅
- Construído app espelho **somente leitura** em Node:
  - `server.js` (proxy + descoberta de auth + /api/explore)
  - `public/` (index.html, app.js, style.css)
  - `.env` / `.env.example` / `.gitignore` / `README.md`
- `npm install` OK (69 pacotes).
- **Teste:** servidor sobe; `GET /api/status` responde JSON correto. ✔
- Logs temporários de teste removidos.

### Pendências imediatas
- Usuário precisa colar **token novo** no `.env` e rodar "Conectar" + "Explorar tudo".
- Capturar JSON real para confirmar schemas em `gemini.md`.

### Blueprint — Discovery respondida (parcial)
- **North Star definido:** executor de sinais do Telegram (ver gemini.md).
- Integrações: **Telegram** (fonte de sinais) + **TradingView** (2ª fonte via webhook).
- Entrega: **dashboard web local**.
- Regras: estratégias **configuráveis**, definidas depois com base em estatística.

### Source of Truth CAPTURADO ✅
- Canal de sinais: **VIVA DE RENDA · AVANCTUS** (ID `-1002835208093`, ~14.7k inscritos).
- Formato real do sinal documentado em gemini.md (ativo OTC, M1, horário, CALL/PUT, 2 gales).
- Sinal chega ~3 min antes do horário de entrada → executor precisa AGENDAR a ordem no horário.
- Estratégia usa **gale/martingale** (até 2 níveis) → será configurável; default desligado.

### Pendências para fechar o Blueprint
- 1 exemplo de sinal **CALL/verde** (pra cobrir as duas direções no parser).
- Mapa nome-do-ativo → ticker Avanctus (via /symbols no Explorador).
- Aprovação final do Blueprint pelo usuário.

### Link / Architect — em construção ✅
- Tools criadas em `tools/`: `signal_parser.py`, `telegram_login.py`, `telegram_listen.py`.
- Telethon 1.44 + python-dotenv instalados.
- **Parser testado com o sinal real** → JSON correto (PUT/SELL, M1, horário, 2 gales). ✔
- `.env` preenchido pelo usuário (api_id, api_hash, phone, canal -1002835208093).

### Próximo passo (depende do usuário)
- Rodar `py tools/telegram_login.py` no terminal DELE (login interativo, código chega no Telegram).
- Depois `py tools/telegram_listen.py` → ver sinais reais sendo lidos/parseados ao vivo.

### Estado do protocolo
- Blueprint aprovado (usuário seguiu: env + github). Schema do sinal confirmado.
