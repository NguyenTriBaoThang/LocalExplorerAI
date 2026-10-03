#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${PGHOST:-}" || -z "${PGUSER:-}" ]]; then
  echo "Set PGHOST and PGUSER; pass credentials through PGPASSWORD or a .pgpass file." >&2
  exit 2
fi
if [[ $# -ne 2 ]]; then echo "Usage: scripts/restore-postgres.sh <backup.dump> <target-database>" >&2; exit 2; fi
backup="$(realpath -- "$1")"
target_db="$2"
[[ "$backup" == *.dump ]] || { echo "Expected a pg_dump custom-format .dump file." >&2; exit 2; }
pg_restore --list "$backup" >/dev/null
read -r -p "This overwrites objects in '${target_db}'. Type the exact database name: " confirmation
[[ "$confirmation" == "$target_db" ]] || { echo "Restore cancelled." >&2; exit 2; }
PGDATABASE="$target_db" pg_restore --clean --if-exists --no-owner --no-acl --exit-on-error "$backup"
echo "Restore completed to database '${target_db}'. Verify migrations and readiness before switching traffic."
