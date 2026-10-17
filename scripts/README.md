# Local Explorer AI — System scripts directory

The scripts/ directory contains automation for data collection, image processing, machine-learning model training, database operations, and system testing for **Local Explorer AI**.

---

## 🗂️ Script categories

### 1. Collecting, processing, and enriching Saigon place data

| Script | Language | Purpose |
|---|---|---|
| crawl_district1_places.py | Python | Collects cultural, historical, and food place candidates in District 1 from open sources |
| download_district1_photos.py | Python | Retrieves candidate images for District 1 places; coverage is not guaranteed for every place |
| attach_district1_photos_to_catalog.py | Python | Attaches eligible downloaded image references to the catalog data |
| generate_full_places_data.py | Python | Combines data from multiple sources into a JSON output |
| saigon_places_data_part1.py / part2.py | Python | Partial source modules for the Saigon place catalog |
| apply_enriched_places.py | Python | Applies additional fields (rating, review, open_hours) to catalog data |
| analyze_places_excel.py | Python | Analyzes the structure of Places/Sai_Gon_Places.xlsx |
| deep_check_excel.py | Python | Performs detailed validation and checks for missing spreadsheet fields |
| check_places_detail.py | Python | Checks place JSON consistency and details |
| dump_sheets.py / dump_indexed.py | Python | Exports spreadsheet sheets and indexed rows for review |

Crawled places and image matches are source candidates, not proof of current operating status. Check source attribution and each image's license. Use the admin staging workflow before promoting operational place data.

### 2. Machine-learning model training

| Script | Example command | Purpose |
|---|---|---|
| train_experience_ranker.py | python scripts/train_experience_ranker.py --mode weak_label | Trains/benchmarks XGBoost and LightGBM rankers (ranker-features-v2) on weak-label data |
| train_verified_experience_ranker.py | python scripts/train_verified_experience_ranker.py | Trains a ranker on human-reviewed data when a qualifying dataset is available |
| train_verified_flood_risk.py | python scripts/train_verified_flood_risk.py --input <verified.csv> --output models/flood-risk-candidate | Fits a chronological-group-split flood model only from directly verified flood and no-flood observations; requires explicit approval to mark it deployable |
| train_bootstrap_experience_ranker.py | python scripts/train_bootstrap_experience_ranker.py | Early experimental bootstrap version |
| verify_alignment.py | python scripts/verify_alignment.py | Checks feature-contract alignment between the backend API and ML pipeline |
| download_e5_model.py | python -m scripts.download_e5_model (from apps/api) | Downloads intfloat/multilingual-e5-base into models/e5/ |

### 3. Flood-risk research

| Script | Example command | Purpose |
|---|---|---|
| download_hcmc_flood_reports.py | python scripts/download_hcmc_flood_reports.py | Downloads and converts the 2002–2026 Ho Chi Minh City historical flood reports to UTF-8 CSV |
| build_flood_report_weak_labels.mjs | node scripts/build_flood_report_weak_labels.mjs | Generates 662 balanced examples for predicting the presence of public flood reports |
| build_flood_report_experiment_notebook.py | python scripts/build_flood_report_experiment_notebook.py | Creates a standalone research Colab notebook |

The flood-report experiment measures the presence of a source report; it does not label physical road flooding or verified dry conditions.
The verified flood template is `data/training/flood_risk_verified_template.csv`. The current raw reports do not meet its requirements; do not use the report-presence pseudo-negatives as dry observations.

### 4. Operations, databases, and development environments

| Script | Environment | Purpose |
|---|---|---|
| run-dev.ps1 | Windows PowerShell | Starts the DB/Redis containers and prints instructions to launch Vite and FastAPI separately |
| production-smoke.ps1 | Windows PowerShell | Runs smoke checks for main API flows before a release |
| backup-postgres.ps1 / .sh | PowerShell / Bash | Creates a timestamped PostgreSQL backup |
| restore-postgres.ps1 / .sh | PowerShell / Bash | Restores PostgreSQL from a backup |

---

## 🚀 Common commands

### Start the development environment (database services, then app processes separately)

~~~powershell
./scripts/run-dev.ps1
~~~

### Run a pre-deployment smoke test

~~~powershell
./scripts/production-smoke.ps1
~~~

### Back up PostgreSQL

~~~powershell
./scripts/backup-postgres.ps1
~~~

### Train/benchmark the Experience Ranker

~~~powershell
python -m pip install -r apps/api/requirements-ranking-training.txt
python scripts/train_experience_ranker.py --mode weak_label
~~~

This is a weak-label experiment, not a production model training workflow.

### Check ML feature-contract alignment

~~~powershell
python scripts/verify_alignment.py
~~~

### Download and rebuild the weak-label flood-report dataset

~~~powershell
# Download the latest historical flood-report data:
python scripts/download_hcmc_flood_reports.py

# Regenerate weak labels (use --force if the output file already exists):
node scripts/build_flood_report_weak_labels.mjs --force
~~~

---

## 🔗 Related resources

- **Source data:** [data/](../data/README.md) — raw, experimental, training, and ranking datasets
- **ML models:** [models/](../models/README.md) — ai-ranker, e5, flood-risk artifacts
- **API backend:** [apps/api/](../apps/api/README.md) — seed_db, import_place_candidates, worker, zalo_bot_poller
- **Research notebooks:** [notebooks/](../notebooks/) — Flood Report Experiment Colab
