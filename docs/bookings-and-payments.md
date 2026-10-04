# Booking, capacity and payment boundary

## Implemented reservation flow

1. An authenticated traveler requests seats from an owned, persisted itinerary stop.
2. The API accepts only currently open slots whose source evidence for POI, experience, and slot is verified and unexpired. Demo, stale, unknown-capacity, or unauthenticated provider data cannot be booked.
3. PostgreSQL locks the slot row, expires overdue holds, counts active seats, checks capacity, snapshots the price basis and amount, and creates a 15-minute `pending_provider` hold. The provider's reported availability is not mutated by the application.
4. The authenticated provider sees a reservation request and explicitly accepts/rejects it. Acceptance rechecks the live slot evidence and total held seats. A paid reservation moves to `awaiting_payment`; a free one can become `confirmed` after provider acceptance.
5. The hold expires automatically when read or when another booking/provider action touches the slot. Expiry and state transitions are recorded in `booking_events`; important actions also write `audit_logs`.

These holds are real reservations inside this application's database, subject to authenticated provider confirmation. The application does not synchronize inventory with a venue's external POS, phone bookings, or third-party marketplace; providers must keep their reported capacity current there and in this portal.

Use PostgreSQL in production. `SELECT ... FOR UPDATE` serializes hold creation per slot on PostgreSQL; SQLite is for tests and does not provide equivalent row-lock guarantees.

## API

- `POST /api/bookings` — create a temporary seat hold. Body: `{ "itinerary_id": "…", "itinerary_stop_id": "…", "quantity": 2 }`.
- `GET /api/bookings?itinerary_id=…` — current traveler's reservations and history.
- `POST /api/bookings/{id}/cancel` — release an unpaid hold; a paid booking transitions to `cancellation_requested` and does not claim to have refunded money.
- `GET /api/bookings/{id}/history` — visible only to the traveler, owning provider, or admin.
- `GET /api/payments/status` — reports VNPay environment and whether signed checkout is ready; never exposes merchant credentials.
- `POST /api/bookings/{id}/checkout` — creates/reuses a pending VNPay transaction and returns a signed VNPay checkout URL. The API does not handle card data.
- `GET /api/payments/vnpay/return` — validates the VNPay signature for display routing only; it never settles a transaction.
- `GET /api/payments/vnpay/ipn` — verifies the merchant, signature, amount and transaction result; idempotently updates the payment ledger and booking.
- `GET /api/provider/me/bookings` — authenticated provider's requests.
- `POST /api/provider/me/bookings/{id}/decision` — body action `accept` or `reject` with optional note.
- `POST /api/provider/me/bookings/{id}/cancellation-decision` — provider approves/rejects an unpaid cancellation; paid cancellation cannot be completed until an actual refund adapter returns verified success.

The provider portal receives reservation quantity, activity, timeslot, price and status only. It does not receive the traveler's name, phone, or email in this release.

## VNPay payment and refund boundary

VNPay is the selected gateway adapter. Checkout remains fail-closed unless TMN code, Hash Secret, payment URL, and public HTTPS Return/IPN URLs are configured. The default payment URL is VNPay sandbox. Production requires the team's merchant-issued production endpoint/credentials and `VNPAY_ENVIRONMENT=production`; the production setting refuses the sandbox endpoint. A local `localhost` URL cannot receive VNPay's server-to-server IPN; use a public HTTPS deployment or tunnel for sandbox testing.

### Enable VNPay sandbox

1. Obtain sandbox `TMN_CODE` and `HASH_SECRET` from VNPay; keep the secret in the untracked `.env`, never in source control.
2. Expose the API through a public HTTPS deployment/tunnel and set `VNPAY_RETURN_URL=https://<api-host>/api/payments/vnpay/return` and `VNPAY_IPN_URL=https://<api-host>/api/payments/vnpay/ipn`. VNPay needs Internet access to call the IPN endpoint; the two paths are validated by the application.
3. Set `VNPAY_ENVIRONMENT=sandbox`, `VNPAY_TMN_CODE`, and `VNPAY_HASH_SECRET`. `VNPAY_PAYMENT_URL` defaults to VNPay's sandbox checkout URL. Restart the API, then check `GET /api/payments/status`; `checkout_enabled` must be `true` before attempting a payment.
4. Have a provider accept a verified slot booking, then use the traveler UI's “Continue to payment” action. Use only VNPay's sandbox payment data while testing and confirm the booking changes only after the server receives a valid IPN.

For production, use merchant-issued live credentials, the production payment URL given by VNPay, public HTTPS callbacks, and `VNPAY_ENVIRONMENT=production`. Do not infer or copy a live endpoint from the sandbox setup. Test signed callbacks, expiry, duplicate delivery and operational alerts before enabling customer charges.

See VNPay's [PAY integration specification](https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html), [merchant setup guide](https://sandbox.vnpayment.vn/apis/docs/gioi-thieu/), and [FAQ](https://sandbox.vnpayment.vn/apis/docs/faqs/) for current account-specific setup, amount limits and sandbox test details.

The server creates the payment reference and amount from the held booking, signs the VNPay request with HMAC-SHA512, stores a pending transaction, and reuses its checkout URL on repeat requests. The signed IPN is authoritative. The browser Return URL is display-only and the page polls the authenticated bookings API until it sees the server-set `confirmed` state. Captures received after a hold expired/cancelled or after another capture are recorded and moved to manual reconciliation; the booking is not falsely confirmed.

Real checkout is only enabled once credentials and externally reachable callback URLs are supplied. Refund API calls remain disabled; paid cancellations and unexpected/late captures require operator reconciliation/refund outside the application. Do not describe refunds as automated. Test the sandbox flow and verify successful IPN delivery before accepting any production payment.

Migration `0007_booking_payments` creates `bookings`, `payment_transactions` and append-only `booking_events`; Compose already runs `alembic upgrade head` at API startup.
