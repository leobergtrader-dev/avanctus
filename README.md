# TRADE IA — Painel Espelho (somente leitura)

Painel local que conecta na API da sua corretora (Avanctus / engine *mybroker*) e
**apenas lê** dados: perfil, saldo, símbolos e histórico. **Não abre, fecha nem
cancela nenhuma operação.** É a fase 1, segura, para validar a conexão.

## Arquitetura

```
navegador  ─►  backend Node (server.js)  ─►  broker-api.mybrokerdev.com
 (tela)         guarda o token + proxy           (API da corretora)
```

O token fica **só no servidor** (arquivo `.env`), nunca vai para o navegador.

## Como rodar

1. **Coloque seu token** no arquivo `.env`:
   ```
   API_TOKEN=seu_token_aqui
   ```
   > Dica de segurança: crie um token NOVO em `app.avanctus.com → API`, já que o
   > anterior foi exibido em tela.

2. **Instale as dependências** (uma vez só):
   ```powershell
   npm install
   ```

3. **Inicie o painel**:
   ```powershell
   npm start
   ```

4. Abra no navegador: **http://localhost:3000**

5. Clique em **Conectar** (o app descobre sozinho o header de autenticação) e
   depois em **Explorar tudo** para ver o que cada endpoint devolve.

## O que descobrimos da API

| Item | Valor |
|---|---|
| REST API | `https://broker-api.mybrokerdev.com` |
| WebSocket de trade | `wss://broker-api-websocket-proxy.asapcode.workers.dev` |
| WebSocket de preços | `wss://symbol-ws.mybrokerdev.com` |
| Autenticação do site | Bearer JWT via `POST /auth/login` |
| Autenticação de automação | token de `/user-api-tokens` (o que você gerou) |
| Ordem (opção binária) | `amount`, `direction` (BUY/SELL), `isDemo`, expiração, `symbol` |

> Os caminhos dos endpoints foram deduzidos do código do app, então o
> "Explorador da API" serve para confirmar quais existem e qual o formato real.

## Próximas fases (depois de validar a leitura)

- **Preços ao vivo** via WebSocket de preços.
- **Conta demo**: leitura de saldo/operações em tempo real.
- **Execução** (somente quando você decidir): replicar o evento `buy` com
  limites de segurança (perda diária, máx. trades/min) — sempre demo primeiro.
