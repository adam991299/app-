#!/usr/bin/env bash
# Creates jarvis/.env with random passwords and permissions 600. Never overwrites.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -e .env ]; then
  chmod 600 .env
  echo ".env finns redan – innehållet är oförändrat (rättigheter 600)."
  exit 0
fi

random() { head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32; }

umask 077
sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(random)|" \
    -e "s|^GRAFANA_ADMIN_PASSWORD=.*|GRAFANA_ADMIN_PASSWORD=$(random)|" \
    -e "s|^JARVIS_PASSKEY_SETUP_CODE=.*|JARVIS_PASSKEY_SETUP_CODE=$(random)|" \
    .env.example > .env
chmod 600 .env
echo ".env skapad med slumpade lösenord (rättigheter 600)."
