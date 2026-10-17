# Travility

Desktop app du lịch + bản đồ cho người Việt, AI Trip Planner làm lõi. PRD (yêu cầu, lộ trình, phân vai): `docs/PRD.md`. Spec kỹ thuật: `docs/superpowers/specs/2026-09-25-travility-design.md`. Hiện trạng code: `docs/2026-09-25-hien-trang-app.md`.

## Agent skills

### Issue tracker

Issues nằm ở GitHub Issues của repo (dùng `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Dùng 5 nhãn mặc định: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` ở gốc repo. See `docs/agents/domain.md`.

## Commands

- Server test: `docker compose up -d db redis && cd server && uv run pytest`
- Cụm (nginx + 2 api + 2 planner + 3 planner-agent + llm-gateway + places + Redis + 4 Postgres): `docker compose -f docker-compose.cluster.yml up -d --build` — xem `docs/runbook-cum.md`
- Client test/build: `cd client && npm test && npm run build`
- Import Place: `cd server && uv run python -m scripts.import_places ../data/places`
- Desktop: `cd desktop && uv run python main.py [url]`
