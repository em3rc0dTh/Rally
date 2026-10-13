#!/usr/bin/env bash
# Disposable production-configuration rehearsal. NO customer services.
set -euo pipefail
project="rally-release-ci-$RANDOM"
export COMPOSE_PROJECT_NAME="$project"
backup_path=""
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
 if [[ -n "$backup_path" ]]; then rm -f "$backup_path" "$backup_path.sha256"; fi
}
trap cleanup EXIT
# Caddy syntax is validated without public ACME network traffic.
docker compose --env-file .env.production -p "$project" -f compose.production.yaml run --rm --no-deps caddy  caddy validate --config /etc/caddy/Caddyfile
# Caddy is not started: actual TLS/ACME needs a genuine public domain.
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

# Exercise one complete authenticated persistence operation on the production profile.
docker compose --env-file .env.production -p "$project" -f compose.production.yaml exec -T rally python - <<'PY'
import os
import httpx
root="http://localhost:8080"
with httpx.Client(timeout=10) as client:
    created=client.post(root+"/api/tenants",json={"name":"Disposable production smoke"},
                        headers={"X-Admin-Key":os.environ["RALLY_ADMIN_KEY"]})
    created.raise_for_status()
    token=created.json()["api_token"]
    saved=client.post(root+"/api/assets",json={"tag":"CI-RESTORE-01","name":"Backup sentinel"},
                      headers={"Authorization":"Bearer "+token})
    saved.raise_for_status()
    assert saved.json()["tag"]=="CI-RESTORE-01"
PY
# Backup and restore into a separate disposable PostgreSQL database, never
# overwriting the running source database.
bash ops/backup.sh
backup_path="$(ls -1t backups/rally-*.dump | head -n 1)"
restore_db="rally_restore_ci_$RANDOM"
bash ops/restore.sh "$backup_path" "$restore_db"
record_count="$(docker compose --env-file .env.production -p "$project" -f compose.production.yaml exec -T postgres \
 psql -U rally -d "$restore_db" -Atc "SELECT count(*) FROM assets WHERE tag='CI-RESTORE-01'" | tr -d '\r\n')"
if [[ "$record_count" != "1" ]]; then
 echo "Restored asset evidence count did not match source database." >&2
 exit 1
fi
echo "Production-profile Caddy config, authenticated API, backup and isolated restore: OK."
