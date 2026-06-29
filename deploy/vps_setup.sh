#!/usr/bin/env bash
# vps_setup.sh — instala o executor Binance da TRADE IA num VPS Ubuntu (24/7).
# Uso (no VPS, dentro da pasta do projeto clonado):
#   sudo bash deploy/vps_setup.sh
set -e

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "==> Pasta do app: $APP_DIR"

echo "==> Instalando Python e dependencias do sistema..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git

echo "==> Criando ambiente virtual e instalando libs..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  echo "==> ATENCAO: nao achei o .env. Copiando o modelo..."
  cp "$APP_DIR/deploy/.env.exemplo" "$APP_DIR/.env"
  echo "    >>> EDITE $APP_DIR/.env e cole suas chaves antes de continuar! <<<"
fi

echo "==> Instalando o servico (roda sozinho e reinicia se cair)..."
cat > /etc/systemd/system/tradeia-binance.service <<EOF
[Unit]
Description=TRADE IA - Executor Binance
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/tools/run_binance.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tradeia-binance
systemctl restart tradeia-binance

echo ""
echo "==> PRONTO! O executor esta rodando 24/7."
echo "    Ver ao vivo:   journalctl -u tradeia-binance -f"
echo "    Parar:         sudo systemctl stop tradeia-binance"
echo "    Reiniciar:     sudo systemctl restart tradeia-binance"
