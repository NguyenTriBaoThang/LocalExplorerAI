# Travility AI Chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trang `/chat` của LocalExplorerAI lập lịch nhiều ngày trên 177 địa điểm TP.HCM bằng bộ lập lịch port từ TravilityV2, hiện trên bản đồ 3D goong-js, tự lưu từng phiên bản và sửa được bằng prompt.

**Architecture:** Port phần server một tiến trình của Travility (`references/TravilityV2/server/app/`) thành package `apps/api/app/services/trip/`, đổi SQL psycopg sang SQLAlchemy ORM, nối vào auth/RBAC, cấu hình LLM, Goong, Open-Meteo và prompt có phiên bản của LocalExplorerAI. Route mới `/api/trips…` trả SSE như Travility. Client port `references/TravilityV2/client/src/` sang `apps/web/src/components/trip/` + `pages/TripChatPage.tsx`, đổi MapLibre sang goong-js đang có, đổi màu sang token của LocalExplorerAI.

**Tech Stack:** FastAPI 0.143, SQLAlchemy 2.1, Alembic, Pydantic 2, `openai` SDK (mới), httpx; React 18, Vite 6, Tailwind 3, `@goongmaps/goong-js`, three.js.

**Spec:** `docs/superpowers/specs/2026-10-17-travility-ai-chat-design.md`

## Global Constraints

- Nguồn port là bản snapshot chỉ đọc `references/TravilityV2/`; không sửa gì trong đó.
- Chỉ tiếng Việt cho mọi chữ của trip chat (prompt, xung đột, phương án, nhãn bữa, PDF, UI), kể cả khi site đang ở `en`.
- Chỉ TP.HCM: một destination `slug="tp-hcm"`, `name="TP. Hồ Chí Minh"`, tâm `lat=10.7769, lon=106.7009`.
- AI chỉ được dùng Place đã trả về từ `search_places` trong lượt đó (hoặc có trong lịch cũ / lịch đang sửa) — giữ nguyên `InvalidDraft` + "làm lại 1 lần" (ADR-0001 của Travility).
- Tiền / km / phút / xung đột chỉ do code tính (`rules.py`), không do LLM.
- Không thêm `maplibre-gl`, `react-map-gl`, `vitest`, pgvector. Dependency mới duy nhất: `openai>=1.50,<3.0` trong `apps/api/requirements.txt` (agent cần `msg.model_dump(exclude_none=True)` để Gemini nhận lại `thought_signature`).
- Bỏ hoàn toàn phần cụm: `gateway`, `jobs`, `worker`, `multi`, `system`, `nodes`, `places_service`, `places_client`, `kv`, `DEMO_TODAY`, `PLANNER_MODE`, Redis.
- Bảng mới đi qua Alembic `0020_trip_planner` (down_revision `0019_itinerary_collaboration`); cột JSON dùng `JSON_DOCUMENT`, thời gian dùng `UTCDateTime` từ `app/models/entities.py` / `app/db/types.py` để test SQLite chạy được.
- Mọi route trip dùng `require_user(P.TRIP_USE)`; permission `trip:use` ("Plan and edit multi-day trips in AI Chat") cấp cho `traveler`, seed trong migration như `0019` làm với `PERMISSIONS`.
- Chuyến của người khác → 404 "Không tìm thấy chuyến đi" (không phải 403).
- Giờ "hôm nay" theo `ZoneInfo("Asia/Ho_Chi_Minh")`.
- Prompt mới vào phiên bản `3.2.0` (`app/prompts/v3_2_0/`, copy nguyên 10 file của `v3_1_0` + 4 file mới); không sửa file của `v3_1_0`.
- Màu UI: thay bảng màu Travility theo bảng dưới; font Be Vietnam Pro; bản đồ dùng style tối `https://tiles.goong.io/assets/goong_map_dark.json`.

| Travility | LocalExplorerAI |
|---|---|
| `bg-pine` (rail) | `var(--bg-surface)` + viền `var(--border-subtle)` |
| `bg-white` panel | `var(--bg-card)` + `backdrop-blur` + `var(--radius-lg)` |
| `marigold` (pin đang tìm, nút tour, nhấn) | `var(--amber)` / `var(--amber-glow)` |
| nút chính, ✓ mục đích | `var(--emerald)` |
| link, chọn Stop, tuyến | `var(--cyan)`; màu từng ngày dùng `LEG_COLORS` từ `components/map/MapAdapter.tsx` |
| Conflict, ✗ | `var(--rose)` |
| `text-stone-900/500` | `var(--text-main)` / `var(--text-muted)` |
| `bg-mist` (hover, chọn) | `var(--bg-surface-elevated)` |

## Review Focus

1. **Giờ mở cửa dạng `"days": "T4,T6,T7"`, `"T3-CN"`, quán qua đêm `18:00–02:00`** — chuyển đổi lúc import phải ra đúng thứ trong tuần; Stop vào ngày đóng cửa bị báo `closed`. Test: `test_open_hours_conversion` (Task 2).
2. **Place có tag tự do không map được sang 17 tag chuẩn** — vẫn import, vẫn tìm được theo từ khoá/embedding, chỉ không khớp lọc tag. Test: `test_unmapped_tags_still_searchable` (Task 2).
3. **Gemini embedding lỗi hoặc chưa cấu hình** — `search_places` lùi về tìm theo kind + tag + từ khoá, chỉ trả Place trong bảng. Test: `test_search_falls_back_to_keywords` (Task 2).
4. **LLM sập giữa chừng (429 / mất mạng)** — SSE trả `error` tiếng Việt, không lưu version dở. Test: `test_llm_error_saves_nothing` (Task 5).
5. **Chuyến của người khác trên mọi route** (GET, pins, restore, disruptions, proposals apply, group-reviews) — 404, không lộ dữ liệu. Test: `test_other_users_trip_is_404_everywhere` (Task 9).

---

## File Structure

**API — tạo mới**
- `apps/api/app/models/trip_entities.py` — ORM: `TripDestination`, `TripPlace`, `Trip`, `TripItinerary`, `TripMessage`, `TripProposal`, `TripGroupReview`.
- `apps/api/migrations/versions/0020_trip_planner.py`
- `apps/api/app/services/trip/__init__.py`
- `apps/api/app/services/trip/domain.py` ← `server/app/domain.py`
- `apps/api/app/services/trip/rules.py` ← `rules.py`
- `apps/api/app/services/trip/distance.py` ← `distance.py` (Goong Distance Matrix + cache RAM)
- `apps/api/app/services/trip/forecast.py` ← `forecast.py` (trên `open_meteo_service.daily_forecast`)
- `apps/api/app/services/trip/llm.py` ← `llm.py` (client OpenAI SDK + embed theo cấu hình LocalExplorerAI)
- `apps/api/app/services/trip/places.py` ← `places.py` (cosine Python + fallback từ khoá)
- `apps/api/app/services/trip/agent.py` ← `agent.py`
- `apps/api/app/services/trip/followup.py` ← `followup.py`
- `apps/api/app/services/trip/replan.py` ← `replan.py`
- `apps/api/app/services/trip/store.py` ← phần SQL của `trips.py`, `versions.py`, `proposals.py`, `group_reviews.py`
- `apps/api/app/services/trip/flow.py` ← phần điều phối của `trips.py` (`_run`, `_follow_up`, `_replan`, `_plan_and_save`, `guarded`, `sse`)
- `apps/api/app/api/routes/trips.py` — mọi route `/api/trips…`
- `apps/api/scripts/import_trip_places.py` ← `server/scripts/import_places.py`
- `apps/api/app/prompts/v3_2_0/` — 10 file copy + `TRIP_PARSER.md`, `TRIP_PLANNER.md`, `TRIP_FOLLOWUP.md`, `TRIP_GROUP_REVIEW.md`
- `apps/api/tests/trip/__init__.py`, `tests/trip/conftest.py` (fixture `trip_places`, `FakeClient`, `reply`), và các `tests/trip/test_*.py`

**API — sửa**
- `apps/api/requirements.txt` (+`openai`), `app/api/permissions.py` (+`TRIP_USE`, cấp traveler), `app/main.py` (include router), `migrations/env.py` (import `trip_entities`), `app/core/config.py` (+`gemini_embed_model`), `app/api/dependencies.py` (tách `resolve_llm_config`), `app/services/chat_response_service.py` (tách `classify_chat_intent`), `app/prompts/manifest.json`, `docs/ai-prompt-catalog.md`, `tests/test_ai_workflows.py` (3.2.0, 14 prompt), `docker-compose.yml` (mount `./data:/data:ro` cho `api`).

**Web — tạo mới** (`apps/web/src/`)
- `api/trips.ts` ← `client/src/api.ts` (bỏ `authRequest`, token; dùng cookie)
- `components/trip/sse.ts`, `place.ts`, `layout.ts`, `tripPrint.ts` ← cùng tên; kèm `sse.test.ts`, `place.test.ts`, `layout.test.ts`, `tripPrint.test.ts` chạy bằng `node --test`
- `components/trip/TripMap.tsx` ← `MapView.tsx` (goong-js), `components/trip/landmarkLayer.ts` (mô hình GLB)
- `components/trip/Rail.tsx`, `FloatingPanel.tsx`, `ChatPanel.tsx`, `ClarifyCard.tsx`, `ConfirmCard.tsx`, `Timeline.tsx`, `PlacePopup.tsx`, `PlaceThumb.tsx`, `ProposalPanel.tsx`, `GroupReviewPanel.tsx`, `TripPrintView.tsx` ← cùng tên
- `pages/TripChatPage.tsx` ← `App.tsx` (bỏ Login, SystemPage, token)

**Web — sửa / xoá**
- `router.tsx` (`/chat` → `TripChatPage`), `package.json` (+script `test`), `tsconfig.json` (exclude `src/**/*.test.ts`), `styles.css` (lớp print + pin nhấp nháy). Xoá `pages/ChatPage.tsx`.

**Lệnh dùng chung**
- Test API: `cd apps/api && .venv/bin/python -m pytest -q -p no:cacheprovider <đường dẫn>`
- Build web: `cd apps/web && npm run build`
- Test web: `cd apps/web && npm test`

---

### Task 1: Bảng, migration, permission và domain

**Files:**
- Create: `apps/api/app/models/trip_entities.py`, `apps/api/migrations/versions/0020_trip_planner.py`, `apps/api/app/services/trip/__init__.py`, `apps/api/app/services/trip/domain.py`, `apps/api/tests/trip/__init__.py`, `apps/api/tests/trip/conftest.py`, `apps/api/tests/trip/test_domain.py`
- Modify: `apps/api/app/api/permissions.py`, `apps/api/migrations/env.py`, `apps/api/app/models/entities.py` (cuối file: `from app.models import trip_entities  # noqa: E402,F401`, cạnh dòng import `auth_entities`)

**Interfaces:**
- Produces (ORM, `id` integer autoincrement trừ `TripDestination`):
  - `TripDestination(slug: str PK, name, lat: float, lon: float, hubs: JSON dict[ArrivalMode, {name, lat, lon}])`
  - `TripPlace(id, ext_id: str unique, destination: FK slug, name, kind, lat, lon, price: int, open_hours: JSON dict[weekday, [open, close] | None], outdoor: bool, tags: JSON list[str], raw_tags: JSON list[str], description, address, photo_url | None, source | None, embedding: JSON list[float] | None)`
  - `Trip(id, user_id: String(36) FK users.id ondelete CASCADE index, spec: JSON, user_messages: JSON list[str] default [], pending_replan: JSON | None, pinned_place_ids: JSON list[int] default [], created_at, updated_at)`
  - `TripItinerary(id, trip_id FK cascade, version: int, data: JSON {"itinerary", "places"}, created_at)`, `UniqueConstraint(trip_id, version)`
  - `TripMessage(id, trip_id FK cascade, role: CHECK IN ('user','ai'), text, version | None, created_at)`, index `(trip_id, id)`
  - `TripProposal(id, trip_id FK cascade, base_version, disruption: JSON, options: JSON, no_feasible: JSON | None, chosen_index | None, applied_version | None, created_at)`
  - `TripGroupReview(id, trip_id FK cascade, source_version, base_version, feedback, candidate: JSON, status CHECK IN ('pending','applied','cancelled') default 'pending', applied_version | None, created_at)`
- Produces: `app.services.trip.domain` — y hệt Travility (`TAGS`, `INTENTS`, `INTENT_LABELS`, `KINDS`, `WEEKDAYS`, `Trip`, `TripAnswers`, `Hub`, `Place`, `Draft*`, `Stop`, `Leg`, `Day`, `Conflict`, `Itinerary`, `Disruption`, `intent_weights`, `place_intents`). `Place.id: int`.
- Produces (test fixtures, `tests/trip/conftest.py`): `FakeClient`, `reply(*calls, content=None)` (copy `server/tests/fakes.py`, bỏ `RoleClient`); fixture `trip_places(db_session) -> dict[str, TripPlace]` tạo destination `tp-hcm` + hub `may-bay` (Tân Sơn Nhất 10.8188, 106.6519) + 8 Place đủ kind (2 `an-uong` mở 06:00–22:00, 1 `an-uong` chỉ tối 17:00–23:00, 2 `cafe`, 2 `tham-quan` trong đó 1 `outdoor`, 1 `cho-o`), toạ độ trong Quận 1, khoá theo `ext_id`.

- [ ] **Step 1: Port test domain** — copy `server/tests/test_domain.py` → `apps/api/tests/trip/test_domain.py`, đổi import `app.domain` → `app.services.trip.domain`.
- [ ] **Step 2: Run** `tests/trip/test_domain.py` — Expected: FAIL (`ModuleNotFoundError: app.services.trip`).
- [ ] **Step 3: Copy `domain.py`** sang `app/services/trip/domain.py`, không đổi logic.
- [ ] **Step 4: Viết ORM + migration** theo Interfaces; migration tạo đủ 7 bảng + seed permission `trip:use` cho `traveler` (copy cách `0019` dùng `op.bulk_insert` và `downgrade_permissions`). Thêm `TRIP_USE = _p("trip:use", "Plan and edit multi-day trips in AI Chat")` vào `P` (nhóm Traveler) và vào `DEFAULT_GRANTS["traveler"]`.
- [ ] **Step 5: Thêm test** `tests/trip/test_domain.py::test_trip_tables_round_trip`: tạo `Trip(user_id=make_user(db_session,"traveler").id, spec={...})` + `TripItinerary(version=1)` + `TripItinerary(version=1)` lần hai → `IntegrityError`; và `test_traveler_has_trip_use`: `Authorizer(DbRoleMatrix(db_session))` cho principal traveler `.can(..., P.TRIP_USE)` là `True`, provider là `False`.
- [ ] **Step 6: Run** `tests/trip/` và `tests/test_rbac.py` — Expected: PASS. Chạy thêm `cd apps/api && DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/local_explorer .venv/bin/alembic upgrade head` rồi `downgrade -1` rồi `upgrade head` — Expected: không lỗi.
- [ ] **Step 7: Commit** `feat(trip): add trip planner tables, permission and domain`

### Task 2: Import 177 địa điểm, embedding và tìm kiếm

**Files:**
- Create: `apps/api/scripts/import_trip_places.py`, `apps/api/app/services/trip/llm.py`, `apps/api/app/services/trip/places.py`, `apps/api/tests/trip/test_import_places.py`, `apps/api/tests/trip/test_places.py`
- Modify: `apps/api/requirements.txt` (+`openai>=1.50,<3.0`), `apps/api/app/core/config.py` (+`gemini_embed_model: str = "gemini-embedding-001"`), `apps/api/app/api/dependencies.py`, `docker-compose.yml` (service `api`: `volumes: - ./data:/data:ro`)

**Interfaces:**
- Consumes: Task 1 ORM + domain.
- Produces:
  - `dependencies.resolve_llm_config(db: Session) -> tuple[str, str, str] | None` — `(api_key, base_url, model)` theo đúng logic đang có trong `get_llm_provider` (provider `openai|gemini` qua `resolve_integration_value`); `get_llm_provider` gọi lại hàm này.
  - `trip.llm.chat_client(db) -> tuple[openai.OpenAI, str] | None` — client + model; `None` khi chưa cấu hình.
  - `trip.llm.embed(db, texts: list[str]) -> list[list[float]] | None` — dùng `gemini_api_key`/`gemini_base_url` (qua `resolve_integration_value(db,"ai",…)`) + `settings.gemini_embed_model`, `dimensions=768`; trả `None` khi thiếu key hoặc gọi lỗi (log warning). `EMBED_DIM = 768`.
  - `EmbedFn = Callable[[list[str]], list[list[float]] | None]`; flow truyền `lambda texts: llm.embed(db, texts)`.
  - `trip.places.search_places(db, destination: str, query: str, embed_fn: EmbedFn, kind: str | None = None, required_tags=(), avoided_tags=(), limit: int = 8) -> list[Place]` — lọc `destination`, `kind`, chứa đủ `required_tags`, không chứa `avoided_tags`; có embedding cho query + Place → xếp theo cosine; không có → xếp theo số từ khoá (đã bỏ dấu, `_fold` như `chat_response_service`) trùng trong `name + description + raw_tags`, hoà thì theo `id`.
  - `trip.places.similar_places(db, place_id: int, kind: str, exclude_ids=(), exclude_tags=(), limit: int = 20) -> list[Place]` — cosine trên embedding đã lưu; thiếu embedding → cùng kind, xếp theo số tag chung rồi khoảng cách.
  - `trip.places.get_places(db, ids) -> dict[int, Place]`, `list_destinations(db) -> list[dict]` (`{slug, name, lat, lon, hubs}`).
  - `scripts.import_trip_places.convert(raw: dict) -> dict` (một bản ghi `sai_gon_places.json` → cột `TripPlace`), `import_file(db, path, embed_fn) -> int`, `TAG_MAP: dict[str, str]`, `HCMC_HUBS`.
- Quy tắc chuyển đổi (`convert`):
  - `ext_id=id`, `price=price_vnd`, `lon=lon`, `address`, `source`, `photo_url`, `description` (+ `" " + note` nếu có).
  - `open_hours`: `json.loads` chuỗi `{"open","close","days"}`; `days` dạng `"T2-CN"` (khoảng, T2=mon … T7=sat, CN=sun) hoặc `"T4,T6,T7"` (liệt kê) → `{weekday: [open, close]}` cho ngày mở, `None` cho ngày còn lại; `"00:00"`–`"23:59"` giữ nguyên. Giá trị lạ → `ValueError` nêu `ext_id`.
  - `tags = sorted({TAG_MAP[t] for t in raw_tags if t in TAG_MAP} | (set(raw_tags) & TAGS))`; `raw_tags = raw.tags`. `TAG_MAP` tối thiểu: `chay→an-chay`; `mon-viet, dac-san, dac-san-sai-gon, am-thuc-duong-pho, com-tam, banh-mi, nam-bo, an-vat, binh-dan→an-dia-phuong`; `specialty-coffee, cafe, chill, cafe-phin→cafe-chill`; `bao-tang, di-tich, di-san, di-tich-quoc-gia→lich-su`; `kien-truc, nghe-thuat, tam-linh, ton-giao, truyen-thong→van-hoa`; `cong-vien, cay-xanh, sinh-thai, san-vuon→thien-nhien`; `rooftop, hoang-hon, view-song, view-toan-canh→view-dep`; `bar, pub, nightclub, live-music, pho-di-bo, nhon-nhip→soi-dong`; `buoi-toi, giai-tri-dem→dem`; `thanh-tinh, thu-gian→yen-tinh`; `hen-ho→lang-man`; `bieu-tuong, noi-tieng→check-in`; `khach-san-5-sao, michelin, michelin-selected, fine-dining, xa-hoa→sang-trong`; `cho, cho-que→mua-sam`; `cong-vien-nuoc→gia-dinh`. Người làm được bổ sung thêm mục cho tag khác, không xoá mục trên.
  - `HCMC_HUBS = {"may-bay": Sân bay Tân Sơn Nhất (10.8188, 106.6519), "tau": Ga Sài Gòn (10.7820, 106.6773), "xe-khach": Bến xe Miền Đông mới (10.8790, 106.8146)}`. Bến xe Miền Tây không có ArrivalMode riêng trong Travility → bỏ.
  - Upsert theo `ext_id`; `place_text = f"{name}. {description}. Tags: {', '.join(raw_tags)}"`; `embed_fn` trả `None` → `embedding=None`.
  - CLI: `python -m scripts.import_trip_places /data/sai_gon_places.json` in ra số Place.

- [ ] **Step 1: Viết test import** `tests/trip/test_import_places.py`:
  - `test_open_hours_conversion`: `convert({... "open_hours": '{"open":"20:30","close":"01:30","days":"T4,T6,T7"}'})["open_hours"] == {"mon": None, "tue": None, "wed": ["20:30","01:30"], "thu": None, "fri": ["20:30","01:30"], "sat": ["20:30","01:30"], "sun": None}`; `"T3-CN"` → `mon` là `None`, `tue`…`sun` có giờ; `"days": "abc"` → `ValueError`.
  - `test_tags_are_normalised`: raw `["chay","rooftop","kien-truc-phap"]` → `tags == ["an-chay","view-dep"]`, `raw_tags` giữ nguyên 3 tag.
  - `test_import_upserts_by_ext_id`: import file tạm 2 Place với `embed_fn=lambda t: [[1.0]+[0.0]*767]*len(t)` → 2 dòng + 1 destination `tp-hcm` có 3 hub; import lại với giá khác → vẫn 2 dòng, giá mới.
  - `test_real_dataset_imports`: `import_file(db_session, <repo>/data/sai_gon_places.json, lambda t: None) == 177`.
- [ ] **Step 2: Viết test tìm kiếm** `tests/trip/test_places.py` (dùng `trip_places`):
  - `test_search_filters_kind_and_tags` (port `server/tests/test_places*.py` phần lọc).
  - `test_search_ranks_by_embedding`: gán embedding tay cho 2 Place, `embed_fn` trả vector gần Place B → B đứng đầu.
  - `test_search_falls_back_to_keywords`: `embed_fn=lambda t: None`, query `"phở bò"` → Place có `"Phở"` trong tên đứng đầu; mọi kết quả đều là `TripPlace` trong bảng.
  - `test_unmapped_tags_still_searchable`: Place chỉ có `raw_tags=["speakeasy"]`, `tags=[]` → `search_places(..., query="speakeasy", embed_fn=lambda t: None)` có Place đó.
- [ ] **Step 3: Run** hai file — Expected: FAIL (module chưa có).
- [ ] **Step 4: Cài** `cd apps/api && .venv/bin/pip install 'openai>=1.50,<3.0'`; thêm dòng vào `requirements.txt`.
- [ ] **Step 5: Implement** `resolve_llm_config`, `trip/llm.py`, `trip/places.py`, `scripts/import_trip_places.py` theo Interfaces.
- [ ] **Step 6: Run** `tests/trip/` + `tests/test_ai_workflows.py` — Expected: PASS.
- [ ] **Step 7: Import thật** `docker compose up -d --build api && docker compose exec api python -m scripts.import_trip_places /data/sai_gon_places.json` — Expected: in `177`; `docker compose exec db psql -U postgres -d local_explorer -c "select count(*), count(embedding) from trip_places"` → `177 | 177` (nếu Gemini key hợp lệ; nếu `count(embedding)=0` ghi lại trong báo cáo, không chặn task).
- [ ] **Step 8: Commit** `feat(trip): import HCMC places with embeddings and search`

### Task 3: Luật tính tiền/xung đột, khoảng cách Goong, khả năng mưa

**Files:**
- Create: `apps/api/app/services/trip/rules.py`, `distance.py`, `forecast.py`, `tests/trip/test_rules.py`, `tests/trip/test_distance.py`, `tests/trip/test_forecast.py`

**Interfaces:**
- Consumes: domain.
- Produces:
  - `rules.*` y hệt Travility (`build_itinerary`, `find_conflicts`, `make_leg`, `is_open`, `haversine_km`, `cost_breakdown`, `intent_retention`, `last_day_limit`, `vnd`, `InvalidDraft`, hằng số). Chỉ đổi import `app.distance` → `app.services.trip.distance`.
  - `distance.lookup(a, b, mode) -> tuple[float, int] | None`, `distance.prefetch(origins, destinations, mode, client: httpx.Client | None = None) -> None` — giữ cache RAM `_cache` + `_down_until` (nghỉ 60 s sau lỗi); key Goong lấy `settings.goong_api_key`, base `settings.goong_api_base_url` + `/DistanceMatrix`; bỏ `kv` và `_via_places`.
  - `forecast.get_rain_chance(lat, lon, start: date | None, days: int, today: date | None = None) -> list[int | None] | None` — mỗi ngày gọi `open_meteo_service.daily_forecast(lat, lon, d)` và lấy xác suất mưa max; ngày ngoài 16 ngày → `None` cho ngày đó; `start` ngoài khung hoặc `OpenMeteoUnavailable` ở ngày đầu → `None`.

- [ ] **Step 1: Port test** `server/tests/test_rules.py`, `test_distance.py`, `test_forecast.py` → `tests/trip/`. Đổi import; thay fixture Place Đà Lạt bằng `Place` dựng trong test (không cần DB); `test_forecast` monkeypatch `open_meteo_service.daily_forecast` thay vì httpx mock; bỏ test dùng Redis/`kv`/`DEMO_TODAY`/`places_client`.
- [ ] **Step 2: Run** — Expected: FAIL (module chưa có).
- [ ] **Step 3: Implement** ba module theo Interfaces.
- [ ] **Step 4: Run** `tests/trip/` — Expected: PASS. `conftest.py` của `tests/trip` thêm fixture autouse xoá `distance._cache` và đặt `distance._down_until = 0.0`, monkeypatch `settings.goong_api_key = ""`.
- [ ] **Step 5: Commit** `feat(trip): port cost, conflict, distance and rain rules`

### Task 4: Prompt 3.2.0 và agent lập lịch

**Files:**
- Create: `apps/api/app/prompts/v3_2_0/*` (10 file copy từ `v3_1_0` + `TRIP_PARSER.md`, `TRIP_PLANNER.md`, `TRIP_FOLLOWUP.md`, `TRIP_GROUP_REVIEW.md`), `apps/api/app/services/trip/agent.py`, `tests/trip/test_parse_trip.py`, `tests/trip/test_clarify.py`, `tests/trip/test_plan.py`
- Modify: `apps/api/app/prompts/manifest.json` (`version: "3.2.0"`, `effective_date: "2026-10-17"`, thêm 4 id), `docs/ai-prompt-catalog.md`, `apps/api/tests/test_ai_workflows.py` (`"3.2.0"`, `len == 14`)

**Interfaces:**
- Consumes: places (`search_places`), rules, domain, `app.prompts.registry.catalog`.
- Produces: `agent.*` như Travility, khác:
  - Prompt đọc từ `catalog.get("TRIP_PARSER").system_prompt.format(today=…)` / `TRIP_PLANNER` / `TRIP_FOLLOWUP` / `TRIP_GROUP_REVIEW`; nội dung file = nguyên văn `PARSE_PROMPT`, `PLAN_PROMPT`, `FOLLOWUP_PROMPT`, `GROUP_REVIEW_PROMPT` của Travility, chỉ đổi ví dụ Đà Lạt thành TP.HCM. Giữ `{today}` và các `{…}` placeholder khác; dấu `{`/`}` nghĩa đen phải nhân đôi.
  - `parse_trip(client, model, message, destinations: dict[str,str], today) -> Trip`; yêu cầu nơi khác → `UnsupportedDestination("Hiện mình chỉ hỗ trợ lịch trình ở TP. Hồ Chí Minh.")`.
  - `run_search(db, trip, embed_fn, args, seen) -> tuple[dict, str]`, `plan(db, client, model, trip, embed_fn, rain, hub=None, user_messages=(), previous=None) -> Iterator[dict]` — bỏ `seeded`, `notes`, `max_searches`.
  - `missing_questions`, `merge_trip`, `apply_answers`, `trip_brief`, `itinerary_event`, `previous_brief`, `MAX_STEPS = 12`, `MAX_INVALID = 1`, `PLAN_TOOLS` giữ nguyên.

- [ ] **Step 1: Port test** `server/tests/test_parse_trip.py`, `test_clarify.py`, `test_plan.py` → `tests/trip/` dùng `FakeClient`/`reply` và fixture `trip_places`; đổi `destination="da-lat"` → `"tp-hcm"`, `place_id` lấy từ `trip_places[...].id`; bỏ test của `multi`. Thêm `test_unsupported_destination_message`: parse trả `destination="ha-noi"` → `UnsupportedDestination` có chữ `"TP. Hồ Chí Minh"`. Thêm `test_prompts_load_from_catalog`: `catalog.get("TRIP_PLANNER").version == "3.2.0"` và `"search_places" in` prompt.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Tạo `v3_2_0`** (copy + 4 file), sửa manifest, catalog doc (một mục cho mỗi prompt mới: mục đích, input, tool), test_ai_workflows.
- [ ] **Step 4: Port `agent.py`** theo Interfaces.
- [ ] **Step 5: Run** `tests/trip/ tests/test_ai_workflows.py tests/test_prompt_workflow_migration.py` — Expected: PASS.
- [ ] **Step 6: Commit** `feat(trip): port trip parser and planning agent with prompt suite 3.2.0`

### Task 5: Lưu trữ, luồng SSE và route lập lịch

**Files:**
- Create: `apps/api/app/services/trip/store.py`, `apps/api/app/services/trip/flow.py`, `apps/api/app/api/routes/trips.py`, `tests/trip/test_trips_api.py`
- Modify: `apps/api/app/main.py` (`app.include_router(trips.router)`), `apps/api/app/services/chat_response_service.py`

**Interfaces:**
- Consumes: agent, places, forecast, llm, `route_chat_message` internals.
- Produces:
  - `chat_response_service.classify_chat_intent(message: str, has_planning_context: bool, provider) -> tuple[ChatRoute, ChatTopic | None, str | None]` — phần đầu của `route_chat_message` (LLM router, lỗi → `_offline_intent`); `route_chat_message` gọi lại nó, hành vi `/api/chat/message` không đổi.
  - `store.trip_row(db, user_id, trip_id) -> Trip | None` (lọc theo `user_id`), `store.save_itinerary(db, trip_id, itinerary: dict, places: dict) -> int` (khoá `SELECT … FOR UPDATE` trên `trips` khi Postgres; version = max+1; commit), `store.log_message(db, trip_id, role, text, version=None)`, `store.load_itinerary(db, trip_id, version=None) -> tuple[int, Itinerary, dict] | None` (gán `stop.pinned` từ `Trip.pinned_place_ids`), `store.latest_itinerary`, `store.itinerary_places`, `store.hub_for(dest, trip)`, `store.list_trips(db, user_id) -> list[dict]` (`{id, spec, created_at, destination_name}`, mới nhất trước — đúng shape `TripSummary` mà `tripLabel` ở client cần).
  - `flow.sse(event) -> str`, `flow.guarded(events)` (bắt `openai.OpenAIError` → `"Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."`, lỗi khác → `"Có lỗi khi lập lịch trình, bạn thử lại nhé."`, đều `db.rollback()` trước khi yield lỗi), `flow.run_message(db, user, message, trip_id | None, provider) -> Iterator[str]`, `flow.run_plan(db, user, trip_id, answers)`, `flow.run_replan(db, user, trip_id, changes, message)`.
  - Định tuyến trong `run_message` (trước bước `parse_trip` / `followup`): `intent, topic, _ = classify_chat_intent(message, has_planning_context=trip có spec, provider)`:
    - `out_of_scope` → event `answer` với `_out_of_scope_reply("vi")`.
    - `travel_information` + `topic == "weather"` → `_weather_reply` với `ChatMessage(message, language="vi", trip_context=ChatTripContext(trip_date=trip.start_date, destination=tâm TP.HCM))` → event `answer {text: reply.reply}`.
    - `travel_information` khác, **chưa** có lịch → `TRAVEL_ASSISTANT` với `catalog_context` dựng từ `search_places(..., embed_fn=lambda t: None, limit=5)` (tên, mô tả, giờ mở, giá) → `answer`.
    - còn lại → luồng Travility (`_run` / `_follow_up`).
    - Có `trip_id` thì `answer` được `log_message` (user + ai); chưa có Trip thì không tạo Trip.
  - Route (`APIRouter(prefix="/api", tags=["trips"])`, mọi route `Depends(require_user(P.TRIP_USE))`):
    - `GET /api/trips` → `list_trips`
    - `POST /api/trips` body `{message: str 1..2000, trip_id: int | None}` → `StreamingResponse(flow.run_message…, media_type="text/event-stream")`; `trip_id` không thuộc user → 404 trước khi stream.
    - `POST /api/trips/{id}/plan` body `TripAnswers` → SSE; 404/409/422 như Travility trước khi stream.
    - `POST /api/trips/{id}/replan` body `{changes: dict, message: str}` → SSE.
    - `GET /api/trips/{id}?version=N` → `{trip_id, trip, center, version, itinerary, places, versions, pinned_place_ids}` như `get_trip` của Travility; version không có → 404 `"Không tìm thấy phiên bản lịch trình"`.
  - Event SSE và payload giữ nguyên Travility: `thinking`, `trip {trip_id, trip, center:[lon,lat]}`, `tool_call {name, query, places}`, `clarify`, `itinerary {itinerary, places, trip_id, version, changed?}`, `answer`, `confirm_replan`, `error`.
  - Session: endpoint dùng `db: Session = Depends(get_db)` và truyền vào generator (FastAPI ≥0.118 đóng dependency yield sau khi stream xong). Step 1 có test chứng minh.

- [ ] **Step 1: Port test** `server/tests/test_trips_api.py` → `tests/trip/test_trips_api.py`: `client` + `bearer_for(make_user(db_session,"traveler"))`; monkeypatch `trip.llm.chat_client` → `(FakeClient([...]), "fake-model")`, `trip.llm.embed` → `lambda db, t: None`, `forecast.get_rain_chance` → `None`, `chat_response_service.classify_chat_intent` → `("planning", None, None)` trừ test định tuyến; đọc SSE bằng `client.stream("POST", …)` và tách `data: …\n\n`. Bỏ test Redis/job/shard. Thêm:
  - `test_llm_error_saves_nothing`: FakeClient trả `openai.APIConnectionError(request=httpx.Request("POST","http://x"))` ở lượt plan → event cuối `{"type":"error","message":"Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."}`, `TripItinerary` count 0.
  - `test_weather_question_answers_without_new_version`: Trip có lịch v1, `classify_chat_intent` → `("travel_information","weather",None)`, monkeypatch `daily_forecast` → event `answer` chứa `"Open-Meteo"`, vẫn chỉ có v1.
  - `test_out_of_scope_does_not_create_trip`: không `trip_id`, intent `out_of_scope` → một `answer`, `Trip` count 0.
  - `test_stream_session_survives_until_end`: luồng plan đủ → `itinerary` có `version == 1` và `TripMessage` có dòng `ai`.
  - `test_requires_login`: `POST /api/trips` không header → 401.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** `classify_chat_intent`, `store.py`, `flow.py`, `routes/trips.py`, include router.
- [ ] **Step 4: Run** `tests/trip/ tests/test_ai_workflows.py tests/test_rbac.py tests/test_role_isolation.py` — Expected: PASS (route inventory phải thấy policy `require` trên mọi route mới).
- [ ] **Step 5: Commit** `feat(trip): stream trip planning over SSE with saved versions`

### Task 6: Sửa lịch bằng hội thoại (followup + xác nhận lập lại)

**Files:**
- Create: `apps/api/app/services/trip/followup.py`, `tests/trip/test_followup.py`
- Modify: `apps/api/app/services/trip/flow.py`

**Interfaces:**
- Consumes: agent, rules. Tạo `app/services/trip/replan.py` ngay ở task này, chỉ chứa `to_draft(itin: Itinerary) -> Draft` (copy từ Travility); Task 7 port phần còn lại vào cùng file.
- Produces: `followup.followup(db, client, model, trip, itin, places, message, rain, hub, embed_fn, pending) -> Iterator[dict]`, `apply_ops`, `itinerary_facts`, `changed_trip`, `InvalidEdit`, `review_group_feedback(...)` (dùng ở Task 8) — như Travility. `flow._follow_up`/`_replan` như `trips.py` (cập nhật `pending_replan`, `user_messages`, log message).

- [ ] **Step 1: Port test** `server/tests/test_followup.py` + phần followup/replan trong `test_trips_api.py` (answer không tạo version; edit tạo v2 có `changed`; Stop ghim bị từ chối; `change_trip` → `confirm_replan` rồi `POST /replan` → v2; gõ "oke" khi có `pending_replan` → lập lại).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** theo Interfaces.
- [ ] **Step 4: Run** `tests/trip/` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(trip): edit itineraries through follow-up messages`

### Task 7: Ghim, phiên bản, lịch sử chat, sự cố và phương án

**Files:**
- Create/Modify: `apps/api/app/services/trip/replan.py` (port đủ), `apps/api/app/services/trip/store.py`, `apps/api/app/api/routes/trips.py`, `tests/trip/test_versions_api.py`, `tests/trip/test_replan.py`, `tests/trip/test_disruptions_api.py`

**Interfaces:**
- Consumes: rules, places.`similar_places`, distance.`prefetch`.
- Produces: `replan.propose(trip, itin, places, d, candidates_fn, hub=None) -> list[ProposalOption] | NoFeasible`, `InvalidDisruption`, `NoFeasible`, `ProposalOption` như Travility. Route:
  - `PATCH /api/trips/{id}/pins` `{place_id, pinned}` → `{pinned_place_ids}`; Place không có trong bản mới nhất → 422.
  - `GET /api/trips/{id}/messages` → `[{role, text, version}]`.
  - `POST /api/trips/{id}/restore/{version}` → event `itinerary` + `pinned_place_ids`; khác số ngày → 422; tự bỏ ghim Place không có trong bản cũ và log message.
  - `POST /api/trips/{id}/disruptions` `{version, kind, day_index, stop_index?, minutes?}` → `{proposal_id, options}` | `{proposal_id, no_feasible}`; version cũ → 409 `"Lịch trình đã có bản mới hơn, hãy mở bản mới nhất rồi thử lại."`; Stop ghim / không tồn tại → 422.
  - `POST /api/trips/{id}/proposals/{pid}/apply` `{option}` → event `itinerary`; áp lại cùng option → trả version cũ; option khác → 409.

- [ ] **Step 1: Port test** `server/tests/test_versions_api.py`, `test_replan.py`, `test_disruptions_api.py` → `tests/trip/`, dùng `trip_places` (đủ một Place `an-uong` thay thế cùng kind, một `tham-quan` trong nhà để thay khi mưa).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** `replan.py` đủ + store + route.
- [ ] **Step 4: Run** `tests/trip/` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(trip): pins, version restore, chat history and disruption proposals`

### Task 8: Góp ý nhóm

**Files:**
- Modify: `apps/api/app/services/trip/flow.py`, `store.py`, `apps/api/app/api/routes/trips.py`
- Create: `tests/trip/test_group_reviews_api.py`

**Interfaces:**
- Consumes: `followup.review_group_feedback`.
- Produces: `POST /api/trips/{id}/group-reviews` `{source_version ≥1, feedback 1..2000 (strip, không rỗng)}` → SSE kết thúc bằng `group_review_preview {review}` hoặc `error {code:"stale_base", status:409}`; `POST …/group-reviews/{rid}/apply` → event `itinerary` (409 khi base cũ hơn bản mới nhất); `POST …/cancel` → `{status:"cancelled"}`. Một Trip chỉ có tối đa một review `pending` (kiểm tra bằng code trước khi insert, thay cho unique index một phần của Postgres).

- [ ] **Step 1: Port test** `server/tests/test_group_reviews_api.py`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests/trip/` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(trip): group review previews applied by the organizer`

### Task 9: Khoá quyền sở hữu toàn bộ route

**Files:**
- Create: `tests/trip/test_ownership.py`
- Modify: `apps/api/app/api/routes/trips.py` (nếu test lộ lỗ)

- [ ] **Step 1: Viết** `test_other_users_trip_is_404_everywhere`: user A có Trip có v1 + một proposal + một group review pending; user B gọi `GET /api/trips/{id}`, `GET …/messages`, `PATCH …/pins`, `POST …/restore/1`, `POST …/disruptions`, `POST …/proposals/{pid}/apply`, `POST /api/trips` với `trip_id`, `POST …/plan`, `POST …/replan`, `POST …/group-reviews`, `…/apply`, `…/cancel` → tất cả 404; `GET /api/trips` của B rỗng. Thêm `test_provider_role_forbidden`: user role `provider` → 403 ở `GET /api/trips`.
- [ ] **Step 2: Run** — Expected: PASS ngay hoặc FAIL chỉ ra route hở → sửa route đó.
- [ ] **Step 3: Run toàn bộ** `tests/` — Expected: PASS, không giảm số test cũ.
- [ ] **Step 4: Commit** `test(trip): lock trip ownership across every route`

### Task 10: Client API, SSE và helper thuần

**Files:**
- Create: `apps/web/src/api/trips.ts`, `apps/web/src/components/trip/sse.ts`, `place.ts`, `layout.ts`, `tripPrint.ts`, và `*.test.ts` tương ứng
- Modify: `apps/web/package.json` (`"test": "node --test src/components/trip/*.test.ts"`), `apps/web/tsconfig.json` (`exclude` thêm `"src/**/*.test.ts"`)

**Interfaces:**
- Produces (`api/trips.ts`, port `client/src/api.ts`): toàn bộ type (`Place`, `Stop`, `Leg`, `Day`, `Conflict`, `Itinerary`, `AgentEvent`, `GroupReview`, `Proposal`, `ProposalOption`, `TripSummary`, `TripView`, `Message`, `Answers`, `Question`, `Clarify`, `ConfirmReplan`, `DisruptionReq`, `ItineraryEvent`, `RestoreEvent`) và hàm (`streamTrip(message, tripId, onEvent)`, `streamPlan(tripId, answers, onEvent)`, `streamReplan(c, onEvent)`, `streamGroupReview(tripId, sourceVersion, feedback, onEvent)`, `listTrips()`, `getTrip(id, version?)`, `getMessages(id)`, `setPin`, `restoreVersion`, `reportDisruption`, `applyProposal`, `applyGroupReview`, `cancelGroupReview`, `mealOf`, `vnd`, `INTENT_LABELS`, `intentChips`, `clarifyAfter`, `confirmAfter`, `searchLine`, `viewingOld`, `noFeasibleText`, `optionPlaces`, `rainable`, `signed`, `tripLabel`, `ApiError`) — **bỏ tham số `token`**. Hàm JSON dùng `api` (axios, `withCredentials`) từ `api/client.ts`; hàm stream dùng `fetch('/api/…', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}})` + `parseSSE`; 401 → `window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))` rồi throw `Error('unauthorized')`.
- `sse.ts`, `place.ts`, `layout.ts`, `tripPrint.ts`: copy nguyên; import nội bộ của chúng chỉ được là `import type` (để `node --test` chạy file `.ts` không cần bundler). Test import bằng đuôi `.ts`, ví dụ `import { parseSSE } from './sse.ts'`, dùng `node:test` + `node:assert/strict`.

- [ ] **Step 1: Port test** `client/src/sse.test.ts`, `place.test.ts`, `layout.test.ts`, `tripPrint.test.ts` sang `node:test` (`describe/it` → `test`, `expect(a).toEqual(b)` → `assert.deepEqual(a,b)`). Phần `api.test.ts` chỉ giữ test của hàm thuần (`clarifyAfter`, `confirmAfter`, `mealOf`, `viewingOld`) — chuyển hàm thuần đó sang `components/trip/tripState.ts` (không import runtime) và test ở `tripState.test.ts`; `api/trips.ts` re-export.
- [ ] **Step 2: Run** `npm test` — Expected: FAIL (file chưa có).
- [ ] **Step 3: Implement** theo Interfaces.
- [ ] **Step 4: Run** `npm test` và `npm run build` — Expected: PASS cả hai.
- [ ] **Step 5: Commit** `feat(web): trip API client and pure trip helpers`

### Task 11: Bản đồ 3D TripMap

**Files:**
- Create: `apps/web/src/components/trip/TripMap.tsx`, `apps/web/src/components/trip/landmarkLayer.ts`
- Modify: `apps/web/src/styles.css` (lớp `.trip-pin`, `.trip-pin--searching` nhấp nháy, `.trip-pin--selected`)

**Interfaces:**
- Consumes: `api/trips.ts` types, `place.ts` (`tourStops`, `selectedPlace`, `Selected`), `LEG_COLORS`, `components/3d/landmark/*` (`loadLandmarkModel`, `DEFAULT_CALIBRATIONS`, `sanitizeCalibration`), `/models-3d/calibration`.
- Produces:
  - `TripMap(props: { center: [number, number]; searchPins: Place[]; itinerary: Itinerary | null; places: Record<string, Place>; selected: Selected; onSelect(s: Selected): void; padding: { left: number; right: number }; pins: number[]; onPin?(placeId: number, pinned: boolean): void })` — cùng props với `MapView` của Travility.
  - `createLandmarkLayer(id: string, calibrations: ModelCalibration[]) -> CustomLayerInterface` — một custom layer three.js vẽ mọi mô hình GLB trong `DEFAULT_CALIBRATIONS` (ghép calibration từ API) tại toạ độ của chúng; ma trận theo cách `Map3DLandmarkViewer.renderFrame` làm cho một mô hình (`MercatorCoordinate.fromLngLat` + scale + rotation), lặp cho từng mô hình. Mô hình lỗi tải → bỏ qua mô hình đó, log `console.warn`.
- Hành vi (port `MapView.tsx`):
  - `new goongjs.Map({style: goong_map_dark.json, center, zoom: 12.5, pitch: 45})`, `accessToken` như `Map3DLandmarkViewer`. Chưa có lịch → `flyTo(center, zoom 12.5, pitch 45)`.
  - Lịch đổi → dừng tour, vẽ một source GeoJSON `LineString` mỗi ngày (thứ tự Hub/Stay → Stop… → Hub/Stay, nối thẳng các toạ độ; màu `LEG_COLORS[day % n]`), marker HTML đánh số theo thứ tự trong ngày, thu vừa toàn tuyến với `padding`.
  - `searchPins` → marker `.trip-pin--searching`.
  - Chọn Stop → `flyTo({center, zoom: 15, pitch: 60, duration: 1800})` + popup `PlacePopup` (nút 📌 khi có `onPin`).
  - Nút "▶ Xem hành trình" (góc dưới giữa, nền `var(--amber)`): lần lượt `onSelect` từng `tourStops(itinerary)`, mỗi bước `bearing += 40`, chờ hết `flyTo` + 1.2 s; hiện `Ngày {d+1} · điểm {i+1}/{n} · {tên}` + nút "■ Dừng"; người dùng kéo bản đồ (`movestart` có `originalEvent`) → dừng; hết tour → thu vừa toàn tuyến. `prefers-reduced-motion` → `duration: 0`.
  - Lớp landmark thêm sau `style.load`.

- [ ] **Step 1: Implement** `landmarkLayer.ts` rồi `TripMap.tsx`.
- [ ] **Step 2: Run** `npm run build` — Expected: PASS.
- [ ] **Step 3: Commit** `feat(web): 3D trip map with route lines, landmarks and journey tour`

### Task 12: Bảng Chat, Timeline và các thẻ

**Files:**
- Create: `apps/web/src/components/trip/Rail.tsx`, `FloatingPanel.tsx`, `ChatPanel.tsx`, `ClarifyCard.tsx`, `ConfirmCard.tsx`, `Timeline.tsx`, `PlacePopup.tsx`, `PlaceThumb.tsx`, `ProposalPanel.tsx`, `GroupReviewPanel.tsx`, `TripPrintView.tsx`
- Modify: `apps/web/src/styles.css` (`@media print` từ `client/src/index.css` của Travility: ẩn `.app-shell`, chỉ in `TripPrintView`)

**Interfaces:**
- Consumes: Task 10, Task 11 types.
- Produces: các component cùng props với bản Travility (đọc trực tiếp file nguồn để lấy props); `Rail` bỏ nút "Hệ thống" và "Đăng xuất" (đăng xuất dùng menu của site), giữ "＋ Chuyến mới" + "🗂 Lịch trình của tôi".
- Đổi class Tailwind màu theo bảng ở Global Constraints; giữ nguyên chữ tiếng Việt, cấu trúc, aria-label.

- [ ] **Step 1: Port** từng component, đổi màu.
- [ ] **Step 2: Run** `npm run build` — Expected: PASS.
- [ ] **Step 3: Commit** `feat(web): port trip chat, timeline, proposal, group review and print panels`

### Task 13: Trang TripChatPage và thay route `/chat`

**Files:**
- Create: `apps/web/src/pages/TripChatPage.tsx`
- Modify: `apps/web/src/router.tsx`
- Delete: `apps/web/src/pages/ChatPage.tsx`

**Interfaces:**
- Consumes: Task 10–12.
- Produces: `TripChatPage` = state + handler của `client/src/App.tsx` (bỏ `token`, `Login`, `SystemPage`, `logout`). Khung: `<div className="app-shell relative h-[calc(100vh-64px)] overflow-hidden">` dưới header của `AppLayout`; `TripMap` phủ khung; `Rail` trái (rộng 64px), `FloatingPanel` chat trái (`left = 64 + 340 + 16` khi mở) và Timeline phải (`right = 384 + 32` khi có lịch và mở); `NARROW = '(max-width: 1099px)'`.
- Chưa đăng nhập (`useAuth().user == null`) → thay toàn khung bằng thẻ "Đăng nhập để lập và lưu lịch trình" + link `/login?next=/chat`. Role khác `traveler` → thẻ "AI Chat dành cho tài khoản du khách".
- Lắng nghe `AUTH_EXPIRED_EVENT` không cần thêm: `AppLayout` đã xử lý.

- [ ] **Step 1: Implement** trang + route; xoá `ChatPage.tsx`, sửa import còn trỏ tới nó.
- [ ] **Step 2: Run** `npm run build` và `npm test` — Expected: PASS.
- [ ] **Step 3: Rebuild** `docker compose up -d --build api web` — Expected: container `healthy`/`Up`.
- [ ] **Step 4: Smoke bằng Playwright MCP** trên `http://localhost:5173/chat` với tài khoản traveler dev (`traveler@localexplorer.ai`, mật khẩu theo `.env`/README; không có thì đăng ký mới): gõ `"Đi Sài Gòn 2 ngày, 3 triệu, 2 người, thích cafe và lịch sử"` → thấy dòng tool + pin vàng → thẻ hỏi lại → chọn → lịch 2 ngày bên phải, tuyến trên bản đồ, có mô hình 3D; bấm "▶ Xem hành trình" → camera bay, có dòng "Ngày 1 · điểm 1/…"; gõ `"đổi bữa tối ngày 1 sang chỗ khác"` → v2, Stop đổi có viền; bấm v1 → "Quay lại bản này" → v3; "Báo đóng cửa" trên một Stop → tối đa 3 phương án → Áp dụng; "☂ Giả sử mưa"; "Tôi trễ 30′"; "Góp ý nhóm" → preview → Áp dụng; "Xuất PDF" mở hộp thoại in (không bấm in — chỉ chụp màn hình trước khi `window.print`; nếu Playwright bị chặn bởi dialog thì ghi lại); `"ngày mai có mưa không"` → câu trả lời có "Open-Meteo", không tạo version; tải lại trang → tự mở chuyến vừa rồi với lịch sử chat. Chụp ảnh vào thư mục scratchpad, không lưu vào repo. Gemini lỗi quota → ghi nguyên văn lỗi trong báo cáo.
- [ ] **Step 5: Commit** `feat(web): replace /chat with the Travility trip planner page`

### Task 14: Rà soát cuối

- [ ] **Step 1:** `cd apps/api && .venv/bin/python -m pytest -q -p no:cacheprovider tests` — Expected: tất cả PASS.
- [ ] **Step 2:** `cd apps/web && npm test && npm run build` — Expected: PASS.
- [ ] **Step 3:** Cập nhật `README.md` mục chạy lần đầu: thêm lệnh import `docker compose exec api python -m scripts.import_trip_places /data/sai_gon_places.json`.
- [ ] **Step 4:** `/code-review` trên diff từ `81787f7` + `superpowers:requesting-code-review`; sửa phát hiện mức nghiêm trọng.
- [ ] **Step 5: Commit** `docs: document trip place import`
