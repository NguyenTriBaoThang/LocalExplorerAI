# Local Explorer AI Proposal for MLAI Hackathon 2026 — Tasco Track

**Solution name:** Local Explorer AI — A Local-Experience Layer on the Map<br>
**Track:** Building an application layer for a Vietnamese map — Tasco direction<br>
**Demo area:** District 1 pilot area, Ho Chi Minh City<br>
**Version:** 2.0 — updated 15 October 2026<br>
**Competition deliverables:** Working Web Demo and Pitch Deck

## 1. Solution Summary

Local Explorer AI adds a local-tourism data and application layer to a map. Instead of only asking “where is this place?”, users can ask “which experience fits, can be joined within my time window, what route should I take, and where was this information verified?”

Travelers enter their needs in Vietnamese, choose origin/destination, and specify constraints. The system retrieves experiences with relevant data, checks opening times, duration, budget, capacity, required stops, and the return leg, then displays sourced results on the map and in an itinerary. If important information has not been verified, the interface must say so instead of presenting it as fact.

The solution fits the Tasco Track direction because it creates a localized map application layer that could extend into a mobility ecosystem. VMap/T-Maps is the target map platform and must be verified using an SDK/API and access granted by Tasco or the organizers. The repository currently has a map interface and a Goong routing adapter, but there is not enough evidence to claim that VMap/T-Maps has been integrated or accepted. The demo must accurately identify the provider actually in use.

## 2. Problem and Need

General-purpose maps help users locate places and find routes, but a local-experience journey also requires answers to:

- Does this place offer an activity/experience, or is it only a POI to visit?
- Where do its price, duration, and opening hours come from, and when were they confirmed?
- Is there a suitable slot with enough capacity for the group?
- Does the itinerary meet the time, budget, and required-stop constraints, including the return leg?
- If a slot is canceled or data is stale, how will the user be warned and what alternatives are available?

A marker on a map does not mean that a service is operating or has availability. The product separates places, experiences, and slots, and also shows information sources and freshness.

### Target Users

- **Travelers:** domestic visitors, first-time visitors to Ho Chi Minh City, friend groups, or families who want to explore local culture, food, and activities without manually combining multiple apps.
- **Venues/partners:** small businesses, artisans, workshop operators, and experience providers who need to update information, slots, and capacity and confirm requests.
- **Tasco map ecosystem:** a partner could add a local data layer and enrich map context for real journeys. The extent of collaboration and integration must be confirmed; no agreement is assumed to exist.

## 3. Value and Differentiators

1. **POI → Experience → Slot:** distinguishes a physical place from a specific activity and a bookable time slot.
2. **Constraint-aware itineraries:** the planner checks feasibility first; the ranker cannot legitimize an option that violates the return deadline, budget, locked stops, or capacity.
3. **Visible source and freshness:** information has a source, confirmation time, and expiry; unsupported data is marked pending/unknown.
4. **Localization:** Vietnamese queries and activities specific to Ho Chi Minh City.
5. **Role coordination:** travelers plan, venues update slots, and administrators review sources and data.

Local Explorer AI is not positioned as another general-purpose map. It adds an experience layer—with timing, services, and data evidence—to a map platform.

## 4. Product Flows

### Traveler Flow

1. Enter a natural-language request in Vietnamese; the system extracts group size, times, budget, travel mode, intent, and required places.
2. Review and edit the extracted constraints; the LLM does not independently confirm prices or availability.
3. Choose origin, destination, date, travel mode, and required stops.
4. View sourced experiences on the map; open details to see price, duration, hours, slots, confirmation status, and missing data.
5. Ask the planner to build an itinerary; the planner checks routes between stops and the return leg before the deadline.
6. Save/share the itinerary and, when supported by the slot, submit a reservation-hold request.
7. Receive a warning and review alternatives if a slot changes; the traveler decides whether to change the itinerary.

### Partner and Administration Flows

- Partners update slots/capacity or accept/reject requests.
- Administrators review sources, field-level evidence, duplicates, and approval status.
- Status changes and confirmation information are stored for traceability.

### Demo Scenario

Choose a District 1 scenario whose data has been checked by the team; enter a request; lock a stop; create a round-trip itinerary; open details to inspect sources and confirmation times; then simulate a slot cancellation in a sandbox and show replanning options. Any synthetic/mock data or sandbox transaction must be labeled in the interface and in the presentation.

## 5. Demo Scope

### Working Web Demo Priorities

- A small area with a defined pilot boundary and a stated data-snapshot date.
- Place search/discovery on the map and details with provenance.
- Itinerary generation using origin/destination, time window, budget, locked stops, and return time.
- Traveler, partner, and administrator interfaces separated as needed by the scenario.
- One slot update/cancellation flow and an alternative recommendation.
- A labeled sandbox or demo scenario if an external service is not ready.

### Not Promised in the Demo

- Complete coverage of all Ho Chi Minh City places, or a claim that the 177 workbook rows have evidence for every field.
- Calling an ETA real-time traffic if the provider does not guarantee that.
- Production transactions, automatic refunds, or actual service capacity without staging/partner testing.
- Claiming that the ranker learned real customer preferences from weak labels.
- Road-flood prediction from historical data lacking negative observations and suitable road-edge labels.

## 6. Tasco Map Integration

The map is the primary interaction surface for displaying the experience layer, data status, routes, and stops. Adapters allow the map/routing provider to vary by environment without coupling provider-specific logic to the planner.

### Target and Conditions

- The competition's integration target is Tasco VMap/T-Maps, subject to the API/SDK, quota, and terms of use granted.
- Testing must cover map loading, marker/layer rendering, geocoding or search if supported, round-trip routing, quota, and timeouts.
- If access is granted in time, prioritize demonstrating the experience layer on Tasco's platform.
- If access is not granted, use the current map provider in the demo and identify it accurately; present Tasco as the integration target, without implying it is already connected.
- Do not draw a route manually and call it an API route; show the provider and ETA timestamp/age.
- Credits/APIs supplied by the organizers may only be used under program conditions; do not expose API keys in the frontend, pitch screenshots, or repository.

## 7. Data Strategy

The Challenge Brief permits combining team-collected data, lawful open data, geographic and community data, third-party APIs, and representative synthetic/mock data. Local Explorer AI clearly classifies each source and does not mix demo data with the operational catalog.

| Source | Role | Limitations to Disclose |
| --- | --- | --- |
| 177-place team workbook | Initial source for POI reconciliation and classification | Row count does not prove that every field is verified; prices, hours, activities, photos, and slots each need evidence. |
| OpenStreetMap | Candidate locations, names, and geographic tags | Provide attribution and comply with ODbL; it does not verify that a venue is operating, its price, or its availability. |
| Venues/partners | Confirmation of a venue's own experiences, prices, durations, slots/capacity | Record the confirming person/organization, time, revision, and expiry. |
| Map/routing APIs | Maps, geocoding, and ETA under the provider's contract | Record provider, timestamp, errors/cache age; an ETA is not automatically real-time. |
| Photos | Images with a clear source and usage right for each file | Store the source page, author, license, and credit; if unsupported, use a labeled placeholder. |
| Synthetic/mock data under the brief | Demonstrate slot cancellation, over-capacity, or future states | Label as demo/test; separate it from the operational catalog and do not use it as evidence of real quality. |

Each important field needs a source, observation/confirmation time, confirmation scope, revision, and expiry. Prices, hours, capacity, and slots need freshness appropriate to their rate of change. If evidence is missing, mark the value unknown/pending; do not infer that it is verified.

## 8. AI and Spatial Processing

- **Vietnamese NLU:** extracts constraints into structured data that users can review and edit.
- **Planner:** decides feasibility, time, budget, locked stops, capacity, and return leg. The planner is authoritative for itinerary validity.
- **Ranking:** the explainable rule baseline is the default. The existing bootstrap XGBoost artifact uses weak labels and does not have enough evidence to serve as a production preference model. Evaluate ML only on independent/consented labels with leakage-resistant splits.
- **Replanning/XAI:** proposes alternatives from solver-filtered candidates; trade-offs come from API data and are not fabricated.
- **Fallback:** when the LLM or an external service fails, use a form/rule fallback and state its limitations.
- **Flood/GeoAI:** do not make this a core demo claim without time-based observational data and road-edge labels. It is a separate research direction.

## 9. Feasible Architecture

1. **Web client:** chat, map/list, details, planner, and role-based interfaces.
2. **API:** authentication, catalog, staging, planner, ranking, booking, and adapters.
3. **Data layer:** POI, experience, slot, source/evidence, approval status, and history.
4. **Map/routing adapters:** normalize providers by environment and store provenance.
5. **AI components:** parser, rule baseline, explanation, and replanning; validate outputs against schemas and business rules.
6. **Operations:** traceable logs, error/quota controls, backups, and smoke tests.

The POI → Experience → Slot model prevents the system from confusing “a real place” with “a service currently accepting guests in a particular slot.”

## 10. Code Status and Demo Conditions

The repository currently contains a React/TypeScript web app, FastAPI API, role-based interfaces, chat with fallback, a planner, map/routing adapter, staging import, booking/slot flows, and adapters/configuration for some external services. This is a codebase for a demo; it does not prove that external services have been staging-tested.

Before claiming that a feature works with a real service, the team must verify:

- Tasco/VMap/T-Maps API/SDK, access, and terms;
- active routing provider, route status, and ETA freshness;
- OAuth, LLM, email, payment sandbox, and HTTPS callbacks if included in the demo;
- a small checked place set, licensed photos, and slots confirmed by venues;
- database/migrations, role-specific test accounts, logs, and a backup build.

If an integration is not ready, disable it in the live demo or clearly label it sandbox/mock. Do not infer a successful integration from the presence of a key/configuration or a visible interface.

## 11. Proposed Demo Criteria

These are targets for the team to finalize and measure before pitching, not achieved results:

| Metric | Proposed Target | How to Check |
| --- | --- | --- |
| Planner scenarios | 5/5 demo scenarios return the correct status | Record inputs/outputs and include at least one infeasible case. |
| Hard-constraint violations | 0 on the predefined test set | Check hours, budget, locked stops, capacity, and return leg. |
| Data traceability | 100% of fields called “confirmed” in the demo have a corresponding source and timestamp | Compare the interface with evidence; mark all remaining fields unknown/pending. |
| Route transparency | 100% of route screens show the correct provider and do not claim “real-time” without support | Check cache, stale data, timeout behavior, and UI labels. |
| Rehearsal | Complete the main flow using the final build and test accounts | Run on the expected device/network and save an issue checklist. |

Only after the competition should a pilot measure planning time, traveler option-selection rate, provider confirmation rate, data staleness, slot cancellations, and satisfaction. Behavioral data collection requires consent and defined denominators.

## 12. Impact and Expansion

### Expected Impact

- Help travelers discover local activities by time, rather than only viewing map markers.
- Create a structured data channel for small businesses and cultural services.
- Add local context to a Vietnamese map and connect discovery with mobility journeys.
- Establish a provenance-aware update workflow that distinguishes reliable information from stale/uncertain data.

### Operating Hypotheses

After validating demand, the team could test venue-management tools, transparent referral/booking fees, B2B solutions for destinations, or a specialized map data layer. These are business hypotheses, not existing revenue or agreements.

### Expansion

Start with a District 1 pilot. Expand only after field verification, slot updates, and operational support are stable; do not expand merely by adding unchecked POIs.

## 13. Implementation Plan

The Challenge Brief lists registration opening on 24/08, registration closing on 15/09, kick-off on 19/09, and the final on 17/10/2026. This proposal is dated 15/10/2026, so the demo should be frozen during the final two days; the team should confirm its official schedule.

| Date | Work | Deliverable |
| --- | --- | --- |
| 15/10 | Finalize the demo narrative; check real integrations; select a small evidence-backed data set; prepare a labeled fallback. | Demo scope, list of data permitted for presentation, issue checklist. |
| 16/10 | Freeze features; rerun five scenarios, role permissions, round-trip itinerary, and slot states; rehearse the pitch and network fallback. | Demo build, pitch deck, contingency plan. |
| 17/10 | Present the problem → map interaction → value → data/AI → Tasco integration and expansion plan. | Working Web Demo and Pitch Deck required by the competition. |

### Post-Hackathon Roadmap

| Phase | Focus | Decision Gate |
| --- | --- | --- |
| Days 0–30 | Confirm map API usage rights; audit the District 1 catalog; interview travelers/venues; complete the data policy. | Launch a pilot only when a subset has sufficient field-level sources and providers agree. |
| Days 31–60 | Onboard venues; create real experiences/slots; test sandbox booking, notifications, and replanning. | End-to-end tests and stale/error handling meet internal criteria. |
| Days 61–90 | Run a limited pilot; measure usability, freshness, ETA/slots, and conversion. | Report metrics and limitations and decide whether to expand. |

The team must confirm POI, experience, slot, and partner targets against actual capacity; quantity does not replace evidence quality.

## 14. Proposed Team Responsibilities

Fill in names after the team agrees; the roles below do not assume any specific members.

| Role | Responsibility |
| --- | --- |
| Product/pitch lead | Users, problem, demo narrative, mentor coordination, and pitch. |
| Frontend/map | Map, layers, interactions, and source status. |
| Backend/planner | API, feasibility, routing adapter, booking/replanning, and tests. |
| Data/AI | Catalog/provenance, NLU, baseline, evaluation, and AI limitations. |
| Demo/QA | Test accounts, data, rehearsal, and backup build. |

One person may cover multiple roles. The pitch should state who is responsible and must not present unearned experience as an achievement.

## 15. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Risk | Impact | Mitigation |
| No Tasco SDK/API yet | Unable to demonstrate integration with the target map platform | Request sandbox/credits; state the adapter and status; do not simulate the API or branding. |
| Missing evidence for prices, hours, slots, or photos | Recommendations may mislead users | Narrow the demo data set; show missing fields as pending; label mock data. |
| API or Internet failure | Demo interruption | Prepare a permitted, labeled snapshot/video and a clear fallback. |
| Stale ETA/slot data | Invalid itinerary or unserved customer | Use timestamps, TTL, stale warnings, and provider confirmation. |
| Weak labels mistaken for real preferences | Unsupported AI claim | Keep the baseline; do not present weak-label metrics as customer effectiveness. |
| Payment/callback not staging-tested | Transaction risk | Use sandbox only; do not collect real money in the demo. |
| Scope too broad | Unstable demo | Demonstrate only one District 1 journey and one replanning scenario. |

## 16. MLAI Hackathon Scoring Criteria Alignment

| Challenge Brief Criterion | Maximum Points | How Local Explorer AI Addresses It and Evidence to Prepare |
| --- | ---: | --- |
| Problem-solving and impact | 20 | Identify target travelers/venues; demonstrate fewer manual itinerary steps; prepare interviews or state assumptions if no research has been done. |
| Relevance to Vietnam | 15 | Ho Chi Minh City data, language, and experiences; explain attribution, data conditions, and deployment feasibility on local infrastructure. |
| Creativity and differentiation | 20 | Experience/slot layer and deadline-constrained itinerary—not only POI layers; demonstrate the difference. |
| Data and AI innovation | 20 | Provenance/freshness; Vietnamese NLU; planner/ranking; clearly distinguish the baseline from weak-label models. |
| Feasibility and prototype | 15 | Stable Working Web Demo; repeatable main flow; describe Tasco integration according to actual API status. |
| Presentation and UX | 10 | Clear UI; one end-to-end demo scenario; pitch deck clearly answers the problem, product, data, AI, and expansion. |

## 17. Proposed Pitch Deck

1. Problem and users: maps show POIs but do not say which experiences can be joined within a time window.
2. Need: target travelers/venues and research evidence; distinguish research data from assumptions.
3. Solution: Local Explorer AI as an experience/slot layer on a map.
4. Demo: Vietnamese request → origin/destination → feasible itinerary → sourced details → replanning.
5. Data and AI: provenance, licenses, freshness; the planner decides feasibility while AI supports language, ranking, and explanations.
6. Tasco fit: a data layer for a Vietnamese map; actual VMap/T-Maps status and integration roadmap.
7. Feasibility, impact, and measurement: prototype status, demo/pilot KPIs, limitations, and expansion model.
8. Team and asks: responsibilities and the API/mentoring/credits/data requested from the organizers/Tasco.

## 18. Support Requested from Tasco and the Organizers

- Documentation, sandbox, and suitable access for the VMap/T-Maps SDK/API, with guidance on attribution, quota, and demo usage conditions.
- Examples for marker/layer integration, deep links, geocoding, and route APIs if supplied by the program.
- A mentor or connections to local venues to validate the data-update workflow.
- Details of any credits and APIs/data provided by the program, including expiry and terms.

The Challenge Brief also mentions mentors from Tasco/the AI Network, Codex and Goong.io credits, and APIs/data that the organizers may provide during the Hackathon. The team must confirm the specific granted rights before making plans that depend on them.

## 19. Truthful Claims During the Pitch

- A working prototype does not mean production deployment.
- Having an adapter/configuration does not mean an external service has been staging-tested.
- The 177 places are team-collected data; confirmation status must be assessed field by field, especially for prices, hours, slots, capacity, and photos.
- The Challenge Brief permits synthetic/mock data in some cases; if used, it must be labeled and kept separate from real data.
- Weak labels measure agreement with the rules that generated those labels; they do not prove that a ranker understands traveler preferences.
- Say “integrated with Tasco/VMap/T-Maps” only after running and recording actual API/SDK test results.

## Pitch Introduction

“Local Explorer AI turns a map into a place where travelers can not only see locations but also find experiences that fit their schedule and journey. Users describe their needs in Vietnamese, choose an origin and destination, and the system checks hours, budget, slots, and routes before suggesting an itinerary. Each item shows its source and freshness; unconfirmed information is never presented as fact. We want to bring this local-experience layer to Tasco’s Vietnamese map, starting with a small District 1 pilot and expanding when the data, partners, and integrations have been verified.”
