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

fetch() { curl --fail --silent --show-error --insecure --retry 10 --retry-delay 2 --retry-all-errors "$1"; }

body="$(fetch https://localhost/api/healthz)"; grep '"service":"api"' <<<"$body" >/dev/null
body="$(fetch https://localhost/healthz)"; grep '"service":"web"' <<<"$body" >/dev/null
body="$(fetch https://localhost/)"; grep 'Jarvis' <<<"$body" >/dev/null

if curl --silent --insecure --output /dev/null --fail https://localhost/api/openapi.json; then
  echo "FEL: API-schemat är nåbart utifrån"; exit 1
fi

published="$(docker ps --filter "label=com.docker.compose.project=$(docker compose config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')" --format '{{.Label "com.docker.compose.service"}} {{.Ports}}' | grep -- '->' || true)"
others="$(grep -v '^caddy ' <<<"$published" || true)"
if [ -n "$others" ]; then
  echo "FEL: andra tjänster än caddy publicerar portar:"; echo "$others"; exit 1
fi
if grep -E -- '->' <<<"$published" | grep -oE '[0-9]+->' | grep -v '^443->' >/dev/null; then
  echo "FEL: caddy publicerar annat än port 443:"; echo "$published"; exit 1
fi

echo "OK: alla tjänster kör och svarar."
