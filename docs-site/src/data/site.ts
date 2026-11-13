export const REPO_URL = 'https://github.com/NguyenTriBaoThang/LocalExplorerAI'

export type Status = 'implemented' | 'partial' | 'planned' | 'experimental' | 'verified'

export const STATUS_LABEL: Record<Status, string> = {
  verified: 'Verified Production',
  implemented: 'Implemented',
  partial: 'Implemented, caveats',
  experimental: 'Experimental Pilot',
  planned: 'Planned',
}

export interface NavItem {
  id: string
  label: string
  path: string
  blurb: string
}

export const NAV: NavItem[] = [
  { id: 'overview', label: 'Overview', path: '/', blurb: 'What LocalExplorerAI is and what it can do' },
  { id: 'architecture', label: 'Architecture', path: '/architecture', blurb: 'System diagram, data model, technical decisions, repository' },
  { id: 'concierge', label: 'AI Concierge', path: '/concierge', blurb: 'Natural-language constraint extraction & streaming trips' },
  { id: 'planning', label: 'Planning', path: '/planning', blurb: 'Planning pipeline, constraints, replanning & version restore' },
  { id: 'ml', label: 'Machine Learning', path: '/ml', blurb: 'E5 semantic search, XGBoost ranker, quote win model, flood risk' },
  { id: 'digital-twin', label: 'Digital Twin', path: '/digital-twin', blurb: 'Lightweight city visualization & Meshy 3D generation' },
  { id: 'platform', label: 'Platform', path: '/platform', blurb: 'Traveler, provider, tour operator and admin portals' },
  { id: 'api', label: 'API', path: '/api', blurb: 'Endpoint reference across 33 FastAPI routers' },
  { id: 'demo', label: 'Demo', path: '/demo', blurb: 'Walkthrough, screenshots and project story' },
  { id: 'roadmap', label: 'Roadmap', path: '/roadmap', blurb: 'Implemented, in progress, planned' },
]

/** Where a claim can be checked, relative to the repository root. */
export const SRC = {
  planner: 'apps/api/app/services/planner_engine.py',
  replan: 'apps/api/app/services/replanning_service.py',
  ranker: 'apps/api/app/services/ml_ranker_service.py',
  features: 'apps/api/app/services/ranker_features.py',
  e5: 'apps/api/app/services/e5_search_service.py',
  flood: 'apps/api/app/services/flood_model_service.py',
  routing: 'apps/api/app/services/routing_service.py',
  quote: 'apps/api/app/services/quote/',
  meshy: 'apps/api/app/services/meshy_service.py',
  routes: 'apps/api/app/api/routes/',
  entities: 'apps/api/app/models/entities.py',
  prompts: 'apps/api/app/prompts/v3_2_0/',
  web: 'apps/web/src/',
  portal: 'apps/portal/src/',
  migrations: 'apps/api/migrations/versions/',
  models: 'models/',
}
