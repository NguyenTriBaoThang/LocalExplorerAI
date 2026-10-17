# Travel Chat Routing Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Route each new chat message to trip planning, grounded travel information, or a polite out-of-scope response; ask for missing route inputs; and show an itinerary map/list preview before saving.

**Architecture:** The browser sends the latest user message separately from prior planning turns and selected trip context. The API classifies only the latest message, then calls the existing constraint parser, a travel-answer prompt, a deterministic out-of-scope response, or the Open-Meteo forecast adapter. Typed responses let the page update planner constraints only for planning messages. Route readiness additionally requires a chosen trip date, origin, return point, and explicitly selected travel mode. A new read-only planner path returns the same solver output without persistence; a confirmation path recomputes and compares the reviewed stop/slot/time/cost signature before saving. The chat page displays that preview in a map and ordered list beside the chat. TravilityV2 is copied as a sanitized source reference under `references/TravilityV2/`.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, the existing structured LLM provider and prompt catalog, Open-Meteo via `httpx`, React, TypeScript.

**Spec:** `docs/superpowers/specs/2026-10-17-travel-chat-routing-design.md`

## Global Constraints

- Resolve relative weather dates in `Asia/Ho_Chi_Minh`.
- Prefer an explicit location/date in the latest message; otherwise use the selected destination/date; ask for a location instead of assuming Ho Chi Minh City.
- Include the forecast location, date, retrieval/update time, and Open-Meteo attribution; do not invent a forecast when data is missing.
- Do not treat model knowledge as proof of live weather, opening hours, prices, transit status, or availability.
- Do not add server-side chat persistence, database tables, migrations, a new weather provider, or a paid API key requirement.
- Version changed prompts through a new catalog directory and manifest update; do not edit the active prompt version in place.
- Keep planner constraints and the HUD unchanged for travel-information and out-of-scope responses.
- Ask for explicit date, origin, return point, and travel mode before enabling preview; interests remain optional.
- Preview does not write to the database. Save revalidates the stop, slot, time, and cost signature and requires another confirmation if it changed.
- The TravilityV2 reference copy includes tracked and untracked source edits but excludes Git metadata, `.env` secrets, installed dependencies, build output, caches, browser artifacts, and personal agent memory.
- Do not modify the pre-existing untracked `.DS_Store` or `.playwright-mcp/` files.
- Do not add or run tests unless the user asks to test or verify the implementation.
- Do not commit unless the user asks.

## Review Focus

- A standalone weather question after a completed plan must not replay the generic planner confirmation.
- A missing weather location must trigger a location question rather than silently defaulting to a city.
- A forecast-provider failure or unsupported forecast date must not produce a guessed weather claim.
- Out-of-scope and travel-information replies must preserve the prior constraints and constraint HUD.
- A planning update must use prior planning turns and the last accepted structured constraints to recover values; travel-information turns stay out of parser history.
- Without an LLM, weather and out-of-scope handling must remain distinct from planner fallback and other travel Q&A must not be mislabeled as out of scope.
- Missing route inputs must prompt instead of inheriting a silent date or transport default.
- Preview is read-only; matching confirmation creates the reviewed plan; changed plan signature returns a replacement preview without persisting.
- The map markers, route data, and ordered list reflect the same preview stops.
- The TravilityV2 snapshot preserves current source edits and untracked WIP while omitting secrets and generated/runtime directories.

---

## File Structure

- `apps/api/app/schemas/ai.py` defines validated chat request context, route decisions, and forecast response fields.
- `apps/api/app/prompts/manifest.json` and `apps/api/app/prompts/v3_1_0/` version the new routing and travel-answer prompts while preserving the existing prompt set.
- `apps/api/app/services/open_meteo_service.py` owns forecast HTTP retrieval, validation, caching, and source metadata.
- `apps/api/app/services/chat_response_service.py` owns intent routing, bounded POI context assembly, travel answers, and offline route behavior.
- `apps/api/app/api/routes/chat.py` orchestrates the service and returns the typed response.
- `apps/web/src/types/index.ts` and `apps/web/src/api/client.ts` define the new request/response contract.
- `apps/web/src/pages/ChatPage.tsx` sends current message and trip context, and only applies constraint updates for planner replies.
- `apps/api/app/services/planner_service.py`, `apps/api/app/schemas/planner.py`, and `apps/api/app/api/routes/planner.py` add read-only preview and revalidated confirmation while preserving the existing direct plan endpoint.
- `apps/web/src/components/map/MapAdapter.tsx` is reused for the preview map; `ChatPage.tsx` renders the matching ordered stop list and invalidates previews when inputs change.
- `references/TravilityV2/LOCAL_REFERENCE.md` documents the isolated source snapshot and exclusions while preserving TravilityV2's original README.
- `docs/ai-prompt-catalog.md` records the added chat prompts and their behavior.

## Tasks

### Task 1: Define the chat request and response contract

**Files:**
- Modify: `apps/api/app/schemas/ai.py`
- Modify: `apps/web/src/types/index.ts`
- Modify: `apps/web/src/api/client.ts`

**Interfaces:**
- `ChatMessage.message: str` is the latest user message only.
- `ChatMessage.prior_user_messages: list[str]` carries at most 30 previous planning turns for parser context; the latest message plus prior turns has a 3,900-character aggregate limit, matching the current UI guard.
- `ChatTripContext` carries `trip_date: date | None`, `destination: ChatDestinationContext | None`, a boolean planner-context hint, and the last accepted planner constraints for incremental updates.
- `ChatDestinationContext` carries `name: str`, `latitude: float`, and `longitude: float`, with geographic bounds validated.
- `ChatMessage` also carries `language: Literal["vi", "en"]`, `conversation_id: str | None`, and `trip_context: ChatTripContext | None`.
- `ChatRoute = Literal["planning", "travel_information", "out_of_scope"]`.
- `ChatReply` includes `intent`, `reply`, existing fallback metadata, and optional `structured_constraints` and `weather_forecast`; only a planning reply has `structured_constraints`.
- `StructuredConstraints.trip_date` carries the most recent explicit trip date or the selected date context. `ChatWeatherForecast` carries location, local forecast date, precipitation probability, precipitation sum in millimeters, retrieval time, and Open-Meteo attribution/source URLs.
- TypeScript `ChatMessageRequest` mirrors `ChatMessage`; `sendChatMessage(request: ChatMessageRequest): Promise<ChatReply>` posts it to `/chat/message`.

- [x] Add strict Pydantic models for the request context, route literal, forecast data, and chat response fields in `apps/api/app/schemas/ai.py`.
- [x] Update TypeScript `ChatReply` and request types to match the Pydantic contract, including nullable/optional planner and weather fields.
- [x] Change `sendChatMessage` to accept the typed request object and send it unchanged to `/chat/message`.

### Task 2: Add versioned intent-routing and travel-answer prompts

**Files:**
- Modify: `apps/api/app/prompts/manifest.json`
- Create: `apps/api/app/prompts/v3_1_0/` with the existing eight prompt files copied unchanged
- Create: `apps/api/app/prompts/v3_1_0/CHAT_INTENT_ROUTER.md`
- Create: `apps/api/app/prompts/v3_1_0/TRAVEL_ASSISTANT.md`
- Modify: `apps/api/app/schemas/ai.py`

**Interfaces:**
- `ChatIntentDecision.intent: ChatRoute` and `topic: Literal["weather", "place", "activity", "opening_hours", "food", "transport", "other"] | None`.
- `TravelQuestionAnswer.reply: str`.
- `PromptRunner.run("CHAT_INTENT_ROUTER", {"message": latest_message, "has_planning_context": ...}, ChatIntentDecision)` routes the latest message and uses the boolean hint only to recognize short planner answers.
- `PromptRunner.run("TRAVEL_ASSISTANT", {"message": latest_message, "language": ..., "trip_context": ..., "catalog_context": ...}, TravelQuestionAnswer)` produces a concise answer grounded in supplied facts.

- [x] Add the two strict output models in `apps/api/app/schemas/ai.py`.
- [x] Create `v3_1_0` by copying all eight existing prompt files from `v3_0_0` byte-for-byte so existing workflows keep working under the manifest version.
- [x] Write the router prompt to classify itinerary changes, travel information, and unrelated topics from the latest message only; set a travel topic when applicable.
- [x] Write the travel-answer prompt to use supplied catalog/context facts, avoid unsupported operational claims, and answer in the user's language.
- [x] Set the manifest version to `3.1.0` and add both prompt IDs without removing existing IDs.

### Task 3: Add daily weather forecast retrieval

**Files:**
- Modify: `apps/api/app/services/open_meteo_service.py`

**Interfaces:**
- `daily_forecast(latitude: float, longitude: float, forecast_date: date) -> ChatWeatherForecast`.
- Raise `OpenMeteoUnavailable` when the provider errors, omits required values, returns invalid data, or does not cover the requested date.

- [x] Implement `daily_forecast` using the configured Open-Meteo forecast URL, `Asia/Ho_Chi_Minh`, daily precipitation probability/amount, and the requested local date.
- [x] Validate coordinates, requested date range, response date alignment, finite numeric values, and required source fields before returning data.
- [x] Cache by rounded coordinates and forecast date using the existing TTL setting; expire old entries and bound cache size as `current_conditions` does.
- [x] Return source URLs, attribution, and a timezone-aware retrieval timestamp with the validated forecast.

### Task 4: Route chat requests and produce grounded replies

**Files:**
- Create: `apps/api/app/services/chat_response_service.py`
- Modify: `apps/api/app/api/routes/chat.py`
- Modify: `apps/api/app/services/offline_chat_fallback.py`

**Interfaces:**
- `route_chat_message(payload: ChatMessage, provider: StructuredOutputProvider, db: Session) -> ChatReply`.
- The service uses `ChatIntentDecision` for configured LLM routing; its offline classifier examines only `payload.message`.
- `build_planning_context(prior_user_messages: list[str], latest_message: str) -> str` serializes only traveler turns for `CONVERSATION_PARSER`.
- `resolve_weather_location(message: str, trip_context: ChatTripContext, db: Session) -> ChatLocationContext | None` resolves an explicit catalog location first, then the selected destination; unresolved location returns a clarification instead of calling Open-Meteo.
- `resolve_weather_date(message: str, trip_date: date | None, today: date) -> date` resolves an explicit date/relative date in `Asia/Ho_Chi_Minh`, otherwise uses the selected trip date.

- [x] Add `route_chat_message` to classify the latest turn and dispatch to planning, travel-information, or out-of-scope handling.
- [x] For planning, rebuild the transcript from prior planning turns plus the latest message, call the existing `CONVERSATION_PARSER`, and return `intent="planning"` with constraints and existing fallback metadata.
- [x] For travel questions, assemble only matching local POI/experience facts; answer stored catalog facts through the travel prompt and use `daily_forecast` plus a deterministic formatter for weather.
- [x] For out-of-scope messages, return a localized deterministic scope response without calling the constraint parser.
- [x] When the LLM is unavailable, route obvious weather and out-of-scope messages without replaying planner output; return an explicit assistant-unavailable response for travel Q&A that has no deterministic local answer.
- [x] Replace the route's inline parser logic with `route_chat_message`, inject the database session, and return the unified `ChatReply` shape.

### Task 5: Preserve chat context and planner state in the UI

**Files:**
- Modify: `apps/web/src/pages/ChatPage.tsx`
- Modify: `apps/web/src/api/client.ts`
- Modify: `apps/web/src/types/index.ts`

**Interfaces:**
- `sendChatMessage({message, language, prior_user_messages, trip_context, conversation_id})` sends the latest input separately from prior user turns.
- `ChatPage` appends all replies to the conversation feed, but updates `constraints` and adds a constraint snapshot only when `result.intent === "planning"`.
- The request context sends selected destination name/coordinates when available, selected date as local `YYYY-MM-DD`, UI language, active-planner flag, and current structured constraints. Prior parser context excludes travel Q&A/out-of-scope turns.

- [x] Replace the concatenated transcript request in `submitMessage` with `message: text`, prior planning turns, current structured constraints, selected destination context/date, UI language, and `conversation_id`.
- [x] Branch message rendering on `intent`; show forecast source/date/time in the weather response and do not fabricate planner snapshots for non-planning replies.
- [x] Only update `constraints` and attach `snapshot` for planner replies; preserve existing constraints and HUD for travel-information/out-of-scope replies.
- [x] Keep conversation reset behavior and maximum message-size handling aligned with the new structured request.

### Task 6: Document the chat prompt and response flow

**Files:**
- Modify: `docs/ai-prompt-catalog.md`

- [x] Document `CHAT_INTENT_ROUTER` and `TRAVEL_ASSISTANT`, catalog version `3.1.0`, routing behavior, local data grounding, and the Open-Meteo forecast source.
- [x] Document that planner replies alone carry structured constraints and that chat history remains browser-supplied rather than persisted.

### Task 7: Ask for explicit route-critical inputs

**Files:**
- Modify: `apps/api/app/schemas/ai.py`
- Modify: `apps/api/app/prompts/v3_1_0/CONVERSATION_PARSER.md`
- Modify: `apps/api/app/services/offline_chat_fallback.py`
- Modify: `apps/web/src/types/index.ts`
- Modify: `apps/web/src/pages/ChatPage.tsx`

- [x] Add `travel_mode_confirmed` to structured constraints. Keep parser completeness for the four existing planner fields, but make route readiness require an explicit mode.
- [x] Make the trip date initially unset, extract it from chat when provided, and otherwise require the traveler to choose it. Keep origin and return point as catalog selections.
- [x] After a planning reply, append a localized clarification for missing route inputs (date, origin, return point, or stated travel mode), preserving any parser clarification for group/time/budget.
- [x] Keep preview disabled until the constraints are complete, every route input is confirmed, pinned places resolve, and routing supports the selected mode.
- [x] Mark mode confirmation only when explicit language is found; the technical default must not count.

### Task 8: Add read-only itinerary preview and guarded save

**Files:**
- Modify: `apps/api/app/services/planner_service.py`
- Modify: `apps/api/app/schemas/planner.py`
- Modify: `apps/api/app/api/routes/planner.py`
- Modify: `apps/web/src/types/index.ts`
- Modify: `apps/web/src/api/client.ts`

- [x] Separate planner computation from its persistence block so preview returns the solver result without adding itinerary, stop, version, or decision-log rows.
- [x] Add a dedicated preview response with preview identifier, route/stop/estimate fields, and a short-lived HMAC token; never expose a fake itinerary ID.
- [x] Bind the token to normalized PlanRequest, authenticated owner, ordered experience/slot/start/end/cost, endpoints, transport mode, and displayed route/ETA metadata.
- [x] Recompute once on confirmation. If the signed request or computed result changed or expired, return 409 with a replacement preview and do not persist; if it matches, persist that exact computed result.
- [x] Store the accepted route/ETA snapshot in the existing itinerary `constraints` JSON so the saved view initially matches the preview without a migration.
- [x] Preserve `/itineraries/plan` direct creation behavior for other callers.

### Task 9: Show and confirm the preview beside chat

**Files:**
- Modify: `apps/web/src/pages/ChatPage.tsx`
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/src/types/index.ts`
- Modify: `apps/web/src/api/client.ts`
- Reuse: `apps/web/src/components/map/MapAdapter.tsx`

- [x] Add a preview state and a **Preview route** action. Render numbered origin/stops/return point on `MapAdapter` plus the same stops in a time-ordered list in an adjacent column.
- [x] Draw route geometry only when returned by the route provider; do not synthesize street geometry.
- [x] Add a separate **Save itinerary** confirmation action after preview.
- [x] On stale-confirmation response, replace preview data, keep it visible, and ask the traveler to review and confirm again. An expired/invalid token requires a fresh preview.
- [x] Invalidate the preview when date, endpoints, constraints, transport, or pinned places change. Keep the chat, map, and trip HUD usable on mobile through tabs.

### Task 10: Copy TravilityV2 as an isolated reference snapshot

**Source:** `/Users/chithanhdaica/Documents/TravilityV2`
**Destination:** `references/TravilityV2/`

- [x] Copy tracked and untracked source files, documentation, data, and project configuration, preserving the source working tree.
- [x] Exclude `.git`, `.env` and secret-bearing environment files, `node_modules`, virtual environments, build output, caches, `.playwright-mcp`, `.remember`, `.superpowers`, and `.DS_Store`.
- [x] Add `references/TravilityV2/LOCAL_REFERENCE.md` with source, snapshot date, content boundaries, and note that this is an isolated design/code reference rather than an application merge. Preserve TravilityV2's original `README.md` unchanged.

## Plan Self-Review

- **Spec coverage:** Planning continuity, the three route types, weather source/location/date behavior, unavailable data handling, offline behavior, localized out-of-scope refusal, state preservation, prompt versioning, explicit route clarification, no-write preview, guarded save, map/list display, and reference snapshot copy map to Tasks 1–10.
- **Step scan:** Each step names one contract, prompt, service, route, UI, or documentation change and its exact file.
- **Type consistency:** `ChatIntentDecision` uses `ChatRoute`; `ChatMessageRequest` mirrors `ChatMessage`; `ChatReply` is shared between API schema and TypeScript; `daily_forecast` returns the weather object carried by `ChatReply`.
- **Review focus:** The listed failure conditions map to Tasks 3–5; no test files or test commands are included because testing was not requested.
- **Proportion:** Ten tasks cover prompt/schema, weather retrieval, API routing, clarification, preview/confirmation, UI integration, documentation, and the explicitly requested project snapshot without adding chat persistence or a new weather provider.
