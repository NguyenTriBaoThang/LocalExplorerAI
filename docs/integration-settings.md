# Admin-managed integrations and secrets

Admin users can open `/admin` → **Tích hợp & API keys** to configure the providers that are already wired into the server:

- Payments: choose MoMo or VNPay and enter the corresponding merchant settings.
- Routing/geocoding: choose Goong (or the existing development mock for routing) and set the Goong key.
- Chat AI: choose Gemini or an OpenAI-compatible endpoint and provide its key, base URL, and model. All structured prompt workflows use this selected provider; chat keeps its local fallback if it is unavailable.
- Google OAuth: set client ID, client secret, and the exact registered callback URI.

The API accepts only the fields in its integration allowlist. It never returns secret values: secret inputs load blank, a configured indicator is shown, and leaving one blank preserves the current value. Removing an admin override reverts to the deployment environment value if one exists. Changes are recorded in the admin audit log by service and key name only; values are not placed in audit details or logs.

## Encryption key prerequisite

Generate one Fernet master key and store it in the API's secret environment (not in PostgreSQL or source control):

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set it as `INTEGRATION_SECRETS_KEY` in `.env`/the deployment secret manager, restart the API, and preserve the same value across restarts and deployments. Production Compose requires it. Losing or changing it makes admin-stored values unreadable; take a protected backup of this key separately from the database. The application does not create a default key or silently store secrets as plaintext. Environment-variable configuration can still be used without the admin database override feature.

Apply the schema migration before deploying the code:

```powershell
cd apps/api
alembic upgrade head
```

This applies `0009_integration_secrets`, which stores authenticated-encryption ciphertext, service/key metadata, updater identity, and timestamps. Only the API process decrypts values for calls to the configured provider.

## Service setup notes

- MoMo: obtain credentials through MoMo merchant onboarding; choose `sandbox` for testing, use the official test API URL, and set public HTTPS Return/IPN endpoints ending in `/api/payments/momo/return` and `/api/payments/momo/ipn`. `GET /api/payments/status` reports readiness. Only a signed IPN can confirm payment; the browser redirect cannot. Refund calls are not implemented.
- VNPay: use merchant-issued credentials and public HTTPS Return/IPN endpoints; production requires the merchant's live endpoint. Refund calls remain disabled.
- Goong: the stored key is used by Directions, geocoding, route capabilities, planning, and replanning. Goong calls remain server-side; the browser never receives the key.
- Gemini: the adapter uses Google's OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`) with the Gemini API key and selected model. Gemini's official guide documents that compatibility path: [Google Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).
- Google OAuth: register the exact configured URI (normally `https://<api-host>/api/auth/google/callback`) in the Google OAuth client. The configured callback path is validated by the API.

Use sandbox/test credentials first. A green readiness flag only means local configuration passes validation; it does not prove the merchant account, callback reachability, billing, quota, or production onboarding is complete. See [payment workflow and limits](bookings-and-payments.md).
