#!/usr/bin/env bash
# DISCLAIMER: This shortcut does not respect production security principles; for the sake of
# simplicity and velocity in local development, this script automates .env secret generation,
# starts the backend Docker Compose stack, and builds and runs the standalone frontend container.

set -euo pipefail
cd "$(dirname "$0")"

cat <<'EOF'
==============================================================================
[DEV SHORTCUT DISCLAIMER]
This shortcut does not respect security principles; for the sake of simplicity
and velocity, this script automatically initializes local .env secrets, starts
the backend stack, and builds/runs the standalone frontend container.
Do NOT use this workflow in production environments.
==============================================================================
EOF

case "${1:-}" in
  --stop)
    echo "Stopping standalone frontend container..."
    docker rm -f monster-tamer-frontend >/dev/null 2>&1 || true
    echo "Stopping backend stack..."
    docker compose down
    exit 0
    ;;
  --reset)
    echo "Stopping standalone frontend container..."
    docker rm -f monster-tamer-frontend >/dev/null 2>&1 || true
    echo "Stopping backend stack and removing persisted volumes..."
    docker compose down -v
    exit 0
    ;;
esac

new_secret() {
  openssl rand -base64 24 | tr '+/' '-_' | tr -d '='
}

if [[ ! -f .env.example ]]; then
  echo "Missing .env.example" >&2
  exit 1
fi

secrets_updated=0

if [[ ! -f .env ]]; then
  echo "Creating .env from .env.example with generated local secrets..."
  : > .env
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^([A-Z0-9_]+)=change-me[[:space:]]*$ ]]; then
      echo "${BASH_REMATCH[1]}=$(new_secret)" >> .env
    else
      echo "$line" >> .env
    fi
  done < .env.example
  secrets_updated=1
else
  echo "Checking existing .env for missing or 'change-me' variables..."
  tmp_env="$(mktemp)"
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^([A-Z0-9_]+)=change-me[[:space:]]*$ ]]; then
      echo "${BASH_REMATCH[1]}=$(new_secret)" >> "$tmp_env"
      secrets_updated=1
    else
      echo "$line" >> "$tmp_env"
    fi
  done < .env
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^([A-Z0-9_]+)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      if ! grep -q "^${key}=" "$tmp_env"; then
        val="${BASH_REMATCH[2]}"
        if [[ "$val" == "change-me" ]]; then
          val="$(new_secret)"
        fi
        echo "${key}=${val}" >> "$tmp_env"
        secrets_updated=1
      fi
    fi
  done < .env.example
  if [[ "$secrets_updated" -eq 1 ]]; then
    mv "$tmp_env" .env
  else
    rm -f "$tmp_env"
  fi
fi

if [[ "$secrets_updated" -eq 1 ]]; then
  echo "New secrets generated; resetting any stale Docker DB volumes so passwords match..."
  docker compose down -v >/dev/null 2>&1 || true
fi

echo ""
echo "Starting backend microservices with Docker Compose..."
docker compose up --build -d --wait

echo ""
echo "Building and starting standalone frontend container..."
docker build -t monster-tamer-frontend ./frontend_service
docker rm -f monster-tamer-frontend >/dev/null 2>&1 || true
docker run -d --name monster-tamer-frontend -p 127.0.0.1:8080:8080 monster-tamer-frontend >/dev/null

echo ""
echo "All services are up and running:"
echo "  - Frontend:    http://localhost:8080"
echo "  - API Gateway: https://localhost:5005"
echo ""
echo "Tip: if your browser warns about the local self-signed CA certificate,"
echo "visit https://127.0.0.1:5005/health once and accept it before playing."
echo "To stop everything: ./start-dev.sh --stop"
