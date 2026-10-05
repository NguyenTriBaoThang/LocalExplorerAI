# LocalExplorerAI documentation site

A static technical documentation and showcase site for LocalExplorerAI. It is **not** the product app (`apps/web`) and needs no backend, database, API key or environment variable.

Built with React, TypeScript and Vite, plus `lucide-react` for icons. Routing is hash-based (`#/architecture`), so deep links work on GitHub Pages without a server fallback. No Three.js is loaded; the digital twin page is a lightweight SVG schematic.

## Development

```bash
cd docs-site
npm install
npm run dev
```

## Build

```bash
npm run build
```

The output is written to `docs-site/dist`. `base` is `./`, so the build works under `https://<user>.github.io/<repo>/` without hardcoding either name.

## Preview

```bash
npm run preview
```

## GitHub Pages

1. Push the repository to GitHub.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set **Source: GitHub Actions**.

`.github/workflows/deploy-pages.yml` then builds `docs-site` and deploys it with the official `configure-pages`, `upload-pages-artifact` and `deploy-pages` actions. It runs on pushes to `main` or `gh-page` that touch `docs-site/`, and can be started manually. Expected URL: `https://<username>.github.io/LocalExplorerAI/`.

## Where the content comes from

All claims are taken from the repository and marked with their source file:

| Content | Source |
| --- | --- |
| Endpoints, access levels | `@router` decorators in `apps/api/app/api/routes/`, dependencies such as `require_roles` |
| Request bodies | Pydantic schemas in `apps/api/app/schemas/` |
| Ranker features | `FEATURE_NAMES` in `apps/api/app/services/ranker_features.py` |
| ML caveats | `docs/ml-training-and-data.md` |
| Demo walkthrough, story, roadmap | `DEMO_SCRIPT.md`, `COMPETITION_SUBMISSION.md`, `README.md` |
| Screenshots | `assets/screenshots/*.png`, converted to WebP in `public/img/` |

Data lives in `src/data/`. Interactive demos (concierge, replanning, digital twin, explainability meter) use hand-written sample data and are labelled as such; nothing on the site calls a backend.

## Known gaps in the source material

- Three diagram PNGs in `assets/diagrams/` and `assets/screenshots/itinerary.png` are blank placeholders and were not used.
- `ARCHITECTURE.md` describes Haversine routing and no LLM, while the code and README use Goong routing with a mock provider for tests. The site follows the code.
- The README mentions itinerary rollback; no rollback code was found.
- Trained model weights (ranker, E5, flood) are not in the repository.
