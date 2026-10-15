# API — Local Explorer AI

The FastAPI backend in apps/api/app serves the web application and catalog, planner, account/access-control, provider/admin, and booking flows. Endpoint contracts are described in [docs/api.md](../../docs/api.md).

> **Status:** This repository contains a prototype. Adapter code or configuration does not prove that Goong, OAuth, an LLM, email, or payments have passed acceptance testing in staging. The rule baseline is the default ranker; the XGBoost bootstrap artifact uses weak labels and is not a production model. E5 and flood-risk weights are not included in the repository. See the [ranking benchmark](../../docs/experience-ranker-benchmark.md) and [ML guide](../../docs/ml-training-and-data.md).

## Business boundaries

- The planner checks feasibility against time, budget, locked stops, capacity, and outbound/return routes.
- The ranker only orders candidates that have passed feasibility filters; it does not confirm slots or prices and does not replace planner checks.
- POIs, experiences, and slots should be used operationally only when their provenance/evidence is suitable and current.
- Payment/provider callbacks, OAuth, email, and map APIs require credentials, a test/staging environment, HTTPS callbacks where applicable, and separately logged smoke tests.

## Run locally (PowerShell)

    cd apps/api
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    # If apps/api/.env does not exist: Copy-Item ..\..\.env.example .env
    alembic upgrade head
    python -m uvicorn app.main:app --reload --port 8000

Do not commit environment files containing secrets. The database and integration settings may require configuration; see [authentication/search setup](../../docs/auth-and-search-setup.md), [integration settings](../../docs/integration-settings.md), and the [data model](../../docs/data-model.md).

## Tests

    pytest -q

Run from apps/api. Report the suite as passing only when the process exits normally with code 0. CI runs backend tests, lint, and Alembic history checks according to the [workflow](../../.github/workflows/ci.yml).

## Source layout

- app/api/routes/: HTTP routers.
- app/services/: planner, ranking, booking, catalog, and business logic.
- app/adapters/: external-service integrations.
- app/models/ and app/schemas/: ORM models and data contracts.
- migrations/: Alembic revisions.
- tests/: API and business-logic tests.

## Documentation

[API](../../docs/api.md) · [Architecture](../../docs/architecture.md) · [Bookings/payments](../../docs/bookings-and-payments.md) · [Operations](../../docs/operations.md) · [Research proposal](../../docs/research-proposal.md)
