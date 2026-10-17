# Collaborative Itinerary Editing Design

## Intent

Let a trip owner invite other travelers to contribute itinerary edits in real time while keeping the owner in control of every saved change. This makes planning a group trip collaborative without allowing an invitee to silently replace the itinerary.

## Goals

- The owner can create, rotate, and revoke a collaboration invite link for an itinerary they own.
- The invite link grants access to view the current itinerary and its pending proposals. Viewing through this link does not require an account; submitting a proposal requires a signed-in traveler account.
- An invited traveler can propose adding, removing, or reordering stops. A proposal is a complete ordered stop list, with each stop identified by its experience and time slot.
- Proposals are persisted and visible to the owner and invitees. Only the itinerary owner can approve or reject them.
- Approval rechecks the proposal against the itinerary's current version, trip constraints, stop locks, slot capacity/status, budget, route timing, and six-stop planner limit. A successful approval atomically updates the itinerary, creates its next version, and broadcasts the new itinerary and proposal status to connected participants.
- Rejected or stale proposals remain visible with their final status. A stale proposal cannot be applied; the collaborator must submit a new proposal against the latest itinerary.
- WebSocket participants see presence and live proposal, review, and itinerary-update events. Reconnecting clients load the current itinerary and proposal list from HTTP.
- Existing public share links remain view-only and keep their current behavior.

## Non-goals

- Editing trip date, time window, group size, budget, travel mode, origin, or destination.
- Editing booked stops. A stop tied to an active booking cannot be removed through a proposal.
- Replacing the existing planner or replan-advice flow.
- Requiring an account to view an invitation link.
- Cross-process WebSocket fan-out. The current Compose deployment runs one API process; a shared broker can be added if the API is scaled later.

## Access and approval rules

- The owner must be signed in as a traveler to create or revoke the invite link, and as the same account to approve or reject proposals.
- The invite token is separate from the existing read-only share token. Store only a hash of the collaboration token; creating a new invite rotates the old one. Revoking or rotating an invite closes its connected collaboration sockets.
- An authenticated traveler with the invite link may submit proposals. Other account roles may view the itinerary through the invite link but cannot submit proposals or review them.
- The WebSocket validates the browser Origin on handshake and the invite token in its first frame before registering the socket in a room. The token stays out of the handshake URL, which Uvicorn may include in protocol logs. A signed-out visitor may connect read-only; an authenticated traveler may submit proposals; only the owner may send review commands. All itinerary writes happen on the server, inside a database transaction.

## Editing and validation

The collaborator UI starts from the current ordered stop list. Invitees can remove a stop, move a stop earlier or later, or add an experience with one of its available slots. The submitted proposal contains the resulting ordered list of `{experience_id, slot_id}` pairs and the `base_version` it was created from.

On approval, the server rejects a stale `base_version`; requires all locked stops to remain in their current relative order; rejects duplicate experiences, unavailable or cancelled slots, insufficient reported capacity, an over-budget plan, an invalid route sequence, or more than six stops; and preserves existing stop IDs where the experience and slot are unchanged. Unknown slot capacity follows the planner's existing tentative-feasibility policy. The approval transaction updates stop order, costs, itinerary version/status, version snapshot, and proposal review fields together.

## User experience

- The owner sees an invite-link control and a pending-proposals review panel on the itinerary page.
- Opening an invite link shows the live itinerary and proposal status. Signed-out visitors receive live updates in read-only mode and are prompted to sign in before submitting a change.
- The collaborative editor exposes add, remove, and move controls. The review panel shows the proposer, the affected stop list, and approve/reject actions.
- On successful approval, all connected clients replace their itinerary snapshot with the server's latest state. If an existing owner replan operation changes the itinerary version, connected clients also receive the refreshed state.

## Implementation calls

- Use FastAPI's WebSocket support and an in-process room manager, matching the current single-process API deployment.
- Keep the invite token out of the WebSocket URL; send it in an authentication frame and acknowledge only after room registration.
- Bound unauthenticated socket use per client IP and per process, expire stalled handshakes, and cap inbound WebSocket frame sizes.
- Persist invitations on `itineraries` and proposals in a dedicated table; use the existing `Itinerary.current_version` and `ItineraryVersion` history.
- Use HTTP for initial collaboration state and invite-link management. Use WebSocket commands for proposal submission and owner review, and WebSocket events for presence and updates.
- Add the collaboration page as a distinct route so the current read-only shared-itinerary page remains unchanged.

## Review focus

- A revoked or rotated invite must no longer read, submit, review, or keep an active socket.
- A non-owner must never approve/reject, even if they know a proposal ID.
- Two proposals based on the same version must not both overwrite each other.
- An invalid, unavailable, over-budget, over-capacity, locked-stop, or unrouteable proposal must leave itinerary and versions unchanged.
- A stop with an active booking must remain attached to the itinerary.
