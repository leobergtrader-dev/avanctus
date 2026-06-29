# 🖥️ Rodar a TRADE IA num VPS (24/7)

A nuvem atual (Railway/EUA) é **bloqueada pela Binance**. Para operar 24h sem depender do seu PC,
usamos um **VPS** (um computador na nuvem) numa região que a Binance aceita.

## 1. Escolher o VPS
⚠️ **NÃO use região dos EUA** (a Binance bloqueia). Use Brasil ou Europa.

Opções baratas (qualquer um serve, ~R$ 25–40/mês, plano mais simples já basta):
- **Contabo** (Alemanha) — barato e forte
- **Hetzner** (Alemanha/Finlândia) — ótimo custo
- **Hostinger VPS** — tem suporte em português
- **Vultr / DigitalOcean** — escolher a região **São Paulo** (Brasil)

Peça: **Ubuntu 24.04**, o plano mais básico (1 vCPU / 1 GB RAM já roda de sobra).

## 2. Conectar no VPS
O provedor te dá um **IP**, um **usuário** (geralmente `root`) e uma **senha**.
No seu PC, abra o **PowerShell** e digite (troque o IP):
```
ssh root@SEU_IP_AQUI
```
Digite a senha quando pedir.

## 3. Baixar o projeto
```
git clone https://github.com/leobergtrader-dev/avanctus.git tradeia
cd tradeia
```

## 4. Configurar suas chaves
```
cp deploy/.env.exemplo .env
nano .env
```
Cole sua **API Key** e **Secret** da Binance, salve com **Ctrl+O → Enter → Ctrl+X**.
> Comece com `BINANCE_TESTNET=true` (fake) para confirmar que o VPS alcança a Binance.
> Só depois mude para `false` (real).

## 5. Instalar e ligar (1 comando)
```
sudo bash deploy/vps_setup.sh
```
Pronto! O robô passa a rodar **24/7**, reinicia sozinho se cair.

## 6. Acompanhar / controlar
```
journalctl -u tradeia-binance -f      # ver ao vivo
sudo systemctl restart tradeia-binance # reiniciar (ex.: depois de editar o .env)
sudo systemctl stop tradeia-binance    # parar
```

## Para virar REAL (semana que vem, se decidir)
1. Crie a chave **REAL** na Binance, **sem permissão de saque**.
2. No VPS: `nano .env` → cole a chave real e mude `BINANCE_TESTNET=false`.
3. `sudo systemctl restart tradeia-binance`.
4. Comece pequeno (R$ ~2.700 = US$ 500 para as duas).
