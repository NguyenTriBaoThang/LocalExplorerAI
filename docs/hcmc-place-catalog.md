# HCMC place catalog (local preview)

`data/sai_gon_places.json` has 177 HCMC place records. The project audit in
`docs/place-import-staging.md` says their coordinates/addresses and operating
fields still need evidence review. The `verified` flag in that file is not
accepted as verification evidence.

For a local catalog preview, run from the repository root:

```powershell
$env:PYTHONPATH = "apps/api"
python apps/api/scripts/sync_hcmc_places_demo.py
```

The sync adds those rows as simulated place candidates and non-bookable Explore
discovery cards, hides the fictional `Điểm demo` fixtures from the public place
list, and does not invent prices, opening hours, photos, durations, or booking
slots. The detail page shows the source-provided description, address, hours,
price and note as unverified. It attaches local photos only when there is an
exact place-name match to the existing Wikimedia Commons manifest, with a
local image file, source page, license, and attribution. The current manifest
matches 7 of the 170 candidate rows; other rows keep the no-photo fallback
until a suitable licensed image is found. Candidate records retain their
original source URL and source fields, and show a warning in the UI. Explore's citywide catalog skips itinerary
filters (date, budget and radius) for these candidates because those facts are
not verified; the cards are excluded from behavior ranker training events.
The script refuses to run with `REAL_DATA_ONLY=true` or outside a local
development environment.

The Places directory can request `GET /api/pois?scope=citywide`, and Explore
uses `GET /api/experiences?scope=citywide`. The planner remains scoped to the
existing District 1 pilot; candidate cards have no booking slots.
This 177-row source file is a project dataset, not a claim that it contains
every place in the current administrative area of Ho Chi Minh City. Verify
each candidate's location and required field-level evidence before approving
it for operational use.
