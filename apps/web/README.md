# Web application — Local Explorer AI

The frontend is a React and TypeScript single-page application built with Vite. It calls the API through relative /api paths; the local Vite configuration proxies API and health-check requests to http://127.0.0.1:8000.

## Run locally

~~~powershell
cd apps/web
npm ci
npm run dev
~~~

Open http://localhost:8080. Run the backend separately on port 8000 and configure it using the root .env.example and the API documentation. Never put private API credentials in frontend variables: client-side values can be read by users.

## Check and build

~~~powershell
npm run lint
npm run build
npm run preview
~~~

## Application areas

The web application includes place discovery and details, chat/concierge, itinerary planning, itinerary sharing and comparison, and role-specific areas. Actual availability depends on the API, reviewed catalog records, and integration configuration. An imported candidate, placeholder, or experimental record is not a verified operational catalog entry.

## Related documentation

[API](../../docs/api.md) · [Architecture](../../docs/architecture.md) · [Authentication and search setup](../../docs/auth-and-search-setup.md) · [Sourced catalog](../../docs/sourced-catalog.md)
