#!/bin/sh
# Smoke test cụm (spec scale §13): dựng cụm, một lượt lập lịch, kiểm GET /system/status.
# Chạy từ gốc repo: ./scripts/smoke_cluster.sh
# Cần server/.env có key LLM thật, hoặc cache đã ghi câu bên dưới và GATEWAY_CACHE=replay.
set -eu
dc() { docker compose -f docker-compose.cluster.yml "$@"; }
BASE=http://localhost:8000

dc up -d --build
printf 'chờ api'
i=0
until curl -fsS "$BASE/health" >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -gt 60 ] && { echo ' quá 120 giây'; exit 1; }
  printf .
  sleep 2
done
echo

if [ "$(dc exec -T pg-catalog psql -U travility -tAc 'SELECT count(*) FROM places')" -eq 0 ]; then
  (cd server && uv run python -m scripts.import_places ../data/places)
fi
dc exec -T api uv run --no-dev python -m scripts.seed_users >/dev/null
dc exec -T redis redis-cli del nodes >/dev/null   # bỏ nhịp tim của container đời trước (node ma)
sleep 5                                           # mọi bản đang sống báo lại nhịp tim

TOKEN=$(curl -fsS "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"demo1@travility.vn","password":"travility-demo"}' |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["token"])')

curl -fsS "$BASE/system/status" -H "Authorization: Bearer $TOKEN" | python3 -c '
import json, sys
nodes = json.load(sys.stdin)["nodes"]
want = {"nginx": 1, "api": 2, "planner": 2, "planner-agent": 3, "redis": 1, "llm-gateway": 1, "places": 1,
        "pg-catalog": 1, "pg-catalog-replica": 1, "pg-shard": 2}
roles = [n["role"] for n in nodes]
bad = [n["name"] for n in nodes if n["state"] != "up"]
short = {r: roles.count(r) for r, n in want.items() if roles.count(r) < n}
if bad or short:
    sys.exit(f"node không sống: {bad}; thiếu bản: {short}")
print(f"{len(nodes)} node đều sống")'

LAST=$(curl -fsSN "$BASE/trips" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"Đà Lạt 1 ngày 1 triệu cho 2 người, đi Grab","trip_id":null}' | grep '^data: ' | tail -1)
case "$LAST" in
  *'"type": "itinerary"'*) echo 'lập lịch: ra Itinerary' ;;
  *) echo "lập lịch không ra Itinerary: $LAST"; exit 1 ;;
esac
echo 'smoke test cụm: ĐẠT'
