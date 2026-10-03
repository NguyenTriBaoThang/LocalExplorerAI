# API MVP

Base URL: `http://localhost:8000`. Swagger UI: `/docs`. Datetime nhận ISO 8601 có timezone offset và tiền VND nhận integer.

## Health

`GET /health` returns `{ "status": "ok" }`.

## Local ML inference

Optional local supervised models are separate from the prompt-backed LLM workflows and the existing E5 semantic-search model. See [training, data provenance, artifact placement, and model safety](ml-training-and-data.md).

- `GET /api/ml/status` reports local ranker/flood bundle configuration and metadata.
- `POST /api/ml/rank-experiences` ranks feasible candidates; rank scores are not probabilities. The same local ranker can break ties among earliest feasible candidates in `POST /api/itineraries/plan` and rank re-plan replacements. Planning hard constraints remain authoritative, and responses expose `explanation.ranking_model_version` when ML ranking was used.
- `POST /api/ml/flood-risk` returns advisory flood-risk probabilities; it does not confirm a closure and does not alter routing. It returns 503 until a real-label flood bundle is installed; demo-mode bundles are rejected.

## Catalog

- `GET /api/pois` — danh sách POI.
- `GET /api/pois/{id}` — một POI.
- `GET /api/experiences` — danh sách có query filters: `intent`, `start_at`, `end_at`, `group_size`, `max_price`.
- `GET /api/experiences/{id}` — hoạt động, POI và slot.
- `GET /api/experiences/{id}/slots?start_at=...&end_at=...` — slot theo thời gian.

Catalog trả `verification_status` và `data_mode`. Dữ liệu seed là `simulated`; `available_reported: null` không có nghĩa là hết chỗ.

## Planner

`POST /api/itineraries/plan`

```json
{
  "start_at": "2026-10-01T09:00:00+07:00",
  "end_at": "2026-10-01T16:00:00+07:00",
  "group_size": 4,
  "budget_vnd": 2000000,
  "transport_mode": "driving",
  "intent_weights": {"handicraft": 1.0, "food": 0.8, "culture": 0.5},
  "locked_experience_ids": []
}
```

Response gồm `request_id`, `itinerary_id`, `data_mode`, `data_as_of`, `feasibility_status`, tổng chi phí, stops, route legs và explanation. `data_mode` là `real`, `simulated` hoặc `mixed` theo catalog được chọn; mỗi stop có `data_status`, nguồn POI/trải nghiệm/slot, `slot_confirmed_at` và `slot_expires_at`. `explanation.evidence_refs` liệt kê ID evidence được dùng. `feasibility_status` có thể là `feasible` hoặc `tentative`; no-plan trả HTTP 422 với code `NO_FEASIBLE_PLAN`. Mỗi route leg trả `distance_m`, `duration_min`, `provider`, `eta_source`, `eta_source_uri`, `eta_calculated_at`, `eta_age_seconds`, `eta_valid_until`, `is_realtime` và (khi Goong trả geometry hợp lệ) tọa độ tuyến đã giải mã. `is_realtime` hiện luôn false: ETA không phải traffic trực tiếp. Nếu gửi điểm đi thì phải gửi cả điểm về; planner tính cả đoạn cuối và áp giờ về lên chặng này.

`ROUTING_PROVIDER=goong` và `GEOCODING_PROVIDER=goong` là mặc định. Cấu hình `GOONG_API_KEY` trong file `.env` tại root; key chỉ được gửi từ API server tới Goong, không đưa xuống trình duyệt. `GOONG_ETA_TTL_SECONDS` mặc định 300 giây và `GEOCODE_CACHE_TTL_SECONDS` mặc định 86400 giây.

- `GET /api/routing/capabilities` — nhà cung cấp đã chọn, trạng thái key, phương tiện UI/API cho phép và thông tin ETA có phải realtime không. Goong hiện bật xe máy/đi bộ/ô tô; phương tiện công cộng và xe đạp bị từ chối rõ ràng, không quy đổi sang profile khác.
- `GET /api/geocoding/forward?address=...` — trả về các địa chỉ khớp, tọa độ, `place_id`, nguồn tài liệu nhà cung cấp, `resolved_at`, `valid_until` và `age_seconds`. UI yêu cầu người dùng chọn một kết quả trước khi lập lịch.

Trong Goong adapter hiện tại, mode xe máy/đi bộ/ô tô được ánh xạ lần lượt sang tham số `bike`/`foot`/`car`. Tổng quan Directions V2 nói hỗ trợ xe máy và đi bộ, nhưng bảng tham số trên tài liệu chỉ liệt kê car/bike; cần smoke-test bằng key hợp lệ với Goong trước triển khai pilot. Thiếu key trả HTTP 503; lỗi/time-out nhà cung cấp trả 502; adapter không âm thầm chuyển sang mock.

`GET /api/itineraries/{id}` tải lại kế hoạch đã lưu.

## Prompt-backed AI workflows

The versioned prompt catalog lives under `apps/api/app/prompts/`; the active version is `3.0.0`. Prompt outputs are schema-validated before use. Configure `OPENAI_API_KEY` (or a compatible endpoint via `OPENAI_BASE_URL`) to enable model-backed routes. Without it, prompt-backed calls fail closed with HTTP 503. All model-backed routes return or persist the prompt version for provenance. See [AI prompt catalog and database mapping](ai-prompt-catalog.md).

`GET /api/ai/prompts` returns the active manifest/version and the eight prompt IDs.

Legacy AI admin routes accept a valid `X-Admin-Key: $ADMIN_API_KEY` or an authenticated admin session:

- `POST /api/experiences/{id}/ai-tag` — run EXPERIENCE_TAGGER, persist tags, hands-on, indoor, primary intent, weather sensitivity, and prompt version.
- `POST /api/ai/intent-similarity` — run INTENT_SIMILARITY for two experience IDs and upsert the canonical pair into `intent_similarities`.
- `POST /api/itineraries/{id}/feedback/label` — label a submitted review and persist the feedback/training rubric fields.
- `POST /api/itineraries/{id}/weather-advisory` — assess caller-provided weather/AQI observations against scheduled outdoor stops and write expiring `WEATHER_ALERT` events. Measurements are not independently verified; the route does not infer flooding.

Traveler and provider workflows:

- `POST /api/chat/message` — run CONVERSATION_PARSER and return `structured_constraints`; this does not create an itinerary or assert availability. If the external LLM is unconfigured/unavailable or produces invalid schema output, chat can return a clearly marked `status: "fallback"` using conservative local rules. `GET /api/chat/status` exposes only the configured mode, never the key. When complete, the client maps constraints to `POST /api/itineraries/plan` (Vietnamese intent keys are accepted and normalized by the planner).
- `GET /api/auth/google/status` — reports OAuth readiness and the exact redirect URI to register; no client secret is returned. Google sign-in uses `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, and `WEB_APP_URL`.
- `POST /api/itineraries/{id}/replan-advice` with `{ "event_id": "..." }` — solver-filters feasible replacement slots, then runs REPLAN_ADVISOR and XAI_EXPLANATION. Advice is read-only and requires user confirmation.
- `POST /api/itineraries/{id}/replan-advice/accept` — accept one returned proposal. Send `event_id`, `affected_stop_id`, candidate experience/slot IDs, proposal code, and the `base_version` from advice. Stale plans return 409.
- `POST /api/providers/{provider_id}/slot-assistant/preview` — send `X-Provider-Access-Key`, a short message, and exact selected `slot_ids`. Runs PROVIDER_ASSISTANT and returns a five-minute signed confirmation token; it does not mutate availability. `PAUSE_DAY` is accepted only when the selection covers every not-yet-cancelled slot for that provider today.
- `POST /api/providers/{provider_id}/slot-assistant/confirm` — send the preview token and provider key to apply the scoped change. The provider's access key is provisioned out of band in `providers.portal_access_key`. Cancellation changes slots and emits `SLOT_CANCELLED` events for re-planning.

Provider confirmation uses `APP_SIGNING_SECRET`; production must set both `APP_SIGNING_SECRET` and `ADMIN_API_KEY`. Never expose the model key, signing secret, admin key, provider access key, or confirmation tokens in browser logs or public responses.

## Booking and payment boundary

The current booking flow supports verified-data seat holds and explicit provider capacity acceptance. See [booking and payment workflow](bookings-and-payments.md) for statuses and safety rules.

- `POST /api/bookings` — traveler requests seats for an itinerary stop; only verified POI/experience/current capacity is eligible.
- `GET /api/bookings` and `GET /api/bookings?itinerary_id=...` — signed-in traveler's booking state.
- `POST /api/bookings/{id}/cancel` — cancels an unpaid hold, or records a cancellation request after payment.
- `GET /api/bookings/{id}/history` — permission-checked booking event history.
- `GET /api/payments/status` — gateway readiness (currently disabled).
- `POST /api/bookings/{id}/checkout` — currently fails closed with `PAYMENT_GATEWAY_NOT_CONFIGURED`; it cannot collect a payment or claim payment success.
- `GET /api/provider/me/bookings` and `POST /api/provider/me/bookings/{id}/decision` — provider request inbox and accept/reject action.
- `POST /api/provider/me/bookings/{id}/cancellation-decision` — process an unpaid cancellation; paid refunds stay pending until a configured gateway confirms them.

The database has payment/refund lifecycle ledger fields, but no payment provider is selected yet; real charge, signed webhook settlement, and actual refund execution remain disabled pending that decision and credentials.

## Lỗi

```json
{
  "error": {
    "code": "NO_FEASIBLE_PLAN",
    "message": "No itinerary satisfies time, capacity, and budget constraints",
    "details": [],
    "request_id": "..."
  }
}
```

Current error codes also include `LLM_NOT_CONFIGURED`, `LLM_PROVIDER_ERROR`, `INVALID_MODEL_OUTPUT`, `ADMIN_UNAUTHORIZED`, `PROVIDER_UNAUTHORIZED`, `REPLAN_NOT_AVAILABLE`, `STALE_ITINERARY_VERSION`, `SLOT_VERSION_CHANGED`, and `INVALID_CONFIRMATION_TOKEN`.

## Accounts and role-managed workflows

- `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET/PATCH /api/auth/me`, `POST /api/auth/password` — email account lifecycle; sessions use an HTTP-only cookie. Public registration always creates a traveler.
- `GET /api/auth/google/start` — starts Google authorization-code + PKCE sign-in. Requires OAuth client settings and a registered callback URL.
- `GET /api/me/itineraries`, `POST/DELETE /api/itineraries/{id}/share`, `GET /api/shared/itineraries/{token}`, `POST /api/itineraries/{id}/feedback` — private itinerary history, revocable share URLs, and submitted traveler reviews.
- `GET /api/notifications` — active cancellation alerts for the signed-in traveler.
- `GET /api/itinerary-comparisons?first_id=...&second_id=...` and `GET /api/itineraries/{id}/versions` — compare owned itineraries and inspect saved schedule versions.
- `GET /api/experience-search?q=...&semantic=true` — optional local multilingual E5 ranking. Supports intent/topic, indoor/outdoor, slot/time, group-size, price and radius filters. The API returns HTTP 503 until the E5 package and a local model directory are configured.
- `/api/provider/*` — signed-in provider account routes for profile, own experience drafts, price/duration edits, slots, cancellations, affected-itinerary counts and operation history. New/edited experiences return to moderation.
- `/api/admin/*` — administrator dashboard/data-quality counters, user-role/account activation, provider creation, POI/experience/evidence moderation, probable duplicate discovery/explicit merge, audit history.

Sourced catalog additions:

- `POST/PATCH /api/provider/pois[/<id>]` — submit or revise the provider's POI with address and coordinates; revisions return to moderation.
- `POST /api/provider/evidence` — attach source URI/type/license, covered fields, observed time and required expiry to an owned POI or experience. Source evidence must be reviewed before approving its target.
- `POST /api/provider/experiences/{id}/slots` — requires `expires_at`; API records a provider-confirmed source and server-side `confirmed_at`. `PATCH /api/provider/slots/{id}` requires a fresh expiry to open a slot.
- Admin evidence approval rejects unlinked, expired or stale-revision evidence. POI/experience approval fails until all required fields are covered by current approved evidence; experience approval also requires an approved POI.
- Catalog payloads expose `data_mode` and `source_evidence`. Expired evidence/slot confirmations are excluded from operational recommendations. See [sourced catalog workflow](sourced-catalog.md).

Itinerary planning accepts optional origin/destination latitude/longitude and labels, plus `locked_poi_ids`. When a destination is supplied, the solver includes the last route leg in its hard return-deadline check; responses include `estimated_return_at` and the return deadline. The planner UI currently selects origin/destination from known catalog POIs; it does not geocode free-form addresses.

See [authentication and local E5 setup](auth-and-search-setup.md) for Google OAuth settings, the local-only model install switch and demo-account seeding behavior.

## Operational readiness and monitoring

- `GET /health` is liveness only; `GET /ready` checks PostgreSQL and Redis when production rate limiting is enabled.
- `GET /api/ops/status`, `/api/ops/jobs`, `/api/ops/events`, and `/api/ops/notifications` require administrator authentication. Notification monitor payloads omit destination email and message body.
- Booking request/decision transitions and provider slot cancellations enter the SMTP outbox when SMTP is configured. The background `worker` delivers and retries; without SMTP, email is reported disabled and existing in-app cancellation notices remain.
- API request logs include `X-Request-ID`; booking/audit/event records include the same identifier for cross-checking. No query strings, bodies, or credentials are written to request logs.
- Production Compose enables Redis-backed rate limits. Set `TRUSTED_PROXY_IPS` only to trusted proxy IP/CIDR ranges; see [production operations](operations.md) for backups, restore drills, and release checks.
