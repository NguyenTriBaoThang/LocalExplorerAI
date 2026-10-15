# Project scripts

The scripts directory contains utilities for place-source collection, image metadata, model training, data inspection, development, database backup, and smoke testing. Inspect a script's command-line help and source before running it; collection scripts contact external services and source terms apply.

## Place and image data

| Script | Purpose |
|---|---|
| crawl_district1_places.py | Collects named OpenStreetMap candidates inside the configured historical District 1 pilot boundary. This is not a complete or operationally verified venue list. |
| download_district1_photos.py | Retrieves candidate place images and source metadata where available; it cannot guarantee an image for every place. Check each file's license and required credit. |
| attach_district1_photos_to_catalog.py | Attaches eligible local image references to the project catalog data. |
| generate_full_places_data.py | Generates/combines place-data files from the project data sources. Review provenance before using its output operationally. |
| saigon_places_data_part1.py / saigon_places_data_part2.py | Place-data source modules. |
| apply_enriched_places.py | Applies place enrichment fields to catalog data. |
| analyze_places_excel.py / deep_check_excel.py | Inspect workbook structure and missing or invalid fields. |
| check_places_detail.py | Checks place JSON details and consistency. |
| dump_sheets.py / dump_indexed.py | Export workbook sheets and indexed rows for inspection. |

OSM discovery and image matching produce source candidates, not verified current operating facts. The supported catalog intake path is the API's admin staging queue; see [place import and verification](../docs/place-import-staging.md).

## Model and dataset utilities

| Script | Example | Purpose |
|---|---|---|
| train_experience_ranker.py | python scripts/train_experience_ranker.py --mode weak_label | Reproduce a research benchmark on weak-label ranking data. Not a production promotion path. |
| train_verified_experience_ranker.py | python scripts/train_verified_experience_ranker.py | Validate/train from reviewed human-label data when a qualifying dataset exists. |
| train_bootstrap_experience_ranker.py | python scripts/train_bootstrap_experience_ranker.py | Train the explicitly experimental bootstrap ranker. |
| verify_alignment.py | python scripts/verify_alignment.py | Check the feature contract shared by the API and training pipeline. |
| download_e5_model.py | python -m scripts.download_e5_model (from apps/api) | Download intfloat/multilingual-e5-base to the configured models/e5 location. |

The verified training template in data/training is intentionally header-only. Do not fabricate labels, user outcomes, or operational features to make training run.

## Flood-report research

| Script | Example | Purpose |
|---|---|---|
| download_hcmc_flood_reports.py | python scripts/download_hcmc_flood_reports.py | Download/convert the public historical Ho Chi Minh City report dataset. |
| build_flood_report_weak_labels.mjs | node scripts/build_flood_report_weak_labels.mjs | Rebuild an experiment about public report presence; not physical flood labels. |
| build_flood_report_experiment_notebook.py | python scripts/build_flood_report_experiment_notebook.py | Generate the separate Colab research notebook. |

The historical reports and weak-label experiment are not suitable as verified no-flood observations for road-level prediction.

## Development and operations

| Script | Environment | Purpose |
|---|---|---|
| run-dev.ps1 | Windows PowerShell | Starts the local database services and prints instructions for starting the API and web app. |
| production-smoke.ps1 | Windows PowerShell | Runs configured API smoke checks before a release. |
| backup-postgres.ps1 / backup-postgres.sh | PowerShell / Bash | Create a timestamped PostgreSQL backup. |
| restore-postgres.ps1 / restore-postgres.sh | PowerShell / Bash | Restore a PostgreSQL backup. |

## Common commands

From the repository root:

~~~powershell
./scripts/run-dev.ps1
./scripts/production-smoke.ps1
./scripts/backup-postgres.ps1
python scripts/verify_alignment.py
~~~

From apps/api, install the ranker training dependencies and run the weak-label benchmark:

~~~powershell
python -m pip install -r requirements-ranking-training.txt
cd ../..
python scripts/train_experience_ranker.py --mode weak_label
~~~

Check each command's working-directory expectations before running it. For database recovery, verify the target database and backup before restoring.

## Related resources

- [Data](../data/README.md)
- [Model artifacts](../models/README.md)
- [API](../apps/api/README.md)
- [ML training guide](../docs/ml-training-and-data.md)
