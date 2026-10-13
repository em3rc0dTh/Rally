#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p backups
backup_path="backups/rally-$(date -u +%Y%m%dT%H%M%SZ)-$.dump"
trap 'rm -f "$backup_path.partial"' EXIT
docker compose --env-file .env.production -f compose.production.yaml exec -T postgres pg_dump -U rally -d rally --format=custom > "$backup_path.partial"
test -s "$backup_path.partial"
mv "$backup_path.partial" "$backup_path"
trap - EXIT
sha256sum "$backup_path" > "$backup_path.sha256"
printf 'Backup created: %s\n' "$backup_path"
