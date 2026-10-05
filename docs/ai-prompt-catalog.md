# AI prompt catalog — PRD 3.0

The active catalog is `3.0.0`, declared in `apps/api/app/prompts/manifest.json`. Each template is immutable under `apps/api/app/prompts/v3_0_0/`; create a new version directory and change the manifest to revise prompt behavior. `PromptRunner` loads the active template and validates its result against the corresponding Pydantic schema before any write. The OpenAI-compatible adapter sends deterministic JSON-mode requests; provider errors, missing configuration, and invalid output fail closed.

## Prompt/API/data mapping

| Prompt | API / flow | Validated output and persistence |
|---|---|---|
| `CONVERSATION_PARSER` | `POST /api/chat/message` | Returns `StructuredConstraints` and prompt version. The existing `itineraries` fields can store weights and travel mode, but parsed chat is not stored: there is no conversation table. Client must supply the trip date when translating `HH:mm` values into the planner's timezone-aware `start_at`/`end_at`. |
| `EXPERIENCE_TAGGER` | `POST /api/experiences/{id}/ai-tag` | Updates `experiences.intent_tags`, `is_hands_on`, `is_indoor`/legacy `indoor`, `primary_intent`, `weather_sensitivity`, and `tagger_prompt_version`. |
| `INTENT_SIMILARITY` | `POST /api/ai/intent-similarity` | Upserts canonical `(experience_a_id, experience_b_id)` pair, semantic/tag/final scores, substitution flag and `prompt_version` in `intent_similarities`. Tag overlap is Jaccard over normalized tags. LLM-produced similarities remain `is_human_reviewed=false`. |
| `REPLAN_ADVISOR` | `POST /api/itineraries/{id}/replan-advice` | Only receives solver-filtered, time/capacity/budget/route-feasible candidates. Proposal IDs, intent sets, cost/time deltas and scheduled return time are checked against solver facts. Advice is audit-logged in `decision_logs`; no itinerary change occurs until explicit acceptance. |
| `XAI_EXPLANATION` | Same replan-advice flow | Uses proposal facts only; explanation is returned and recorded in `decision_logs.explanation_vi`. |
| `PROVIDER_ASSISTANT` | Provider `/slot-assistant/preview` then `/confirm` | Preview scopes the action to explicit provider-owned slot IDs. A short-lived signed token plus slot versions prevents unconfirmed or stale writes. Confirm updates `experience_slots`; cancellations also emit `SLOT_CANCELLED` `events`, which feed re-planning. |
| `FEEDBACK_LABELER` | `POST /api/itineraries/{id}/feedback/label` | Adds `feedbacks` row with rubric grade, justification, objective ratio, training flag and `labeler_prompt_version`; original review/rating is retained. |
| `WEATHER_AQI_ADVISOR` | `POST /api/itineraries/{id}/weather-advisory` | Considers only actual outdoor itinerary stops and caller-provided measurements, returns an advisory, and writes expiring `WEATHER_ALERT` events against affected POIs with measurements and prompt version in event metadata. It never infers flooding. |

## Alignment notes and deliberate constraints

- The prompt says re-plan may provide up to three candidates, but the declared output only has codes `B` and `C`. This integration honors the concrete output schema and returns at most two candidates; a third requires a future schema/version change.
- The current itinerary schema has no home/origin location. Re-plan's `estimated_return_time` therefore means the scheduled end of the final itinerary stop; the API marks this basis and does not claim a home-arrival estimate.
- `EXPERIENCE_TAGGER`/`WEATHER_AQI_ADVISOR` use `experiences.is_indoor` as canonical while synchronizing the legacy `indoor` field used by existing API/seed code.
- PRD intent names are Vietnamese, while seeded experience tags and legacy planner clients use English aliases. The planner and re-plan normalizer bridge `thủ_công`↔`handicraft`, `ẩm_thực`↔`food`, `văn_hóa`↔`culture`, and `thư_giãn`↔`relaxation`.
- The team schema has no conversation-history, weather-provider provenance, or provider-preview audit table. Chat parse is returned but not persisted; weather source is explicitly marked caller-provided/unverified; provider cancellation creates the existing event record. We do not add unrelated tables for those records.
- A model's claim about current availability is never treated as authoritative: slot/capacity writes require explicit provider confirmation and checked database scope/version. A null `available_reported` remains unknown.
- Weather observations supplied to the endpoint are not independently fetched or verified. `rain_mm_per_hour > 10` is enforced as rainy/indoor-priority; AQI is supplied as PM2.5, and no route/flood inference is made.

## Database migration

Revision `0003_prompt_workflows` follows `0002_team_database_architecture` and adds the tagger provenance fields, similarity substitution/provenance fields, and feedback label fields/checks. The production migration chain targets PostgreSQL/PostGIS; apply via `alembic upgrade head` after configuring `DATABASE_URL`. SQLite test fixtures create metadata directly (the earlier 0002 migration contains PostgreSQL-specific data transforms). The new revision's feedback-column/check-constraint operations use Alembic batch mode for SQLite compatibility. The application code does not auto-migrate on startup.

## Configuration and access

Set `OPENAI_API_KEY`, and optionally `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_TIMEOUT_SECONDS`. Chat alone has an explicitly disclosed, schema-validated local fallback enabled by `LLM_FALLBACK_ENABLED`; it returns `status: fallback` and does not claim to be an LLM. Other prompt-backed routes fail closed with 503/502 when credentials or a valid model response are unavailable. In production also set `APP_SIGNING_SECRET`. Admin labeling/tagging/similarity/weather routes require an admin session with the `admin:ai_tools` permission. Provider endpoints accept a signed-in provider account; the legacy `X-Provider-Access-Key` (`providers.portal_access_key`) is still honoured for now but is deprecated and scheduled for removal. Never commit secrets or log provider preview tokens.

Prompt requests include the submitted chat text, business/catalog descriptions, itinerary facts, weather measurements, or review text as applicable; this data is sent to the configured LLM endpoint. Provider confirmation SMS copy is returned as text only—the repository has no Zalo/SMS delivery connector, and weather observations are not fetched from Open-Meteo here.

