#!/usr/bin/env bash
# Disposable production-configuration rehearsal. NO customer services.
set -euo pipefail
project="rally-release-ci-$$"
if [[ -e .env.production ]]; then
  echo "Refusing to overwrite an existing production environment file" >&2
  exit 2
fi
root_secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
app_secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
admin_secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
umask 077
printf 'POSTGRES_PASSWORD=%s\nRALLY_APP_PASSWORD=%s\nRALLY_ADMIN_KEY=%s\nRALLY_DOMAIN=rally.example.com\nACME_EMAIL=ci@example.com\n' \
 "$root_secret" "$app_secret" "$admin_secret" > .env.production
cleanup() {
 docker compose --env-file .env.production -p "$project" -f compose.production.yaml down --volumes --remove-orphans >/dev/null 2>&1 || true
 rm -f .env.production
}
trap cleanup EXIT
# Caddy is intentionally not started: TLS/ACME needs a genuine public domain.
docker compose --env-file .env.production -p "$project" -f compose.production.yaml up --build -d postgres rally worker
ready=0
for i in $(seq 1 60); do
 if docker compose --env-file .env.production -p "$project" -f compose.production.yaml exec -T rally \
  python -c "import httpx; r=httpx.get('http://localhost:8080/readyz', timeout=3); r.raise_for_status()" \
  >/dev/null 2>&1; then ready=1; break; fi
 sleep 2
done
if [[ "$ready" != 1 ]]; then
 docker compose --env-file .env.production -p "$project" -f compose.production.yaml ps || true
 docker compose --env-file .env.production -p "$project" -f compose.production.yaml logs --tail=60 postgres rally worker || true
 echo "Production-profile stack is not ready" >&2
 exit 1
fi
docker compose --env-file .env.production -p "$project" -f compose.production.yaml exec -T rally \
 python -c "from rally.storage import connect; db=connect(); row=db.execute('SELECT current_user,rolsuper FROM pg_roles WHERE rolname=current_user').fetchone(); assert row['current_user']=='rally_app' and not row['rolsuper']; db.close()"
echo "Production-profile API, worker, migrations and restricted PostgreSQL role: OK."
