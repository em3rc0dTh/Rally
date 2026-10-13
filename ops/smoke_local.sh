#!/usr/bin/env bash
# Disposable container smoke check. NEVER run against production Compose or real data.
set -euo pipefail
project="rally-smoke-$$-$RANDOM"
secret="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
if [[ -e .env ]]; then
  echo "Refusing to overwrite existing .env; run smoke check in a disposable checkout." >&2
  exit 2
fi
printf 'RALLY_ADMIN_KEY=%s\nRALLY_ENV=development\n' "$secret" > .env
chmod 600 .env
cleanup() {
  docker compose -p "$project" -f compose.yaml down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -f .env
}
trap cleanup EXIT
docker compose -p "$project" -f compose.yaml up --build -d
ready=0
for i in $(seq 1 60); do
  if curl --fail --silent --show-error --max-time 2 http://127.0.0.1:8080/readyz >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  docker compose -p "$project" -f compose.yaml ps || true
  docker compose -p "$project" -f compose.yaml logs --tail=50 rally worker || true
  echo "Rally readiness did not become healthy." >&2
  exit 1
fi
created="$(curl --fail --silent --show-error --max-time 8 \
 -X POST http://127.0.0.1:8080/api/tenants \
 -H "X-Admin-Key: $secret" -H 'Content-Type: application/json' \
 --data '{"name":"Disposable CI Tenant"}')"
token="$(python3 -c 'import json,sys;print(json.loads(sys.stdin.read())["api_token"])' <<<"$created")"
curl --fail --silent --show-error --max-time 8 \
 -H "Authorization: Bearer $token" http://127.0.0.1:8080/api/overview \
 | python3 -c 'import json,sys; p=json.load(sys.stdin); assert p["assets"] == 0 and p["open_cases"] == 0'
echo "Disposable Docker stack: API + worker + readiness + authenticated tenant succeeded."
