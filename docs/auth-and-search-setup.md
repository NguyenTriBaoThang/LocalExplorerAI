# Authentication, roles, and local E5 setup

## Accounts and permissions

The API stores password hashes, issues an HTTP-only session cookie, and assigns one of three roles: `traveler`, `provider`, or `admin`. Public registration always creates a traveler. An admin can create provider profiles/accounts, change roles, deactivate accounts, review POIs/experiences/evidence, inspect likely duplicate POIs, merge a confirmed duplicate, and review audit history.

In development, `scripts.seed_db` creates the configured demo admin and traveler only when their password variables are set and the account does not already exist. The local `.env` is ignored by Git; keep account passwords and all signing keys there, not in source control. Every environment needs the RS256 signing keys (`python -m scripts.generate_auth_keys`); production also defaults `ADMIN_MFA_REQUIRED` on. Google sign-in also requires an OAuth client ID and secret from the application's Google Cloud project, with the callback URL registered exactly as `GOOGLE_REDIRECT_URI`.

## Google sign-in

Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` in the root `.env`. For local development, the callback is `http://localhost:8000/api/auth/google/callback`. For deployment, use the externally reachable HTTPS API URL, e.g. `https://api.example.com/api/auth/google/callback`, and register that exact value under Google Cloud Console → OAuth client → Authorized redirect URIs. `WEB_APP_URL` must be the public frontend origin. `GET /api/auth/google/status` shows whether the settings are usable and the exact callback URL without exposing credentials; the login page also shows why Google sign-in is unavailable. Production rejects non-HTTPS callbacks. The web app starts authorization at `/api/auth/google/start`; the API uses authorization-code flow with PKCE and accepts only Google profiles with a verified email.

## OpenAI-compatible chat and fallback

To use a hosted LLM, set `OPENAI_API_KEY`; optionally change `OPENAI_BASE_URL` (the API root, not the `/chat/completions` path), `OPENAI_MODEL`, and `OPENAI_TIMEOUT_SECONDS`. The selected service must support the OpenAI Chat Completions JSON-object response format. Do not put keys in frontend variables or commit `.env`.

`LLM_FALLBACK_ENABLED=true` is the default. If the key is missing, the LLM times out/errors, or its response fails schema validation, `POST /api/chat/message` uses a conservative local rule parser and returns `status: "fallback"`, `assistant_mode: "local_fallback"`, a reason code, and fallback version. It only fills values found in recognizable text patterns; unknown required values remain missing and are asked as clarification. Since the fallback is not an LLM, its intent weighting is neutral when it cannot recognize intent, and it labels the default motorcycle mode when no mode was stated. Verify those values before creating a trip. `GET /api/chat/status` reports which mode is configured. Other prompt-backed AI routes still fail closed when LLM is missing or unavailable; they do not invent output. Set `LLM_FALLBACK_ENABLED=false` to restore fail-closed behavior for chat too.

## E5 semantic search

E5 inference is local-only: catalog/query text is not sent to an external inference endpoint. The optional runtime is pinned in `apps/api/requirements-e5.txt` for the repository's Python 3.12 API image. Install it from `apps/api` with `python -m pip install -r requirements-e5.txt`, then download the Hugging Face `intfloat/multilingual-e5-base` snapshot with `python scripts/download_e5_model.py`. The downloader resolves `main` to an immutable commit SHA, prints that SHA, and downloads the safetensors checkpoint and tokenizer files (not the legacy duplicate `.bin` weights) into the ignored `models/e5` directory. The model checkpoint is about 1.1 GB, so ensure there is sufficient disk space and network access.

For Docker Compose, set `INSTALL_E5=true` in `.env`, run `docker compose build api`, then download the model to `models/e5` using the script above. Compose mounts `./models` read-only at `/models` and sets `E5_MODEL_PATH=/models/e5`. Keep weights out of Git. Until both optional dependencies and model files are present, semantic search returns explicit `503`; keyword search remains available.

The traveler UI's distance radius is currently centered on the downtown HCMC reference point. Planner origin/destination choices are selected from catalog POIs; arbitrary address geocoding is not part of this implementation.
