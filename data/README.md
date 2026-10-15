# Data directory

The data directory separates raw source material, experimental datasets, and training templates. Not every file here is suitable for the live catalog or production training.

## Raw source data

- data/raw/Sai_Gon_Places.xlsx is a project-provided workbook staged for review. Its 177 rows are not currently publishable under the field-level evidence checks; see [place import and verification](../docs/place-import-staging.md).
- data/raw/district1_osm_places.json contains named OpenStreetMap source candidates inside a historical District 1 pilot polygon. It is not a complete place list and does not establish current opening status, price, or availability.
- The District 1 photo manifest and local-photo JSON retain source metadata. Use an image only when its individual source, license, and required credit are known.
- data/raw/hcmc_flood_reports_2002_2026.csv is a historical report dataset, not a road/time flood training set.
- data/raw/flood_training.csv is not assumed to be training-ready. Validate its schema and provenance; do not infer dry observations or observation times.

See [raw data notes](raw/README.md).

## Experimental data

- data/experimental/ranking/ranking_candidates_labeled.csv contains OSM-derived candidates crossed with six analyst-assumed intent profiles and weak rule-generated labels. It measures imitation of those rules, not real traveler preferences.
- data/experimental/flood_training_weak_labels.csv is an experiment about whether a public flood report appears in the source for a place/month. Its negative labels do not mean a road was observed to be dry.

See [experimental data notes](experimental/README.md) and [ranking notes](experimental/ranking/README.md).

## Training data

data/training/experience_ranker_verified_template.csv is a header-only template for collecting reviewed ranking examples. It intentionally contains no synthetic examples. Do not add user identifiers, fabricate labels, or claim operational facts without evidence. See the [ML training guide](../docs/ml-training-and-data.md).

## Import workflow

POI workbook rows are imported into an admin-only staging queue; they are not inserted directly into the live catalog. From apps/api, use:

~~~powershell
python -m scripts.import_place_candidates --dry-run
python -m scripts.import_place_candidates
~~~

Review and approve field-level evidence before publishing any operational record. Imports do not create experiences, prices, opening hours, or slots.

## Licensing and reproducibility

Preserve original source files, collection dates, hashes, and provenance. Follow the source-specific terms. OpenStreetMap-derived data requires applicable ODbL attribution/obligations; Wikimedia image files have individual licenses and attribution requirements. The historical flood dataset is subject to its stated CC BY-NC 4.0 terms; review the non-commercial restriction before reuse.

## Related folders

- [Models](../models/README.md)
- [Scripts](../scripts/README.md)
- [API](../apps/api/README.md)
