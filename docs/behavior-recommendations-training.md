# Behavior-based recommendations: data and training

Explore records impressions and selections only for signed-in travelers who
opt in. A separate demo ranker can reorder the existing Explore candidates in
local development after the traveler enables personalization. The planner and
active production ranker remain unchanged; guest recommendations continue to
use the existing catalog and filters.

## Data flow

1. A traveler chooses separately whether to use activity for personalization,
   allow de-identified activity in model training, and allow administrators to
   inspect their identifiable Explore history.
2. Explore sends a list request ID, coarse filters, displayed experience IDs,
   display positions, and selection events. Free-text searches, names, email,
   phone, and map coordinates are not recorded.
3. The API checks current consent before writing events and takes candidate
   feature snapshots from the existing catalog. The browser cannot supply
   candidate tags, prices, or verification status.
4. The dataset builder attributes later itinerary additions and confirmed
   bookings to the latest matching impression within seven days.
5. The local demo loads the XGBoost artifact from
   `models/behavior-ranker-experiment/`. Its source data is generated and its
   artifact is marked non-deployable. It is not used by production or the
   itinerary planner.

## Storage and consent

- `recommendation_consents` stores separate personalization, training, and
  administrator-history choices, all off by default.
- `recommendation_interactions` stores `impression`, `selected`, and
  `dismissed` events. Each row has the recommendation request, display
  position, a coarse context snapshot, a catalog-derived feature snapshot,
  consent version, and separate eligibility flags for personalization, model
  training, and administrator history. Turning off one choice clears that
  eligibility on prior events while preserving rows still eligible for the
  other opted-in purposes.
- Turning off model-training consent excludes the user's stored rows from
  future training exports. Turning off administrator-history consent hides
  identifiable Explore events from customer-history views. Turning off all
  three choices deletes this feature's interaction rows. Previously exported
  local CSVs or model artifacts are not automatically rewritten and must be
  removed separately.
- The Admin customer-history view may show itineraries, booking summaries, and
  feedback ratings for support operations. It shows identifiable Explore
  events only after the customer separately opts in from Profile. Each admin
  history view is written to the audit log; feedback comments and payment
  references are not included in this view.
- Event context is allowlisted: category intent, budget band, group size,
  indoor preference, and time of day. Search text is excluded.

## Labels in the prepared dataset

The CSV has one row per displayed candidate. Candidates in the same
`query_id` form one ranking group.

| Grade | Evidence |
| --- | --- |
| 0 | Displayed and no qualifying follow-up within the attribution window; weak implicit negative, not an explicit dislike |
| 1 | Selected from the same Explore list |
| 2 | Added to an itinerary within seven days |
| 3 | Booking confirmed within seven days |

The builder waits until a full request group is at least seven days old before
including it, avoiding premature negatives. Itinerary-level star ratings are
not assigned to individual experiences. An explicit dismissal event is
supported by the API but is not yet exposed as a button in Explore.

The dataset contains an HMAC pseudonym for temporal analysis, but that
identifier is excluded from the model features. The script requires
`APP_SIGNING_SECRET`; it never writes that secret to the CSV.
Generated datasets and model artifacts are ignored by Git.

## Prepare and compare

For PostgreSQL, set `DATABASE_URL` to the target PostgreSQL/PostGIS database
and run the additive migration from the API directory. The historical
migrations include PostgreSQL/PostGIS-specific SQL, so the full Alembic chain
does not run against the local SQLite database:

```powershell
Set-Location apps/api
$env:DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE"
python -m alembic upgrade head
Remove-Item Env:DATABASE_URL
Set-Location ..
```

The current local SQLite database has the two new tables initialized directly
from SQLAlchemy metadata. Fresh SQLite development/test databases should use
the project's metadata initialization path; do not point Alembic's historical
PostgreSQL chain at SQLite.

After the schema is ready, collect opted-in Explore activity. Only rows whose
model-training consent is on at export time enter the dataset:

```powershell
python scripts/build_behavior_ranking_dataset.py
python -m pip install -r apps/api/requirements-ranking-training.txt
python scripts/train_behavior_ranker.py
```

The builder writes `data/derived/behavior-ranking/training_dataset.csv` and a
metadata sidecar. The trainer uses a chronological 70/15/15 split by request,
keeps requests intact, and reports NDCG@5 and Recall@5 for both rule baselines
and XGBoost. It requires at least 20 useful multi-candidate requests with a
positive interaction; until then it exits with a data-volume message rather
than producing a misleading score.

The existing OSM category-rule ranking experiment is not a substitute for
these labels: it contains assumed scenarios and weak category labels, not
observed user behavior. The new output is not eligible for deployment until
its data coverage, consent handling, offline results, and prospective product
evaluation have been reviewed.
