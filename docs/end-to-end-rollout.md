# End-to-end pilot rollout

## Application flow

The customer journey is wired through these application boundaries:

1. A traveler registers or signs in at `/api/auth/register` or `/api/auth/login`.
2. The client geocodes start and return addresses through `/api/geocoding/forward`; the traveler chooses returned coordinates.
3. `POST /api/itineraries/plan` requires both endpoints when routing is requested. The planner checks outbound and return legs, time, budget, locked stops, slot capacity, current evidence, and expiry before it saves an itinerary.
4. `POST /api/bookings` creates a capacity hold only for a verified POI, experience, and provider-confirmed slot.
5. The partner accepts or rejects the hold through `/api/provider/me/bookings/{booking_id}/decision`.
6. For paid reservations, the traveler starts checkout. A verified MoMo or VNPay IPN, not the browser return page, updates the payment and booking state.
7. A partner cancellation writes a `SLOT_CANCELLED` event, updates affected bookings, queues notifications when SMTP is configured, and makes replan advice available at `/api/itineraries/{itinerary_id}/replan-advice`.

The automated API test `test_catalog_requires_current_sources_and_hides_expired_slot` covers source review, provider slot creation, traveler login, mocked Goong request parsing for both route legs, planning, booking hold, and partner acceptance. The mocked Goong response keeps CI independent of private credentials; it does not establish that the staging Goong account is working.

## Data gate

`data/raw/Sai_Gon_Places.xlsx` currently feeds the admin import queue. It is not the live catalog. The current workbook audit reports all 177 rows as not publishable under field-level evidence rules, including address/coordinate confirmation and source evidence. The old seeder is disabled because it inferred missing values and fabricated evidence and slots.

The admin and provider workflows can promote sourced POIs, experiences, and slots after a reviewer checks current evidence. No script may synthesize 10–15 partner experiences or 30–50 provider-confirmed slots. Those inventory targets require source rows from the participating businesses, with confirmed prices, durations, and capacity.

## Staging configuration and checks

Use a separate staging database, persistent `INTEGRATION_SECRETS_KEY`, HTTPS API and web origins, and secrets stored in the staging secret manager or the encrypted admin integration screen. Do not copy production secrets into a browser `.env` file.

| Integration | Required staging setup | Verification boundary |
|---|---|---|
| Goong | REST API key on the API server; public map tile key only if the browser uses Goong tiles | Admin routing test calls Geocoding and Directions. Confirm the selected travel modes against the Goong account. |
| LLM | Gemini or OpenAI-compatible key, base URL, and model | Admin AI test makes a small structured request. Chat reports its configured or local-fallback mode. |
| Google OAuth | Client ID and secret; register the exact `https://<api-host>/api/auth/google/callback` URI in Google Cloud | Configuration status validates the callback. Complete a browser OAuth round trip in staging to verify the Google app and allowed origins. |
| SMTP | Host, port, TLS mode, sender, and credentials in the staging API environment | Confirm the outbox worker is running, send a staging notification, and check delivery in the mailbox and `/api/ops/notifications`. |
| MoMo | Sandbox merchant credentials and public HTTPS return/IPN URLs ending in `/api/payments/momo/return` and `/api/payments/momo/ipn` | Complete a sandbox checkout and verify the signed IPN changes payment/booking state. |
| VNPay | Sandbox TMN code/hash secret and public HTTPS return/IPN URLs ending in `/api/payments/vnpay/return` and `/api/payments/vnpay/ipn` | Complete a sandbox checkout and verify the signed IPN changes payment/booking state. |

AI and Goong checks can contact their configured external services. Payment integration configuration alone is not a payment test; gateway behavior requires a sandbox checkout. Google callback configuration alone is not an OAuth test; finish the user consent/redirect flow in a browser. No live staging credentials or partner confirmations are present in this repository, so those external checks remain deployment tasks.

## Release gates

- CI has separate backend `pytest -q`, frontend lint/build, and Windows frontend-build jobs. Configure repository branch protection to require all three checks before merging.
- The current local verification completed with 106 API tests passing and a Windows production frontend build passing. The frontend build still reports a large JavaScript chunk; split map/3D-heavy routes before treating load performance as production-ready.
- Keep `REAL_DATA_ONLY=true`; keep the bootstrap ranker disabled. Promote a learned ranker only after reviewed, real traveler preference/outcome data passes the documented evaluation gate.
- Before a pilot, record the approved partner inventory, run the role-by-role sandbox flow above, verify cancellation notifications and replan in staging, and confirm recovery/backup procedures for the staging database.
