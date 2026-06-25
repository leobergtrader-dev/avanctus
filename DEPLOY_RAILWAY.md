# Deploy no Railway (rodar 24h na nuvem)

O Railway roda um **processo sempre ligado** (ideal pro nosso robô). O mesmo painel que
você usa local vai ficar online, com **senha**, acessível do celular.

## Pré-requisitos
- Conta no Railway (https://railway.app) — login com o GitHub.
- Nosso repositório já está no GitHub: `leobergtrader-dev/avanctus`.

## Passo 1 — Criar o projeto
1. No Railway: **New Project → Deploy from GitHub repo → selecione `avanctus`**.
2. Ele detecta Python (pelo `requirements.txt`) e usa o `Procfile` (`python tools/painel.py`).

## Passo 2 — Variáveis de ambiente (os segredos)
Em **Variables → Raw Editor**, cole o conteúdo abaixo **preenchendo os valores**
(copie os do seu `.env` local). **NÃO** inclua `PORT` (o Railway define sozinho).

```
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
TELEGRAM_GRUPO=-1002835208093
TELEGRAM_SESSION=
AVANCTUS_EMAIL=leobergtrader@gmail.com
AVANCTUS_PASSWORD=
AVANCTUS_2FA_SECRET=
TENANT_ID=01HZTB9FAN88DFM3T589J4FW17
CONTA_DEMO=true
ENTRY_AMOUNT=25
USE_GALE=false
MAX_GALE=2
GALE_FACTOR=2
ONE_AT_A_TIME=true
MAX_TRADES_DAY=60
HORARIOS_PERMITIDOS=
STOP_WIN_DIA=200
STOP_LOSS_DIA=300
STOP_LOSS_SEMANA=800
MAX_PERDAS_SEGUIDAS=3
DEGRAD_JANELA=30
BREAKEVEN=0.54
SIZING=flat
KELLY_FRACAO=0.25
PAYOUT=0.85
BANCA=10000
MIN_STAKE=5
MAX_STAKE=200
KELLY_MIN_AMOSTRA=100
EDGE_MIN_AMOSTRA=100
PAINEL_USUARIO=leo
PAINEL_SENHA=ESCOLHA_UMA_SENHA_FORTE
```

> `PAINEL_SENHA` é a senha pra abrir o painel online. Escolha uma forte — sem ela,
> qualquer um com o link controlaria suas operações.

## Passo 3 — Persistir os dados (operações/estatística)
1. No serviço: **Settings → Volumes → New Volume**.
2. Mount path: **`/app/.tmp`**
   (assim `operacoes.csv` e o cache do login sobrevivem a cada novo deploy.)

## Passo 4 — Publicar e acessar
1. **Settings → Networking → Generate Domain** (cria a URL pública).
2. Abra a URL → o navegador vai pedir **usuário e senha** (os do Passo 2).
3. Confira o card **Login** = OK e clique **▶ Ligar**.

## Observações importantes
- **Conta DEMO** por padrão (`CONTA_DEMO=true`). Real só com decisão sua + edge-gate liberado.
- **Login de IP de datacenter:** a corretora pode sinalizar login de local novo. Se houver bloqueio,
  a gente trata (ex.: confirmar o acesso, ou usar proxy). Começar em demo reduz risco.
- O Telegram pode te avisar de "novo acesso" (o robô usa sua sessão) — é esperado.
- Custo: ~US$5/mês (plano Hobby) após o crédito inicial.
