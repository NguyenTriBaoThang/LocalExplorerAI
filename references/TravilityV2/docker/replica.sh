#!/bin/sh
# Bản sao đọc của pg-catalog (spec scale §9.2): volume trống → chép từ node chính, rồi chạy hot standby.
set -e
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  until pg_basebackup -h pg-catalog -U travility -D "$PGDATA" -R -X stream; do
    echo "chờ pg-catalog…"; sleep 1
  done
fi
exec docker-entrypoint.sh postgres
