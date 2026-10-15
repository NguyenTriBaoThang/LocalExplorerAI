<div align="center">

<p align="center">
  <img src="./assets/images/logo.png" alt="Local Explorer AI logo" height="160" />
</p>

<h1 align="center">Local Explorer AI</h1>

<p align="center"><b>An AI-assisted platform for discovering, planning, and booking local experiences in Ho Chi Minh City.</b></p>

<p align="center">
  <a href="https://nguyentribaothang.github.io/LocalExplorerAI/">Technical documentation</a> ·
  <a href="./docs/architecture.md">Architecture</a> ·
  <a href="./docs/api.md">API reference</a> ·
  <a href="./docs/end-to-end-rollout.md">Pilot and rollout status</a>
</p>

<p align="center">
  <a href="https://github.com/NguyenTriBaoThang/LoaclExplorerAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/NguyenTriBaoThang/LoaclExplorerAI/ci.yml?label=CI" alt="CI status" /></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License" /></a>
  <a href="./.github/SECURITY.md"><img src="https://img.shields.io/badge/Security-Policy-red?logo=shield" alt="Security policy" /></a>
</p>

</div>

---

## What it does

Local Explorer AI helps travelers find activities and build itineraries around real-world constraints. The application combines a React web client with a FastAPI service. Its catalog separates a physical place (POI), an activity offered there (experience), and a dated, capacity-limited session (slot). Evidence and freshness metadata are used to keep sourced records distinct from imports and experiments.

The planner is responsible for hard constraints such as opening/session times, budget, group size, locked stops, capacity, travel time, and the return deadline. A ranker may order candidates only after those feasibility checks; it cannot make an unavailable or unverified activity feasible.

## Current status and important limits

This repository contains a working prototype and local integration code. A configured adapter or a passing mocked test does not establish that an external service has been verified in a live staging environment.

- The 177-row places workbook is an import source, not the live operational catalog. Current field-level evidence checks do not make those rows publishable yet. See [place import and verification](./docs/place-import-staging.md).
- OpenStreetMap and Wikimedia files are source candidates with their own coverage and licensing limits; they are not proof that every venue is open or that its prices and sessions are current.
- `rule-baseline-v1` is the default experience-ranking method. The XGBoost artifact in `models/ai-ranker/` is a weak-label bootstrap experiment and is not production-eligible. Its metrics must not be presented as evidence of real traveler preference quality.
- E5 model weights and a production road-flood model are not included. The flood-report experiment is a different task from predicting whether a road will flood or be passable.
- Booking, payment, OAuth, maps, LLM, and email flows require appropriate credentials and staging tests. Do not treat code presence or simulated provider data as a completed live integration.

For current rollout gates and the test boundary, see [end-to-end rollout](./docs/end-to-end-rollout.md) and [ML training and data](./docs/ml-training-and-data.md).

## Main application areas

- **Traveler:** account and profile, place discovery, AI chat with a fallback mode, itinerary planning, saved/shared itineraries, comparisons, and feedback.
- **Provider:** manage sourced places and activities, report dated availability, submit evidence, and respond to booking requests.
- **Administrator:** review imported places and evidence, moderate catalog records, manage accounts and integrations, and inspect operational/audit information.
- **Planning and routing:** check candidate feasibility and use configured route/geocoding services for outbound and return legs.
- **ML and search:** use a deterministic ranking baseline by default; optional model and semantic-search paths have explicit artifact/configuration requirements.

Availability in the UI depends on API configuration, reviewed catalog data, and whether the relevant external service has been set up. See the [API guide](./apps/api/README.md) and [web guide](./apps/web/README.md).

## Architecture

```text
apps/web (React + TypeScript + Vite)
        │ /api
        ▼
apps/api (FastAPI)
  ├── authentication and role-based access
  ├── sourced catalog, evidence, and moderation
  ├── planner, route adapters, and ranking fallback
  ├── itineraries, bookings, and payment callbacks
  └── operations and notification worker
        │
        ├── SQLite for local development / PostgreSQL + PostGIS for deployment
        ├── optional Redis
        └── external integrations configured per environment
```

Detailed design is documented in [architecture](./docs/architecture.md), [data model](./docs/data-model.md), [API reference](./docs/api.md), and [integration settings](./docs/integration-settings.md).

## Run locally

Use Python 3.12+, Node.js/npm, and Docker Desktop if you want the Compose database and Redis services. Set up the API environment and integration settings using `.env.example` and the linked configuration guides. Never put private API keys in frontend variables or commit a populated `.env` file.

Start the local database services from the repository root if using Docker Compose:

```powershell
docker compose up -d db redis
```

In a backend terminal:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item ..\..\.env.example .env }
alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

If `apps/api/.env` already exists, do not overwrite it; edit it carefully and keep secrets private. Configure the database URL for the environment you are using before applying migrations.

In a separate frontend terminal:

```powershell
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:8080`. The API is available at `http://localhost:8000`; Swagger UI is at `/docs`. For a guided local launch, see [`scripts/run-dev.ps1`](./scripts/run-dev.ps1).

## Checks

Run the API tests from `apps/api`:

```powershell
pytest -q
```

Run frontend checks from `apps/web`:

```powershell
npm run lint
npm run build
```

Only report a test suite as passing when the process exits normally with code `0`. CI configuration is in [`.github/workflows/ci.yml`](./.github/workflows/ci.yml).

## Data and model policy

The repository keeps source candidates, experimental datasets, operational catalog records, and model artifacts separate:

- [`data/raw/`](./data/raw/README.md): imported workbooks, OSM candidates, image-source metadata, and historical reports; these are not automatically production data.
- [`data/experimental/`](./data/experimental/README.md): weak-label ranking and flood-report experiments; not real-user preference or road-flood ground truth.
- [`data/training/`](./data/README.md): templates and instructions for reviewed training records. Do not invent labels, slots, evidence, or negative observations.
- [`models/`](./models/README.md): model files and metadata, with promotion and eligibility limits documented explicitly.

## Repository map

```text
apps/api/          FastAPI service, migrations, and API tests
apps/web/          Traveler, provider, and admin web application
data/              Raw, experimental, and training data
docs/              API, architecture, catalog, operations, and ML documentation
docs-site/         Static documentation site published with GitHub Pages
models/            Ranker and other model artifacts/metadata
models_3d/          3D landmark assets and calibration data
notebooks/         Google Colab training and evaluation notebooks
Places/             Original places workbook
scripts/            Development, data, model, and database utilities
```

## Further documentation

- [API backend](./apps/api/README.md) · [Web frontend](./apps/web/README.md) · [Scripts](./scripts/README.md)
- [Sourced catalog](./docs/sourced-catalog.md) · [Place import staging](./docs/place-import-staging.md)
- [Bookings and payments](./docs/bookings-and-payments.md) · [Operations](./docs/operations.md)
- [ML training and data](./docs/ml-training-and-data.md) · [Ranker benchmark](./docs/experience-ranker-benchmark.md)
- [Documentation site](./docs-site/README.md) · [Demo walkthrough](./DEMO_SCRIPT.md)

## License

The software is licensed under the [MIT License](./LICENSE). Data and image assets may have separate attribution and license requirements; follow the source-specific terms documented with each dataset.
