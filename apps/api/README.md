# API — Local Explorer AI

The FastAPI service in apps/api serves the web client and the catalog, planning, authentication, role-based access, provider/admin, and booking flows. See the [API reference](../../docs/api.md) for the endpoint contract.

> **Status:** This repository contains a prototype. Adapter code and configuration do not prove that Goong, OAuth, an LLM, email, or payment has passed a live staging acceptance test. The API uses the rule baseline by default; the XGBoost bootstrap artifact is weak-label research and is not production-eligible. E5 weights and a road-flood model are not included. See the [ranker benchmark](../../docs/experience-ranker-benchmark.md) and [ML guide](../../docs/ml-training-and-data.md).

## Business boundaries

- The planner checks time, budget, locked stops, capacity, and outbound/return routing constraints.
- A ranker only orders candidates after feasibility checks; it does not confirm availability or price and cannot override planner constraints.
- POIs, experiences, and slots should be used operationally only when their provenance/evidence is appropriate and current.
- External payment/provider callbacks, OAuth, email, and map APIs require credentials, a test/staging environment, HTTPS callbacks where applicable, and separately recorded smoke tests.

## Run locally (PowerShell)

~~~powershell
cd apps/api
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
# Create apps/api/.env from the root .env.example if it does not exist.
if (-not (Test-Path .env)) { Copy-Item ../../.env.example .env }
alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
~~~

Do not overwrite an existing environment file blindly, commit secrets, or place private keys in frontend variables. The database and integrations may need configuration. See [authentication and search setup](../../docs/auth-and-search-setup.md), [integration settings](../../docs/integration-settings.md), and the [data model](../../docs/data-model.md).

## Tests

~~~powershell
pytest -q
~~~

Run the command from apps/api. Claim the suite passed only if the process exits normally with code 0. CI runs backend tests, lint checks, and Alembic history validation as defined in the [workflow](../../.github/workflows/ci.yml).

## Source layout

- app/api/routes/: HTTP routers.
- app/services/: planner, ranking, booking, catalog, and business logic.
- app/adapters/: external-service integrations.
- app/models/ and app/schemas/: ORM models and data contracts.
- migrations/: Alembic revisions.
- tests/: API and business-logic tests.

## Documentation

[API](../../docs/api.md) · [Architecture](../../docs/architecture.md) · [Bookings and payments](../../docs/bookings-and-payments.md) · [Operations](../../docs/operations.md) · [ML training and data](../../docs/ml-training-and-data.md)
