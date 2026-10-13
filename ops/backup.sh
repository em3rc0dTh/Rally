#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p backups
backup_tmp="$(mktemp "backups/rally-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.dump.partial")"
backup_path="$(printf '%s' "$backup_tmp" | sed 's/[.]partial$//')"
trap 'rm -f "$backup_tmp"' EXIT
docker compose --env-file .env.production -f compose.production.yaml exec -T postgres \
  pg_dump -U rally -d rally --format=custom > "$backup_tmp"
test -s "$backup_tmp"
mv -- "$backup_tmp" "$backup_path"
trap - EXIT
sha256sum "$backup_path" > "$backup_path.sha256"
printf 'Backup created: %s\n' "$backup_path"
