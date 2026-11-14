#!/usr/bin/env bash
# Verifies Fas 0: every service is up and healthy, and the app answers over HTTPS only.
set -euo pipefail
cd "$(dirname "$0")/.."

expected="api backup broker-service caddy db execution-engine grafana learning-service \
market-data-service news-service notifier prometheus redis research-lab risk-engine \
scheduler strategy-engine watchdog web"

running="$(docker compose ps --status running --format '{{.Service}}' | sort | tr '\n' ' ')"
for service in $expected; do
  case " $running " in
    *" $service "*) ;;
    *) echo "FEL: tjänsten $service kör inte"; exit 1 ;;
  esac
done

unhealthy="$(docker compose ps --format '{{.Service}} {{.Health}}' | awk '$2 == "unhealthy" || $2 == "starting"')"
if [ -n "$unhealthy" ]; then
  echo "FEL: tjänster som inte är friska:"; echo "$unhealthy"; exit 1
fi

curl --fail --silent --show-error --insecure --retry 10 --retry-delay 2 --retry-all-errors \
  https://localhost/api/healthz | grep -q '"service":"api"'
curl --fail --silent --show-error --insecure https://localhost/healthz | grep -q '"service":"web"'
curl --fail --silent --show-error --insecure https://localhost/ | grep -q 'Jarvis'

published="$(docker compose ps --format '{{.Service}} {{.Ports}}' | grep -E '0\.0\.0\.0|:::' | grep -v '^caddy ' || true)"
if [ -n "$published" ]; then
  echo "FEL: andra tjänster än caddy publicerar portar:"; echo "$published"; exit 1
fi

echo "OK: alla tjänster kör och svarar."
