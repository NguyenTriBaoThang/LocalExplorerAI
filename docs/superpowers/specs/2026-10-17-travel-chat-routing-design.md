# Travel Chat Routing Design

## Intent

Make the Local Explorer chat respond to the latest user message according to its purpose. Today, a follow-up such as “ngày mai có mưa không” is parsed as another itinerary-constraints update. Since the earlier trip details remain in the transcript, the API extracts them again and returns the same generic confirmation. Travelers need to ask trip-related questions in the planning chat without having planner state overwritten, and receive a clear boundary when a question has nothing to do with travel.

## Goals

- Route each latest message to itinerary planning/update, travel information, or out-of-scope handling.
- Keep itinerary planning conversational: prior planning turns remain available to recover constraints, while the newest message determines which flow runs; travel-information and out-of-scope turns stay out of parser history.
- Answer travel questions about weather, places, activities, opening hours, food, and getting around.
- Answer weather questions with a real forecast from Open-Meteo. Use an explicitly mentioned location first, then the selected trip destination; if neither exists, ask for a location.
- Use the current trip date when a weather question has no date. An explicit date or relative date in the latest message takes precedence. Resolve relative dates in `Asia/Ho_Chi_Minh`.
- Include the forecast location, forecast date, retrieval/update time, and Open-Meteo attribution in a weather answer. If a forecast cannot be retrieved or does not cover the requested date, say so and do not guess.
- Refuse unrelated questions politely, in the user's language, and keep the existing itinerary constraints intact.
- Preserve existing planner state and the right-side constraint summary for travel questions and out-of-scope replies. Only planning/update replies may replace the parsed constraints.
- When planning details that change route feasibility are missing, ask the traveler for them instead of silently choosing a route. These include date, both route endpoints, and a stated travel mode; the existing required constraint fields (group size, start time, return deadline, and total budget) remain required. Interests may stay balanced when unspecified.
- Show a read-only itinerary preview before saving: a map with the origin, ordered stops, return point, and route geometry when available, plus a time-ordered stop list. Saving is a separate explicit action.
- Keep the preview and confirmation in the existing chat page, adapting the TravilityV2 chat/map/timeline layout to LocalExplorerAI's React and Leaflet components.
- Copy the TravilityV2 working tree into `references/TravilityV2/` as an isolated, inspectable reference snapshot, including tracked and untracked source changes, while excluding its Git metadata, secrets, installed dependencies, build output, caches, browser artifacts, and personal agent memory.
- Keep answers useful when the LLM is unavailable: weather still uses the forecast service; obvious out-of-scope messages receive a fixed refusal; travel Q&A that needs the LLM reports that the assistant is unavailable rather than returning stale planner text.

## Non-goals

- Build a general-purpose assistant for non-travel topics.
- Create or persist server-side chat histories or add a conversation database.
- Change itinerary generation, routing, booking, or weather-advisory behavior for existing itineraries.
- Replace or merge the TravilityV2 application into LocalExplorerAI; only its source snapshot and relevant interaction patterns are brought over.
- Treat model knowledge as proof of live weather, opening hours, prices, transit status, or availability.
- Add a new weather provider or require a paid API key; use the existing Open-Meteo configuration.

## User-visible behavior

### Itinerary planning and updates

Continue extracting group size, date/time window, budget, transport, interests, and locked places from the user conversation. A planner update may use prior planning turns so a short follow-up can complete or correct trip details. The latest message must be routed as a planning update before this extraction occurs. The existing deterministic offline parser remains available for this flow.

The assistant must not imply that a route is ready while required route inputs are missing. The planner asks for missing group size, time window, or total budget using the parser's clarification. It extracts a stated trip date into constraints (or uses the selected date context); the chat page adds a concise follow-up for any still-missing date, origin, return point, or explicitly chosen travel mode, pointing the traveler to the relevant control. No preference for activity type is required; balanced interests remain the existing neutral default. The selected date starts empty so the assistant never plans against a silently assumed tomorrow.

### Preview and save

After the chat constraints and route inputs are complete, the traveler chooses **Preview route**. A new read-only planner endpoint runs the same solver and returns the proposed stops and route metadata without creating itinerary, stop, version, or decision-log rows. The chat page displays a map with numbered ordered stops and a matching time-ordered list beside the chat. Provider route geometry is drawn when present; the preview does not fabricate road paths when geometry is unavailable.

The traveler then chooses **Save itinerary**. The preview response includes a short-lived HMAC-signed token bound to the normalized `PlanRequest`, traveler identity, ordered stop/slot/start/end/cost signature, endpoint and transport values, and returned route/ETA metadata. Confirmation verifies the token and recomputes once; it compares the new result with the signed preview and persists that same computed result only when the signature matches. If it changed or the token expired, the API returns a fresh preview and the UI replaces the old one and asks for review again. Changing date, endpoints, mode, constraints, or pinned POIs invalidates the current preview. Route geometry/ETA are saved into the existing itinerary constraints JSON so the saved itinerary initially shows the route the traveler approved. The existing direct planner endpoint remains available for existing non-chat callers.

### Travel information

Answer travel-related questions in Vietnamese or English, following the language of the current conversation. Use the selected destination/date and relevant trip details as context. Use the POI/experience catalog for catalog facts such as place descriptions and any stored opening-hours or ticket fields. Do not invent missing catalog facts or current operational information.

Weather questions are a grounded tool-assisted answer. Resolve the location from the latest explicit place mention, then from the selected destination in the chat page. If no location is available, ask for one before fetching. Resolve a date from the latest message first, otherwise use the selected trip date. Fetch daily precipitation probability and precipitation amount for that local date from Open-Meteo. The response names the location and date, states the retrieval time and source, and describes probability as a forecast rather than a guarantee. If the provider fails or the requested date is outside its forecast range, return a clear unavailable message without generating a weather claim.

Travel Q&A must not modify planner constraints. If the LLM is unavailable and a question cannot be answered from a deterministic local source such as the weather service or catalog, state that the travel assistant is unavailable; do not classify the question as out of scope and do not repeat the previous planner reply.

### Out of scope

For messages unrelated to trip planning or travel, return a short, courteous response explaining that this chatbot helps with itineraries and travel information, then suggest a relevant travel question. Do not run itinerary extraction, replace planner state, or reuse the preceding assistant response.

## Request and response context

- The browser sends the latest user message separately from prior user turns/context, along with the UI language and a boolean indicating an active planning flow. The latest message determines intent; the boolean lets the router recognize short replies to pending planning questions. Only prior planning turns are supplied as context for itinerary updates, preventing dates from weather questions from becoming trip dates.
- Send the selected destination's name and coordinates, selected trip date, and last accepted structured planner state as optional context. The server validates and uses only bounded fields needed for routing, forecast lookup, or parser state/date fallback.
- Keep `conversation_id` as a client correlation value. This change does not add server persistence.
- Prior user turns used by the planner parser include only turns previously routed as planning. The API response identifies its route (`planning`, `travel_information`, or `out_of_scope`). Planner constraints are present only when the route is `planning`; weather answers may include structured source metadata. The UI only updates constraint state and renders the constraint snapshot for planner responses.
- The constraint schema records the parsed trip date and whether the travel mode was explicitly stated. The latest accepted constraint object helps merge short answers with earlier values; a technical mode default may be displayed but cannot satisfy route readiness.
- Preview responses use a dedicated schema with a `preview_id` and signed confirmation token, without a persisted itinerary identifier. Confirmation submits the original planning request and token; invalid/stale/expired previews return 409 with a replacement preview or a request to preview again without saving.
- The frontend owns the current date/endpoint selections. For planner turns it composes the route clarification from missing UI values, while the parser's own clarification continues to cover group/time/budget fields.
- Preserve the current fallback disclosure fields and status behavior for planning. Non-planner responses must not masquerade as constraint-parser output.

## Constraints

- The existing chat page already holds the selected destination POI, its coordinates, and the selected trip date. The current request does not send those fields to the API.
- The current planner computes and persists an itinerary in one `plan()` call; preview support must split the same solve result from the persistence block and preserve the direct create flow.
- `APP_SIGNING_SECRET` is available for signed previews in configured environments; development can use a process-local secret, making previews expire when the API restarts.
- TravilityV2 currently has dirty tracked files, valuable untracked WIP, secrets, and large generated/runtime directories. The reference copy must preserve its source working changes without copying secrets or machine-generated/install state.
- `CONVERSATION_PARSER` returns only `StructuredConstraints`; the API currently uses a fixed confirmation reply when all required fields are present.
- Prompt files under the active version are immutable; behavior changes require a new prompt version directory and manifest update.
- The existing Open-Meteo service fetched current conditions and AQI before this change; the chat flow adds a separate daily forecast lookup. The current itinerary weather-advisory endpoint remains admin-only and is not suitable as a traveler chat endpoint.
- `POI` includes coordinates, curated `opening_hours`, and `ticket_info`; experience and slot data are already stored locally.
- The API does not persist chat history. The browser currently resends accumulated user turns.
- Do not change or overwrite existing untracked `.DS_Store` and `.playwright-mcp/` files.

## Implementation calls

- Add a typed intent-routing result and a chat response shape that supports planner, travel-information, and out-of-scope replies without requiring every response to contain constraints.
- Version any new or changed prompt through the prompt catalog's existing manifest workflow; do not edit the active prompt version in place.
- Route from the latest message; pass prior planning turns separately to planner parsing and pass only relevant bounded context to travel Q&A.
- Keep weather retrieval in a dedicated Open-Meteo service function, extending the existing adapter with a daily forecast lookup and a short cache. Use `Asia/Ho_Chi_Minh`, strict coordinate/date validation, bounded HTTP timeouts, and source metadata already used by the current adapter.
- Use explicit place/date in the latest message over UI context. Use selected destination/date only as defaults; ask rather than assuming Ho Chi Minh City when location is missing.
- Ground place facts in local catalog records and reserve live/volatile claims for a source-backed lookup. If no verified fact exists, say it is unavailable or ask a follow-up.
- Keep responses localized and concise. The out-of-scope refusal is deterministic and must work without an LLM.
- Preview generation is read-only. Confirmation persists only the exact plan signature reviewed by the traveler; if it no longer matches, return a replacement preview and require a second confirmation.
- A preview token is HMAC-signed, expires after a short interval, and binds normalized request, owner, stop/slot/time/cost order, endpoints, mode, and displayed route/ETA data. Confirmation compares and persists the same computed solve result.
- Save the displayed route/ETA snapshot in the existing itinerary constraints JSON (no migration) so the first saved view stays consistent with the preview.
- Travel Q&A catalog context is assembled from matching POI and experience records. Stored hours/prices are labeled as catalog data, not proof of current operations.
- Keep the TravilityV2 snapshot separate from application code and document its source path, copy date, and excluded runtime/artifact categories in a local reference note that preserves the source project's own README.
- Do not add database tables, migrations, a new provider, or unrelated planner/UI redesign.

## Review focus

- A weather follow-up after complete itinerary constraints returns a forecast or a location clarification, not the generic planner confirmation.
- A weather question with no explicit or selected destination asks for a location; it never silently assumes a city.
- Forecast output reports the requested local date, location, retrieval time, and source; provider errors and unsupported dates produce no invented forecast.
- A non-travel question receives the boundary response and leaves existing constraints and the HUD unchanged.
- A travel-information response also leaves existing constraints and the HUD unchanged.
- A planning follow-up can still reuse previous user-provided constraints and updates the HUD as before.
- If route-critical data is missing, the assistant asks for it and the preview action stays disabled; a default travel mode/date cannot make the route ready.
- Previewing an itinerary writes no itinerary, stop, version, or decision-log rows.
- The map and ordered list agree on stop order and coordinates, and the preview stays visible beside the chat.
- Saving a matching preview creates an itinerary; a changed route/slot/cost returns an updated preview and creates nothing until reviewed again.
- TravilityV2's source modifications and untracked source files are in the reference copy, while `.git`, `.env` secrets, installed dependencies, generated output, caches, browser artifacts, and personal memory are excluded.
- With the LLM unavailable, offline planner extraction still works; weather and out-of-scope handling remain distinct; other travel Q&A is not mislabeled as out of scope.
- The existing admin itinerary weather-advisory flow keeps its current access and behavior.
