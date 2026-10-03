#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${PGHOST:-}" || -z "${PGDATABASE:-}" || -z "${PGUSER:-}" ]]; then
  echo "Set PGHOST, PGDATABASE, and PGUSER; pass credentials through PGPASSWORD or a .pgpass file." >&2
  exit 2
fi
if [[ $# -ne 1 ]]; then echo "Usage: scripts/backup-postgres.sh <existing-output-directory>" >&2; exit 2; fi
mkdir -p -- "$1"
out_dir="$(cd -- "$1" && pwd)"
stamp="$(date -u +%Y%m%d-%H%M%SZ)"
target="$out_dir/local-explorer-${PGDATABASE}-${stamp}.dump"
partial="$target.partial"
if [[ -e "$target" ]]; then echo "Refusing to overwrite $target" >&2; exit 2; fi
pg_dump --format=custom --no-owner --no-acl --file="$partial"
mv -- "$partial" "$target"
echo "Backup created: $target"
