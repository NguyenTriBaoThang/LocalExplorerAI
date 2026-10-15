# MVP API

The API accepts ISO 8601 timestamps with a timezone offset (for example, Vietnam time `+07:00`); slots are normalized and stored in UTC. SQLite does not store timezone information, so the model converts offsets to UTC when writing and restores UTC when reading.

Base URL: `http://localhost:8000`. Swagger UI: `/docs`. Datetimes must use ISO 8601 with a timezone offset; VND amounts must be integers.

## Health

`GET /health` returns `{ "status": "ok" }`.

## Local ML inference

Local ranker inference is separate from prompt-backed LLM workflows and the E5 semantic-search model. The active ranker defaults to `rule-baseline-v1`. The explicitly marked bootstrap bundle can run only as an opt-in pilot; it is not production-eligible. See [training, data provenance, artifact placement, and model safety](ml-training-and-data.md).

- `GET /api/ml/status` reports active ranker, ML bundle eligibility, and whether the rule baseline is serving as fallback.
- Experience-ranker bundles with a model SHA-256 are integrity-checked before loading. The verified trainer emits that checksum and explicit human-label/deployment metadata. Generic weak-label bundles remain blocked; only the exact `bootstrap_pilot` artifact can be enabled with `ENABLE_BOOTSTRAP_RANKER=true` for a controlled experiment.
- `POST /api/ml/rank-experiences` ranks feasible candidates; rank scores are not probabilities. The same ranker breaks ties among earliest feasible candidates in `POST /api/itineraries/plan` and orders re-plan replacements. Planning hard constraints remain authoritative. Planner explanations expose `ranking_source` and `ranking_model_version`; bootstrap plans also display an experimental weak-label warning.
- `POST /api/ml/flood-risk` returns advisory flood-risk probabilities; it does not confirm a closure and does not alter routing. It returns 503 until a real-label flood bundle is installed; demo-mode bundles are rejected.

## Catalog

- `GET /api/pois` — list POIs.
- `GET /api/pois/{id}` — one POI.
- `GET /api/experiences` — list with query filters: `intent`, `start_at`, `end_at`, `group_size`, `max_price`.
- `GET /api/experiences/{id}` — experience, POI, and slots.
- `GET /api/experiences/{id}/slots?start_at=...&end_at=...` — slots within a time range.

The catalog returns `verification_status` and `data_mode`. Seed data is `simulated`; `available_reported: null` does not mean sold out.

## Planner

`GET /api/pois/{id}` returns the POI detail fields (including source-backed `details`, image/license metadata, current evidence, and linked experience summaries). The crawler workflow is documented in [District 1 catalog crawl and display](district1-place-catalog.md).

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

The response includes `request_id`, `itinerary_id`, `data_mode`, `data_as_of`, `feasibility_status`, total cost, stops, route legs, and an explanation. `data_mode` is `real`, `simulated`, or `mixed` according to the selected catalog; each stop has `data_status`, POI/experience/slot sources, `slot_confirmed_at`, and `slot_expires_at`. `explanation.evidence_refs` lists the evidence IDs used. `feasibility_status` can be `feasible` or `tentative`; if no plan exists, the API returns HTTP 422 with code `NO_FEASIBLE_PLAN`. Each route leg returns `distance_m`, `duration_min`, `provider`, `eta_source`, `eta_source_uri`, `eta_calculated_at`, `eta_age_seconds`, `eta_valid_until`, `is_realtime`, and (when Goong returns valid geometry) decoded route coordinates. `is_realtime` is currently always false: the ETA is not live traffic. If an origin is supplied, a destination is required too; the planner computes the final leg and applies the return deadline to it.

`ROUTING_PROVIDER=goong` and `GEOCODING_PROVIDER=goong` are the defaults. Configure `GOONG_API_KEY` in the root `.env` file or the admin integrations screen; the key is sent only from the API server to Goong, never to the browser. `GOONG_ETA_TTL_SECONDS` defaults to 300 seconds and `GEOCODE_CACHE_TTL_SECONDS` to 86400 seconds.

- `GET /api/routing/capabilities` — selected provider, key status, UI/API-supported travel modes, and whether the ETA is real-time. Goong currently enables motorcycle/walking/car; public transit and bicycle requests are explicitly rejected rather than remapped to another profile.
- `GET /api/geocoding/forward?address=...` — returns matching addresses, coordinates, `place_id`, provider source, `resolved_at`, `valid_until`, and `age_seconds`. The UI requires the user to select a result before planning.

In the current Goong adapter, motorcycle/walking/car modes map respectively to `bike`/`foot`/`car`. The Directions V2 overview says it supports motorcycle and walking, but the parameter table in the documentation lists only car/bike; smoke-test using a valid Goong key before a pilot. A missing key returns HTTP 503; provider errors/timeouts return 502; the adapter does not silently switch to a mock.

`GET /api/itineraries/{id}` reloads a saved plan.

## Prompt-backed AI workflows

The versioned prompt catalog lives under `apps/api/app/prompts/`; the active version is `3.0.0`. Prompt outputs are schema-validated before use. Configure `OPENAI_API_KEY`, `GEMINI_API_KEY`, or an admin-managed OpenAI-compatible provider to enable model-backed routes. Chat retains its clearly marked local fallback if the external LLM is unavailable; other structured workflows report an error rather than fabricating a result. All model-backed routes return or persist the prompt version for provenance. See [AI prompt catalog and database mapping](ai-prompt-catalog.md) and [integration settings](integration-settings.md).

`GET /api/ai/prompts` returns the active manifest/version and the eight prompt IDs.

Legacy AI admin routes accept a valid `X-Admin-Key: $ADMIN_API_KEY` or an authenticated admin session:

- `POST /api/experiences/{id}/ai-tag` — run EXPERIENCE_TAGGER, persist tags, hands-on, indoor, primary intent, weather sensitivity, and prompt version.
- `POST /api/ai/intent-similarity` — run INTENT_SIMILARITY for two experience IDs and upsert the canonical pair into `intent_similarities`.
- `POST /api/itineraries/{id}/feedback/label` — label a submitted review and persist the feedback/training rubric fields.
- `POST /api/itineraries/{id}/weather-advisory` — assess caller-provided weather/AQI observations against scheduled outdoor stops and write expiring `WEATHER_ALERT` events. Measurements are not independently verified; the route does not infer flooding.

Traveler and provider workflows:

- `POST /api/chat/message` — run CONVERSATION_PARSER and return `structured_constraints`; this does not create an itinerary or assert availability. If the external LLM is unconfigured/unavailable or produces invalid schema output, chat can return a clearly marked `status: "fallback"` using conservative local rules. `GET /api/chat/status` exposes only the configured mode, never the key. When complete, the client maps constraints to `POST /api/itineraries/plan` (Vietnamese intent keys are accepted and normalized by the planner).
- `GET /api/auth/google/status` — reports OAuth readiness and the exact redirect URI to register; no client secret is returned. Google sign-in uses environment values or the encrypted admin-managed Google OAuth configuration.
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
- `GET /api/payments/status` — selected MoMo/VNPay provider and provider readiness, with no secret values returned.
- `POST /api/bookings/{id}/checkout` — creates or reuses a server-generated MoMo/VNPay checkout session while configuration is valid; otherwise fails closed.
- `GET /api/payments/vnpay/return` — signature-checked browser return for display only; does not update payment state.
- `GET /api/payments/vnpay/ipn` — public, signed and idempotent VNPay settlement callback. VNPay must be able to reach this URL over HTTPS.
- `GET /api/payments/momo/return` — browser return for display only; does not update payment state.
- `POST /api/payments/momo/ipn` — public, signed and idempotent MoMo settlement callback; MoMo must be able to reach this URL over HTTPS.
- `GET /api/provider/me/bookings` and `POST /api/provider/me/bookings/{id}/decision` — provider request inbox and accept/reject action.
- `POST /api/provider/me/bookings/{id}/cancellation-decision` — process an unpaid cancellation; paid refunds stay pending until a configured gateway confirms them.

VNPay/MoMo checkout and IPN settlement are implemented but activate only after merchant credentials and public HTTPS callback URLs are configured. Refund execution remains disabled; paid cancellation and late-capture cases require manual reconciliation. See [booking and payment workflow](bookings-and-payments.md) and [integration settings](integration-settings.md) for setup and constraints.

## Errors

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
