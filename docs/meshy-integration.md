# Meshy generation for Map3D

Portal: `/admin/meshy` (permission `admin:models_3d`). Configure a NEW Meshy API key in `/admin/integrations`, or use backend-only `MESHY_API_KEY`. Never put it in VITE variables. The key previously shared in chat should be revoked by its owner; this implementation does not install or call it.

## Deploy
1. Back up the database, then from apps/api run `.venv/Scripts/python.exe -m alembic upgrade head` (0020_meshy_jobs).
2. Build apps/portal and apps/web with `npm run build`, restart API. Keep traveler web at port 8080. Local Portal preview uses http://localhost:5174/admin/meshy; traveler web stays at http://localhost:8080. Use the same hostname (localhost) on both so the existing host cookies are shared. The current Vite 8080 proxy only routes /api and /health, not Portal pages; publishing Portal on the public domain needs a separate Portal route/host configuration.
3. Configure Meshy key through the existing encrypted integration settings. API readiness only indicates configuration; no real Meshy account or credits were verified during implementation.
4. Preserve `apps/api/.meshy-assets` across restarts/deployments. On containers set `MESHY_STORAGE_DIR` to a persistent writable volume and mount it. Back up that volume together with the jobs table. Multiple API instances must share this storage. Do not expose it as a static directory.

## Workflow
Choose a POI or enter coordinates/name/height; submit a prompt (max 800 chars) or 1–4 PNG/JPEG/WebP images (max 5 MB each). Images are sent to Meshy as data URIs, not retained locally in jobs. UI explicitly confirms transmission and estimated credit cost.

Pinned model: meshy-6, GLB, target 30,000 faces. Text preview 20 credits; optional explicit refine 10 credits/2K texture. Multi-image with texture 30 credits. Estimates from the linked official pricing page; provider billing controls actual usage. Reserve 120 credits per actor per UTC day by default (`MESHY_DAILY_CREDITS`), two unresolved/running jobs maximum per actor. Failed and uncertain requests conservatively retain reservations for that day. This is an application allowance, not a Meshy billing hard cap.

POST requests use durable local UUID request keys. No automatic retries of billable POSTs, including after a timeout. A crashed submission is marked uncertain; operators reconcile the Meshy dashboard and attach the correct task ID or mark it absent. A refine is a separate job; a parent can create at most one refine job. If that refine fails and must be regenerated, start a new generation. Avoid repeatedly generating just to change placement.

API lifespan worker polls every 15 seconds, resumes persisted jobs after restart, and stops polling at two hours. Resume extends observation without creating another paid job. PostgreSQL row locks serialize worker claims and per-user credit reservations. SQLite is for unit tests, not concurrent production budget enforcement.

Successful GLB is downloaded immediately to private local storage. HTTPS assets.meshy.ai only, no redirects, streaming 50 MB limit, GLB v2 header checks and embedded dependencies only. URL and upstream error bodies never appear in responses or logs. Downloads can be retried without starting a new paid task.

Open private preview `/map-3d?meshyPreview=<id>` using an authenticated admin session. After model loads, adjust the existing map calibration and save. Return to Portal, refresh, and publish. Published models appear in the existing calibration registry and can receive landmark stories/timelines. They carry an AI-generated label. Unpublish immediately removes public registry/file access (previously downloaded copies cannot be recalled).

Only published GLB bytes have a public endpoint. Draft URLs still require admin auth, MFA/CSRF follow existing guards. A model's prompt, image data, API key and actor identity are not exposed through public calibration or file routes. Publication cannot establish architectural accuracy; review against reference material.

## Verification
`python -m pytest tests/test_meshy.py tests/test_models_3d.py tests/test_landmark_stories.py tests/test_integrations.py tests/test_rbac.py -q` from apps/api, with APP_ENV=test, DATABASE_URL=sqlite:// and ROUTING_PROVIDER=mock. Tests mock Meshy and never consume credits. Builds type-check both frontends. Live paid generation still needs a new key and a user-selected model/input.

## Official references (checked 2026-10-17)
- https://docs.meshy.ai/en/api/text-to-3d
- https://docs.meshy.ai/en/api/multi-image-to-3d
- https://docs.meshy.ai/en/api/pricing
- https://docs.meshy.ai/en/api/asset-retention (ordinary API assets retained up to 3 days)

## Gemini chat before Meshy
Portal now starts with a chat supporting 1–4 images, held in page memory only. Sending explicitly transmits the current images and the latest 15 text messages to Gemini through the backend. Gemini API key/model come from the dedicated encrypted `map3d_ai` integration (Gemini · Tạo mô hình 3D). Configure `gemini_api_key` and `gemini_model` there; this feature does not read the shared travel assistant key. The endpoint uses native Google generateContent with inlineData images and a responseSchema; model JSON is validated before showing the brief. The current local deployment uses `gemini-2.5-flash`; configure this model explicitly in `map3d_ai`. The former OpenAI-compatible route returned HTTP 503 during verification; native generation returned a valid brief. Errors do not expose provider bodies or secrets.

Gemini prepares a description; it does not create, edit images, or authorize a Meshy charge. The user reviews the brief and confirms the separate Meshy submission. Image mode forwards the original images (no geometry prompt support). Text mode sends the reviewed prompt, so requested textual changes can influence generation. No location/scale is inferred from Gemini. Chat history is not persisted after page reload.

Reference: https://ai.google.dev/gemini-api/docs/openai#image-understanding
Tests: tests/test_meshy_assistant.py verifies multimodal payload, RBAC, input/output validation, masked errors and that chat creates no paid Meshy jobs.


## Public Portal and runtime secrets
- Public Portal: `https://portal.localexplorerai.site`, Cloudflare Tunnel service `http://localhost:5174`.
- Public traveler site: `https://www.localexplorerai.site`, Tunnel service `http://localhost:8080`.
- Both frontends proxy `/api` to `http://127.0.0.1:8000`, using the same database. Set backend `PORTAL_APP_URL=https://portal.localexplorerai.site` and include that origin in `CORS_ORIGINS`.
- Configure Meshy, dedicated 3D Gemini, shared chat Gemini, and Goong keys in Portal integrations. Set a persistent `INTEGRATION_SECRETS_KEY` on the backend. Actual keys, passwords, databases and generated private models are not shipped in Git; provision them separately on each deployment.
- Goong model placement search uses the backend routing integration `goong_api_key`. Select a result in the calibration panel, then explicitly save the model position.
- Portal reads authoritative permissions from `/auth/me` after login/profile updates; the empty default permissions in mutation responses must not deny an administrator access.
