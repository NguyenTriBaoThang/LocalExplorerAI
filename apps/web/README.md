# Web application — Local Explorer AI

The frontend is a React and TypeScript single-page application built with Vite. It calls the API through relative /api paths; the local Vite configuration proxies API and health-check requests to http://127.0.0.1:8000.

## Run locally

    cd apps/web
    npm ci
    npm run dev

Open http://localhost:8080. Run the backend separately on port 8000 and configure it using the root .env.example and the API documentation. Do not put API secrets in the frontend because client-side values can be viewed by users.

## Checks and build

    npm run lint
    npm run build
    npm run preview

## Interface

The web app includes place discovery, chat/assistant, itinerary planning, itinerary sharing/comparison, and role-specific areas. Real availability depends on the API, reviewed data, and integration configuration. Place-import candidates, placeholders, and experimental data must not be treated as a verified catalog.

## Related documentation

[API](../../docs/api.md) · [Architecture](../../docs/architecture.md) · [Authentication and search setup](../../docs/auth-and-search-setup.md) · [ML training and data](../../docs/ml-training-and-data.md)
