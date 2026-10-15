# Local Explorer AI — Documentation site

The static technical documentation and showcase for **Local Explorer AI** is built with React, TypeScript, and Vite and deployed to GitHub Pages.

> **This is not the product application** (apps/web). It does not require a backend, database, API key, or environment variables.

---

## ⚙️ Technology

- **Framework:** React + TypeScript + Vite
- **Icons:** lucide-react
- **Routing:** Hash-based (#/architecture, #/api, etc.); deep links work on GitHub Pages without server fallback.
- **3D:** Does not use Three.js; the Digital Twin page is a lightweight SVG diagram.
- **Hosting:** GitHub Pages through GitHub Actions

---

## 🚀 Local development

~~~bash
cd docs-site
npm install
npm run dev
~~~

## 🏗️ Build

~~~bash
npm run build
~~~

Output is written to docs-site/dist/. The base: './' setting is intended to make the build work under GitHub Pages project URLs.

## 👁️ Preview

~~~bash
npm run preview
~~~

---

## 🌐 GitHub Pages deployment

1. Push the repository to GitHub.
2. Go to **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. The .github/workflows/deploy-pages.yml workflow builds docs-site and deploys it with the configure-pages, upload-pages-artifact, and deploy-pages actions.

**Triggers:** Pushes to main or gh-page that include changes under docs-site/, or a manual run (workflow_dispatch).

**Public URL:** https://nguyentribaothang.github.io/LocalExplorerAI/

---

## 📝 Documentation content sources

The content is derived from the repository's implementation:

| Content | Source |
|---|---|
| Endpoints and access levels | @router decorators in apps/api/app/api/routes/ and require_roles dependencies |
| Request/response bodies | Pydantic schemas in apps/api/app/schemas/ |
| Ranker features (15) | FEATURE_NAMES in apps/api/app/services/ranker_features.py |
| ML caveats and safety | docs/ml-training-and-data.md |
| Demo walkthrough, story, roadmap | DEMO_SCRIPT.md, COMPETITION_SUBMISSION.md, README.md |
| Screenshots | assets/screenshots/*.png, converted to WebP in public/img/ |

Interactive data (concierge demo, replanning, Digital Twin, explainability meter) uses hand-written sample data and is clearly marked; it does not call the backend.

---

## ⚠️ Known documentation gaps

> [!WARNING]
> - The older ARCHITECTURE.md describes Haversine routing; it has since been **updated** to reflect the Goong Directions API.
> - The repository does not include the E5 or flood-risk model weights. The ranker artifact that is present is a bootstrap/weak-label experiment, not a production-eligible model. See the model cards and [ML guide](../docs/ml-training-and-data.md).
> - The Digital Twin page in docs-site is an SVG schematic, not the Three.js experience in the product application.

---

## 📁 Directory structure

~~~text
docs-site/
├── src/
│   ├── data/        # Static JSON for interactive demos
│   ├── pages/       # Documentation pages: architecture, API, ML, planning, demo...
│   └── components/  # Shared UI components
├── public/
│   └── img/         # Screenshots and diagrams (WebP format)
├── index.html
└── vite.config.ts
~~~
