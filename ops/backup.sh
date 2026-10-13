#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p backups
backup_path="backups/rally-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
docker compose --env-file .env.production -f compose.production.yaml exec -T postgres pg_dump -U rally -d rally --format=custom > "$backup_path.partial"
mv "$backup_path.partial" "$backup_path"
sha256sum "$backup_path" > "$backup_path.sha256"
printf 'Backup created: %s\n' "$backup_path"
