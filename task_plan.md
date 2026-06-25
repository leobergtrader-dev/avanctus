# task_plan.md — Plano por Fases (B.L.A.S.T.)

## Fase 0 — Initialization ✅
- [x] Criar memória de projeto (gemini.md, task_plan.md, findings.md, progress.md)
- [ ] **HALT** — aguardando Discovery Questions respondidas
- [ ] Blueprint aprovado pelo usuário

## Fase 1 — Blueprint (Vision & Logic) ⏳ EM ANDAMENTO
- [x] Discovery: North Star (executor de sinais TG), Integrations (Telegram; TV depois),
      Delivery (dashboard local), Behavioral (estratégias configuráveis)
- [x] Research: backend, endpoints e fluxo de ordem mapeados (ver findings.md)
- [ ] **Source of Truth: obter exemplos reais de sinais do grupo** → define schema do parser
- [ ] Confirmar Data Schema do sinal em `gemini.md`
- [ ] **Blueprint aprovado pelo usuário** (gate para sair do HALT)

## Pipeline alvo (Architect)
Telegram (Telethon) → Parser → Motor de Estratégia → Executor (Avanctus) → registra no Dashboard
- [ ] Tool: listener Telegram (handshake Link → também captura sinais reais)
- [ ] Tool: parser de sinal (determinístico, baseado no formato real)
- [ ] Tool: motor de estratégia (config-driven: agressivo ↔ comedido)
- [ ] Tool: executor de ordem na Avanctus (demo first) — só após leitura validada
- [ ] Kill switch no dashboard

## Fase 2 — Link (Connectivity)
- [x] Handshake construído: backend Node descobre auth + proxia endpoints de leitura
- [x] Servidor sobe e responde (`/api/status` OK)
- [ ] **Verificar com token real**: rodar "Conectar" + "Explorar tudo" e capturar JSON real
- [ ] Confirmar qual header autentica o token

## Fase 3 — Architect (3 camadas A.N.T.)
- [ ] Layer 1 (architecture/): SOPs em Markdown por tool
- [ ] Layer 2 (Navigation): roteamento de dados
- [ ] Layer 3 (tools/): scripts determinísticos atômicos
- [ ] Cards de Saldo e Histórico ligados ao JSON real
- [ ] Preços ao vivo (WebSocket)

## Fase 4 — Stylize (Refinement & UI)
- [ ] Refinar payload/UI do dashboard
- [ ] Apresentar para feedback antes do deploy

## Fase 5 — Trigger (Deployment)
- [ ] (Definir se haverá cloud/cron — depende do North Star)
- [ ] Maintenance Log em gemini.md
