# Local Explorer AI documentation site

This is the static technical documentation and showcase for Local Explorer AI. It is built with React, TypeScript, and Vite and published to GitHub Pages.

> This is not the product application in apps/web. The documentation site does not require the product backend, a database, API keys, or environment variables.

## Technology

- Framework: React, TypeScript, and Vite.
- Icons: lucide-react.
- Routing: hash-based paths such as #/architecture and #/api, so deep links work on GitHub Pages without a server fallback.
- Digital Twin page: a lightweight SVG schematic; it does not use Three.js.
- Hosting: GitHub Pages through GitHub Actions.

## Develop locally

~~~bash
cd docs-site
npm install
npm run dev
~~~

## Build and preview

~~~bash
npm run build
npm run preview
~~~

Build output is written to docs-site/dist/. The relative Vite base path is intended to support the GitHub Pages project URL.

## Deploy to GitHub Pages

1. Push the repository to GitHub.
2. In repository Settings → Pages → Build and deployment, choose GitHub Actions as the source.
3. The .github/workflows/deploy-pages.yml workflow builds docs-site and deploys it with the Pages actions.

The workflow can run on its configured branch/path changes or be started manually with workflow_dispatch. Public site: https://nguyentribaothang.github.io/LocalExplorerAI/

## Documentation sources and demo data

The site documentation is maintained in docs-site/src and draws implementation details from the API routers, Pydantic schemas, ranker feature builder, and repository documentation. Interactive examples use clearly identified static sample data and do not call the product backend.

## Known boundaries

- The bootstrap ranker stored in the repository is experimental, not production-eligible.
- E5 model weights and a road-flood model are not included. The historical report-presence experiment is a separate task.
- The documentation site's SVG Digital Twin illustration is not the Three.js view in the product app.

## Directory layout

~~~text
docs-site/
├── src/
│   ├── data/        # Static JSON for interactive examples
│   ├── pages/       # Architecture, API, ML, planning, and demo pages
│   └── components/  # Shared UI components
├── public/
│   └── img/         # Screenshots and diagrams
├── index.html
└── vite.config.ts
~~~
