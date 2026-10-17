# Collaborative Itinerary Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add authenticated, owner-approved itinerary edit proposals with live WebSocket presence and updates.

**Architecture:** Store one hashed collaboration invite token per itinerary and durable stop-list proposals in the API database. A collaboration service validates and atomically applies owner-approved proposals against the current itinerary version. FastAPI WebSockets carry presence, proposal, review, and itinerary-update events; React adds an owner review panel and an invitee editor page.

**Tech Stack:** FastAPI WebSocket, SQLAlchemy/Alembic, React 18, TypeScript, existing planner and catalog services, nginx.

**Spec:** `docs/superpowers/specs/2026-10-17-collaborative-itinerary-design.md`

## Global Constraints

- The read-only public share token and its existing route remain unchanged.
- A valid collaboration link permits live read-only viewing; submitting proposals requires a signed-in traveler; only the itinerary owner can review them.
- The only proposed edits are adding, removing, or reordering stops. Trip dates, group size, budget, travel mode, origin, and destination stay fixed.
- Accepted edits must satisfy the planner's existing slot-capacity policy, route timing, budget, locked-stop rules, booking protection, and six-stop limit.
- The current deployment runs one API process, so the WebSocket room manager is process-local.
- Preserve unrelated existing workspace changes. Do not add or run automated tests in this implementation.

## Review Focus

- A rotated or revoked invite must deny new HTTP and WebSocket access and close its active room.
- Only the itinerary owner can approve or reject a proposal, even when another traveler knows its ID.
- Only one proposal based on a given current version can be applied; subsequent approvals must see the updated version.
- Invalid, unavailable, over-capacity, over-budget, over-limit, or unrouteable proposals must not partially update stops or version history.
- Stops with an active booking and locked stops must remain protected during proposal review.

---

### Task 1: Persist collaboration links and proposals

**Files:**
- Modify: `apps/api/app/models/entities.py`
- Modify: `apps/api/app/api/permissions.py`
- Create: `apps/api/migrations/versions/0019_itinerary_collaboration.py`

**Interfaces:**
- `Itinerary.collaboration_token_hash: str | None` stores the SHA-256 digest of the current invite token.
- `ItineraryEditProposal` stores `id`, `itinerary_id`, `proposer_id`, `base_version`, ordered `proposed_stops`, `status` (`pending|approved|rejected|stale`), `reviewed_by`, `created_at`, and `reviewed_at`.
- `P.ITINERARY_COLLABORATE` is granted to the traveler role.

- [x] **Step 1: Add the SQLAlchemy fields and proposal model**

  Add the nullable unique/indexed invite hash to `Itinerary` and a proposal model with cascading itinerary ownership, proposer/reviewer user references, JSON stop snapshots, status, and timestamps.

- [x] **Step 2: Add the Alembic migration**

  Create revision `0019_itinerary_collaboration` after `0018_web_push_notifications`; add the invite-hash column/index and proposal table, constraints, and indexes. Implement a complete downgrade.

- [x] **Step 3: Register the traveler permission**

  Define `P.ITINERARY_COLLABORATE` and include it in the traveler default grant list.

- [x] **Step 4: Check Python syntax**

  Run: `python -m compileall -q apps/api/app`
  Expected: exit code 0.

### Task 2: Implement proposal validation and atomic review

**Files:**
- Create: `apps/api/app/services/itinerary_collaboration_service.py`
- Modify: `apps/api/app/models/entities.py` only if a relationship is needed by the service.

**Interfaces:**
- `create_invite(db: Session, itinerary_id: str, owner: User) -> str` rotates and persists a token digest, returning the raw token once.
- `revoke_invite(db: Session, itinerary_id: str, owner: User) -> None` clears the digest after owner validation.
- `load_invite(db: Session, token: str) -> tuple[Itinerary, dict]` validates a raw token and returns the current itinerary snapshot.
- `list_proposals(db: Session, itinerary_id: str) -> list[ItineraryEditProposal]` returns proposals ordered newest first for the invite view and owner review panel.
- `submit_proposal(db: Session, itinerary_id: str, proposer: User, base_version: int, proposed_stops: list[dict]) -> ItineraryEditProposal` persists a pending ordered stop-list proposal.
- `review_proposal(db: Session, itinerary_id: str, owner: User, proposal_id: str, decision: Literal["approve", "reject"]) -> dict` enforces ownership and atomically records the decision; approval applies the valid stop list, increments the itinerary version, and writes its version snapshot and total travel time.

- [x] **Step 1: Implement owner-bound invite rotation and lookup**

  Generate a high-entropy raw token, persist only its SHA-256 digest, and compare digests when loading an invite. Require an owned itinerary for rotation and revocation.

- [x] **Step 2: Persist and list stop-list proposals**

  Validate the proposal's base version, one-to-six stops, unique experience/slot pairs, existing slot references, and the rule that locked stops remain in their current relative order. Persist the proposer and ordered stop list without changing the itinerary.

- [x] **Step 3: Apply approval as one database transaction**

  Lock the itinerary row, recheck `base_version`, validate slot status/capacity and evidence freshness using the existing availability/catalog services, validate budget using the planner's per-person versus flat-price rule, and validate trip/route timing with `RoutingService`. Prevent removing stops with live booking statuses (`pending_provider`, `awaiting_payment`, `confirmed`, `cancellation_requested`). On a validation failure, leave itinerary/versions untouched and mark the proposal stale where its base or feasibility has expired. On approval, preserve existing stop IDs for unchanged experience/slot pairs, update/delete/add stops and order safely around the unique order constraint, recalculate route travel time, update cost/status/version, and insert an `ItineraryVersion` snapshot before commit.

- [x] **Step 4: Record rejection without changing the itinerary**

  Require the owner and a pending proposal, set `rejected`, reviewer, and review time, then commit without modifying itinerary stops or versions.

- [x] **Step 5: Review service consistency**

  Inspect the service for transaction rollback on route/provider/validation errors and ensure no mutation is committed before all candidate stops pass validation.

### Task 3: Add collaboration HTTP and WebSocket transport

**Files:**
- Create: `apps/api/app/services/itinerary_collaboration_hub.py`
- Create: `apps/api/app/api/routes/collaboration.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/api/routes/ai.py`
- Modify: `apps/web/nginx.conf`
- Modify: `apps/web/vite.config.ts`

**Interfaces:**
- HTTP owner routes: `POST /api/itineraries/{id}/collaboration-invite` returns `{ invite_url, invite_active: true }`; `DELETE /api/itineraries/{id}/collaboration-invite` revokes it; `GET /api/itineraries/{id}/collaboration-proposals` returns `{ invite_active, proposals }`.
- HTTP invite route: `GET /api/collaborations/{token}` returns current itinerary, proposal summaries, and whether the signed-in user may submit.
- WebSocket routes: `/api/itineraries/{id}/collaboration/ws` for the owner and tokenless `/api/collaborations/ws` for invite-link participants. Invite participants send the token in the first `authenticate` frame so it is not exposed in handshake-path logs.
- WebSocket commands: invite `authenticate`, `submit_proposal`, and owner-only `review_proposal`; events: `authenticated`, `presence`, `proposal_created`, `proposal_reviewed`, `itinerary_updated`, and structured `error`.
- Pending invite authentication is capped at 32 connections per client IP and 256 per API process, times out after 10 seconds, and accepts at most an 8 KiB auth frame; Uvicorn caps WebSocket frames at 64 KiB.
- Hub operations: `connect(room_id, websocket)`, `disconnect(room_id, websocket)`, `broadcast(room_id, event)`, and `close_room(room_id, code)`.
- `broadcast_from_sync(room_id, event)` schedules a room broadcast from the existing synchronous accepted-replan HTTP handler after its transaction commits.

- [x] **Step 1: Implement the in-process room manager**

  Track active WebSockets by itinerary, broadcast JSON events to a room, remove disconnected sockets, and close all room connections on invite revocation or rotation.

- [x] **Step 2: Add owner invite/proposal HTTP routes**

  Guard link management with `P.ITINERARY_SHARE`, and proposal review-list access with `P.ITINERARY_COLLABORATE`; enforce itinerary ownership on both. Keep invite-link reading public only because the unguessable token is the credential.

- [x] **Step 3: Add invite read and WebSocket routes**

  Validate `Origin` before accept, cap pending handshakes, then validate the invite token from a bounded first frame before registering the socket in a room. Allow signed-out invite viewers to receive read-only events; require `P.ITINERARY_COLLABORATE` for traveler proposal commands and the same permission plus itinerary ownership for owner review commands. Validate each message schema and close unauthorized sessions with an appropriate WebSocket code.

- [x] **Step 4: Broadcast committed changes**

  Broadcast proposal creation/review and committed itinerary snapshots after database commit. Implement `broadcast_from_sync` for the existing synchronous accepted-replan handler so it publishes a refreshed snapshot to collaboration rooms after it commits.

- [x] **Step 5: Register the router and proxy WebSocket upgrades**

  Include the collaboration router in `main.py`; enable nginx WebSocket upgrade headers for production and `ws: true` on the `/api` Vite proxy for local development.

- [x] **Step 6: Check Python and Compose syntax**

  Run: `python -m compileall -q apps/api/app`
  Run: `docker compose config --quiet`
  Expected: both commands exit 0.

### Task 4: Add typed client and WebSocket lifecycle hook

**Files:**
- Modify: `apps/web/src/api/client.ts`
- Create: `apps/web/src/hooks/useItineraryCollaboration.ts`
- Modify: `apps/web/src/types/index.ts`

**Interfaces:**
- Typed helpers create/revoke links, load invite state, and list owner proposals using the existing Axios instance.
- `useItineraryCollaboration({ url, onEvent })` connects with browser cookies, parses typed events, reconnects with bounded backoff, and closes cleanly on unmount or token rotation.
- Proposal input is `{ base_version: number; stops: Array<{ experience_id: string; slot_id: string }> }`.

- [x] **Step 1: Add collaboration API and event types**

  Define proposal, collaboration snapshot, WebSocket event, and command types in `types/index.ts`; add the matching HTTP helpers in `api/client.ts`.

- [x] **Step 2: Implement the socket hook**

  Derive `ws:` or `wss:` from `window.location`, connect to the selected owner or invite endpoint, surface connection state/events, reconnect only while mounted, and close the old socket when the URL changes.

- [x] **Step 3: Run the web TypeScript check**

  Run: `npm run lint --prefix apps/web`
  Expected: exit code 0.

### Task 5: Build owner review controls and invited editor

**Files:**
- Create: `apps/web/src/components/itinerary/CollaborationPanel.tsx`
- Create: `apps/web/src/pages/CollaborativeItineraryPage.tsx`
- Modify: `apps/web/src/pages/ItineraryPage.tsx`
- Modify: `apps/web/src/router.tsx`
- Modify: `apps/web/src/i18n.ts`

**Interfaces:**
- `CollaborationPanel` accepts itinerary ID, owner WebSocket state/events, and callbacks for create/revoke invite and approve/reject.
- `CollaborativeItineraryPage` reads `/collaborate/:token`, shows the current itinerary and proposal list, lets signed-in travelers propose an ordered stop list, and leaves signed-out visitors read-only.
- The owner itinerary page exposes invite management and review controls and replaces its displayed itinerary after `itinerary_updated` events.

- [x] **Step 1: Add owner invite and proposal review panel**

  Show the invite URL after creation, indicate active/revoked status, support rotation/revocation, and render pending proposals with add/remove/order differences and approve/reject controls.

- [x] **Step 2: Add the collaborator page and editor**

  Load the invitation snapshot, show live presence, support stop removal and up/down reordering, search eligible experiences and slots with the existing catalog client, and submit the full ordered list as a proposal. Require sign-in before proposal submission; show anonymous viewers a sign-in prompt that returns to the invitation URL.

- [x] **Step 3: Integrate owner WebSocket updates**

  Add the owner panel to `ItineraryPage`, update itinerary state when an approved change/replan is broadcast, and refresh version history after a committed update.

- [x] **Step 4: Register route and translations**

  Add `/collaborate/:token` without changing `/shared/:token`; provide Vietnamese and English labels for invite state, proposal differences, review actions, connection state, validation failures, and sign-in prompts.

- [x] **Step 5: Run the web TypeScript check**

  Run: `npm run lint --prefix apps/web`
  Expected: exit code 0.

### Task 6: Final implementation review

**Files:**
- Review: all files changed by Tasks 1–5.

- [x] **Step 1: Review the final diff**

  Check authorization boundaries, SQL transaction ordering, invite revocation, WebSocket cleanup, stale-version handling, and that the read-only share path is unchanged.

- [x] **Step 2: Run allowed static verification**

  Run: `python -m compileall -q apps/api/app`
  Run: `npm run lint --prefix apps/web`
  Run: `docker compose config --quiet`
  Expected: all commands exit 0. Automated tests are not added or run.

- [x] **Step 3: Summarize changes and limitations**

  Report the implementation, verification output, and the current single-process room-manager limitation.
