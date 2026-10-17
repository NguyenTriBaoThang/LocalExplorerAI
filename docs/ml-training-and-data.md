# ML training and FastAPI model bundles

## Two separate models

Local Explorer AI has two distinct supervised-learning tasks. Do not combine their CSVs or metrics:

| Task | Input labels/data | Output | Colab notebook |
|---|---|---|---|
| Replacement-experience ranker (human labels) | `query_id`, planner-feasible candidates, human relevance grades 0–3 | Relative candidate order (`rank_score`) | `notebooks/LocalExplorerAI_Train_Verified_Ranker_Colab.ipynb` |
| Ranking weak-label benchmark (experiment only) | Six assumed intents and category-rule grades on OSM POIs | Baseline/LightGBM/XGBoost comparison; never production-ready | `notebooks/LocalExplorerAI_Ranking_Benchmark_Colab.ipynb` |
| Flood-risk classifier | Road-edge/time samples with verified flood and verified no-flood labels | Calibrated probability estimate for a road segment/time/horizon | `notebooks/LocalExplorerAI_Flood_Training_Colab.ipynb` |

## Experience ranker benchmark and current model

The current deployment choice is the built-in, versioned `rule-baseline-v1`, based on the completed Colab benchmark. The older ignored XGBoost artifact (`local-explorer-ranker-v1-20261003T014631Z`, trained from `data/dataset_ranking_tphcm.csv`) is unverified and does not meet the current deployment gate; its historical NDCG@5 of 0.9516 is not a same-data comparison. No ML artifact was selected in the supplied full benchmark because the baseline won validation.

The supplied `LocalExplorerAI_Weak_Ranking_Model.zip` contains a `RandomForestRegressor` weak-label prototype, not an XGBoost/LightGBM learning-to-rank model. Its NDCG@10=1.0 and MAE≈0.0036 are agreement with the category-rule labels only. Its `joblib` file is not loaded by this project; deserializing untrusted joblib/pickle files can execute code.

The new dataset is stored under `data/experimental/ranking/`. It has 638 OSM POIs crossed with six analyst-assumed intents, not real queries. The category-rule labels are weak. Price, duration, ETA, and some indoor values are estimates; hands-on status is unknown, and activity/slot/planner verification is absent. See the folder README for license and field-level provenance. Only the explicit `--mode weak_label` run accepts it, and the output metadata always says `deployment_eligible=false`.

`scripts/train_experience_ranker.py` compares the tag/category rule baseline, LightGBM LambdaRank, and XGBoost NDCG ranking with the same shared v2 API feature function, four configurations per algorithm, and a deterministic POI-disjoint 70/15/15 split. It selects by validation NDCG@5. NDCG@10, latency, model size, and three-seed validation stability are supporting checks. It reads the test split only after selection. A weak-data model is exported only if it exceeds baseline validation NDCG@5 by at least 0.01; otherwise the rule baseline is selected and no new ML artifact is created. The test output is therefore not a real-world quality claim.

Run the complete comparison in Google Colab using `notebooks/LocalExplorerAI_Ranking_Benchmark_Colab.ipynb`, or install `apps/api/requirements-ranking-training.txt` and run the script locally. The full run requires both LightGBM and XGBoost. CatBoost is not included because the present shared feature matrix is numeric, the dataset has only six assumed contexts, and its target is a deterministic category rule; another learner cannot supply missing human labels.

The adapter accepts native XGBoost JSON or LightGBM text bundles and preserves the v1 feature contract. The v2 builder represents unknown hands-on/indoor facts as missing with explicit known flags. Production ML requires both `dataset_status=verified_human_labeled` and `deployment_eligible=true`; weak experiments never meet that gate. There is one narrowly scoped opt-in for a bundle with the exact `model_mode=bootstrap_pilot` metadata; it remains `production_eligible=false` and `deployment_allowed=false`. If no eligible bundle is installed or it fails to load, the shared `rule-baseline-v1` scores candidates. The itinerary planner and replanner check route/time/budget/capacity/locked-stop rules first; ranking only orders candidates that already passed those checks.

See [the completed benchmark report](experience-ranker-benchmark.md) for the Colab comparison, selection, and the CSV checksum caveat.

The supplied `dataset_ranking_tphcm.csv` has 877 rows and 170 query groups. It includes 639 rows marked `hard_feasible=1` and 238 rows marked infeasible; all 238 infeasible rows have grade 0. Among feasible rows, grades are 0: 69, 1: 170, 2: 199, 3: 201. The file has no source URL, collection timestamp, reviewer ID, label-method, or provenance field. Its origin/label process therefore cannot be verified from the file alone. The new notebook marks the resulting bundle `unverified_user_dataset`; it does not create synthetic rows. Treat its metric as a pipeline check, not evidence of real-world ranking quality.

The supplied flood notebook is not compatible with that ranking CSV. Flood training also requires independently verified negative observations; missing flood reports cannot be relabeled as no-flood. The new flood notebook has no simulated-data fallback and refuses simulated/heuristic rows.

### Verified flood-risk training gate

`data/training/flood_risk_verified_template.csv` is a header-only collection template. Each row must describe a real road-edge decision time and future label window, with source/evidence URLs, reviewer provenance, a distinct observation-group ID, and explicit `verified_flood` or `verified_no_flood` status. A negative additionally needs at least 95% direct observation coverage during that interval and edge-level spatial precision. The trainer does not sample missing reports or generate labels.

The current 425-row public-report file does not satisfy this contract: it has no verified dry windows, project road-edge IDs, or sufficiently exact observation times. Consequently, no flood classifier is trained or shipped from the repository data.

When an authorized, reviewed dataset is available, install `apps/api/requirements-ml.txt` and run `python scripts/train_verified_flood_risk.py --input <verified.csv> --output models/flood-risk-candidate`. The gate requires at least 100 verified flood and 200 verified no-flood rows, at least 20 road edges and 20 independent observation groups per class, and chronological group splits that contain both labels. The candidate must reach test average precision ≥0.50, Brier score ≤0.20 and recall ≥0.80. It remains ineligible for inference unless the operator also supplies `--approve-deployment`; the API repeats the count, provenance, metric and approval checks from bundle metadata. Never edit metadata to bypass the checks.

## Public HCMC flood reports (raw, not training-ready)

`data/raw/hcmc_flood_reports_2002_2026.csv` is a CSV conversion of the 425-row, 22-column `Flood_event_locations.tab` published in DataSuds (Hardy & Radziute, 2026, [DOI 10.23708/8Y16HU](https://doi.org/10.23708/8Y16HU)). `data/raw/flood_training.csv` is a duplicate with the exact requested filename, **not a training-ready dataset**. The source compiles reported observations from 53 sources; 63 rows have no exact `Date` value in the downloaded table. The source file checksum is verified by `scripts/download_hcmc_flood_reports.py`; run that script to download and convert the original file again.

This is real historical event-report data, but it is **not** the Flood notebook's `flood_training.csv`: it has no independently observed no-flood windows, no project `edge_id`, and insufficient exact timestamps for the required decision-time/horizon labels. Do not create those values by inference from absent reports. The source is licensed CC BY-NC 4.0; cite the dataset and check the non-commercial restriction before redistribution or commercial use. See `data/raw/README.md` for attribution and limitations.

The strongest local candidate for richer, real event data is HCMC's Flood Data Exchange System (FEDS). A [World Bank implementation note](https://documents1.worldbank.org/curated/en/099052625225018333/pdf/P176260-dffa6f4e-18b1-412f-ab75-4e4dfe34167d.pdf) describes field-officer flood point/segment reports, WebGIS manager exports, and 954 reports submitted by April 2025 after a July 2024 restart. The note does not publish the underlying records as a public download; request an authorized export from the city data custodian. Confirm whether the export includes verified no-flood status observations and full observation coverage—flood reports alone still cannot train this binary classifier. The [public SCFC alert map](https://chongngap.hochiminhcity.gov.vn/baongap/) shows current flood/rain/tide/camera/report layers, but is not evidence of a downloadable historical training archive.

## FastAPI endpoints

- `GET /api/ml/status` — reports the active ranker, production eligibility, bootstrap pilot state, and rule-baseline fallback.
- `POST /api/ml/rank-experiences` — ranks planner-filtered replacement candidates with a verified local ranker, an explicitly enabled bootstrap pilot, or `rule-baseline-v1`. It filters `hard_feasible=false`, over-budget candidates, and candidates where `eta_min + duration_min > remaining_time_min`. Pass the exact group price, time budget, and current weather only when known. The score is not a probability.
- `POST /api/ml/flood-risk` — batch flood-risk inference using the flood bundle. A predicted risk is not a verified flood report or road closure and must never override a hard block. Unknown observations remain unknown.

Flood inference returns `risk_state=unknown` when `coverage_ratio` is absent; a low model probability alone is not evidence that a road is clear. The caller must supply a meaningful coverage measurement from the data pipeline.

The selected baseline is used by the normal itinerary planner only as a tie-break among candidates at the earliest feasible time; hard filters for budget, return deadline, slot, capacity, and locked experiences remain authoritative. It is also used by `ReplanningService` after its database checks. `/api/ml/status` reports when this fallback is active and why a bundle was not used. A baseline is not a trained ML artifact and has not been validated with human preference labels.

## Exact artifact placement

On the project host, unzip/copy the Colab ranker files here:

```text
models/ai-ranker/
  xgboost_ranker.json  # or lightgbm_ranker.txt; model_file is declared in metadata
  model_metadata.json
  feature_schema.json
  preprocessing.json
```

For flood, unzip the bundle here:

```text
models/flood-risk/
  model.joblib
  preprocessor.joblib
  metadata.json
  feature_schema.json
  calibration.json
  threshold.json
```

These artifact directories are ignored by Git. Do not commit trained weights or personal/user-level data. Set `INSTALL_ML=true` before building the API container to install `apps/api/requirements-ml.txt`. Docker Compose already mounts `./models` read-only at `/models`; the default model paths are `/models/ai-ranker` and `/models/flood-risk`. For a direct local API process, install the same optional requirements and set `RANKER_MODEL_DIR` / `FLOOD_MODEL_DIR` in `.env`. Restart/rebuild the API after copying artifacts. A Colab bundle is not loaded until its required files are in place. Flood inference refuses metadata with `demo_mode=true`.

The benchmark Colab output is a weak-label benchmark and produces no production ML bundle. A production bundle is loaded only when metadata declares both `dataset_status=verified_human_labeled` and `deployment_eligible=true`, and it includes a matching feature schema and model file. The separate bootstrap pilot path below is opt-in and never changes these production checks. Do not edit metadata flags to bypass provenance checks.

Only load joblib artifacts created by your own trusted Colab run. Python joblib/pickle files can execute code when deserialized.

## Train the ranker in Colab

### Verified human-label training workflow

Use [`LocalExplorerAI_Train_Verified_Ranker_Colab.ipynb`](../notebooks/LocalExplorerAI_Train_Verified_Ranker_Colab.ipynb) with [`experience_ranker_verified_template.csv`](../data/training/experience_ranker_verified_template.csv) and [`train_verified_experience_ranker.py`](../scripts/train_verified_experience_ranker.py). The CSV in the repository is header-only; it intentionally contains no example/synthetic records. Training cannot produce an eligible model until the team collects and reviews enough genuine post-trip labels.

For each `query_id`, include at least two distinct candidates actually shown by the planner and mark only candidates proven feasible at that time. The contract requires a completed trip and a human 0–3 relevance grade; stable POI/experience/slot IDs; actual address and coordinates; first-party/catalog URLs and evidence references for POI, activity, price, duration, outbound/return ETA, open slot and available capacity; timezone-aware confirmation timestamps plus validity/expiry timestamps; and the original query snapshot, travel mode, group size, budget and return deadline. `slot_status` must be `open`, available capacity must cover the group, the slot must fit the activity duration and outbound ETA, and the return ETA must meet the deadline. Set `estimated_columns` blank only when these values are confirmed rather than estimated. Set `training_eligible=true` only after auditing the record. Keep reviewer refs pseudonymous; never export names, email, raw chat or other direct identifiers.

Use one consistent rubric: grade 3 means the trip achieved the core purpose as promised; 2 means a close substitute with minor trade-offs; 1 means a purpose mismatch (such as a passive visit when hands-on participation was wanted); 0 means a serious real-world failure. Allowed `label_method` values are `consented_feedback_reviewed` and `independent_human_review`; both require an auditable completed-trip outcome, a versioned rubric and a label timestamp after trip completion. The script rejects the existing OSM/category weak-label CSV, inferred or estimated operational facts, unverified capacity, missing evidence, impossible return timing, duplicate candidates and too few query groups. It does not generate labels or fill missing values.

The benchmark compares the deterministic rule baseline and the same four LightGBM/XGBoost tuning configurations with identical shared API features, seed and query-disjoint 70/15/15 split. Validation NDCG@5 selects the model; NDCG@10, latency, native model size and three-seed stability are supporting metrics. Test is inspected only after selection. A production ZIP is emitted only if the selected ML ranker beats baseline validation NDCG@5 by at least 0.01 and is not worse on either test NDCG@5 or NDCG@10. Otherwise there is no deployable ZIP (or the ZIP is explicitly named `research_candidate_bundle_NON_DEPLOYABLE.zip`) and the API remains on `rule-baseline-v1`. This statistical gate does not replace human review or a pilot.

In Colab the notebook stores run reports under `MyDrive/LocalExplorerAI/ranker_runs/` and downloads `local_explorer_ranker_bundle.zip` only when the gate passes. Extract the ZIP contents directly into the project `models/ai-ranker/` directory, not into a nested folder. The bundle contains a native model file, `model_metadata.json` with dataset/model SHA-256 and promotion status, `feature_schema.json`, and `preprocessing.json`; the dataset and label evidence are not packaged. The API verifies the model checksum, exact shared feature contract and explicit verified/deployment metadata. Install `apps/api/requirements-ml.txt`, restart the API, send one ranking request to trigger model loading, then check `GET /api/ml/status` for `active_ranker=ml_ranker`, `deployment_allowed=true`, and `loaded=true`. Any failed check leaves the rule baseline active.

The current six-intent weak-label Colab comparison is a separate experiment. Do not upload its model, the weak RandomForest ZIP, or the OSM category-rule CSV as the verified dataset, and do not change metadata flags to bypass the gate.

1. For the current weak-label experiment, open `notebooks/LocalExplorerAI_Ranking_Benchmark_Colab.ipynb` and use the CSV in `data/experimental/ranking/`.
2. Run cells in order and retain the comparison/results as experiment artifacts. The supplied run selected the rule baseline and emitted no ML bundle because LightGBM/XGBoost did not beat it on validation.
3. Do not copy a weak-label or unverified-user-data bundle into `models/ai-ranker/`, and do not flip its metadata flags. The API will keep `rule-baseline-v1` active.
4. After collecting real, reviewed preference labels, retrain/benchmark on those records. Only install a bundle with `dataset_status=verified_human_labeled`, `deployment_eligible=true`, matching feature schema, and compatible model file under `models/ai-ranker/`; then restart and verify `GET /api/ml/status` reports `active_ranker=ml_ranker`.

### Current CSV bootstrap pilot (not human-verified)

The separate `notebooks/LocalExplorerAI_Bootstrap_Ranker_Colab.ipynb` and `scripts/train_bootstrap_experience_ranker.py` accept the supplied `experience_ranker_verified.csv` only when its weak-label provenance markers are intact. The inspected file has 960 rows, 120 query IDs, 60 scenario families, and 11 POIs. Labels are all `bootstrap_rule_v1`; the scenario, ETA, slot, and capacity fields are marked synthetic/fixture data, and no real-user feedback or operational feasibility is evidenced. The script ignores its `training_eligible` flag (including the 25 true values) and keeps `estimated_columns`; the filename does not make these labels verified.

The Colab run uses the shared API feature builder (`ranker-features-v2`), a fixed XGBoost `rank:ndcg` configuration, and a 70/15/15 split by `scenario_family_id`. It compares validation NDCG@5 to the rule baseline before reporting test metrics; the test set is not used for selection. It exports a **bootstrap candidate** regardless of whether the rule baseline wins, but records the validation recommendation and never marks the artifact production-eligible. POIs occur across split partitions, so this does not test generalization to unseen locations; the dataset also cannot establish quality for real users or availability. The bundle excludes the source CSV.

The reviewed `localexplorer_bootstrap_ranker_bundle.zip` has been staged under `models/ai-ranker/`; the exact model, metadata, preprocessing, schema, metrics, comparison, predictions, and model card are retained in the repository. The source training CSV is not part of the bundle and is not copied here. The artifact checksum and API feature contract were checked. Install `apps/api/requirements-ml.txt` and restart the API. Keep `ENABLE_BOOTSTRAP_RANKER=false` for normal service. To intentionally run a pilot, set `ENABLE_BOOTSTRAP_RANKER=true` and restart. `/api/ml/status` must show `active_ranker=bootstrap_ml_ranker`, `pilot_runtime_enabled=true`, `production_eligible=false`, and `deployment_allowed=false`; ranking responses and itinerary explanations show an experimental warning. Only this exact metadata mode is accepted; generic weak-label artifacts remain blocked. To recreate the staged artifact, run the Colab notebook and extract the bundle files directly into `models/ai-ranker/`.

This pilot can help collect later outcomes, but the existing post-trip rating/comment alone is not a candidate-level training record. Persist the exact candidates shown to each traveler and connect them, with consent and pseudonymous IDs, to selected/booked/completed/cancelled outcomes and reviewed 0–3 human labels. Do not use the bootstrap model's scores or LLM-generated labels as ground truth.

Train the flood model only after building `flood_training.csv` to the documented edge/event schema and obtaining both verified positive and verified negative observations. Open the separate flood notebook; it has no demo mode and will stop when evidence, group counts, or time-split classes are insufficient. It exports the six flood files listed above. This API currently serves predictions but does not use them in routing; verified closures remain an independent hard rule.

## How to build real data

### Ranking candidates and relevance labels

Real POI existence/location and real operational inventory are different facts. OpenStreetMap can provide candidate coordinates/categories/road geometry; it does not prove that a place still exists, offers a hands-on workshop, has a current price, or has an available slot. Preserve OSM object IDs, source URL, fetch time, tags, and license attribution. If redistributing an OSM-derived database, review the ODbL share-alike obligations and display `© OpenStreetMap contributors` with a copyright/license link. See the [OSM copyright and license](https://www.openstreetmap.org/copyright) and [ODbL summary](https://opendatacommons.org/licenses/odbl/summary/).

Use the [HCMC open-data portal](https://data.hochiminhcity.gov.vn/) to search for published city datasets and their access/schema documentation. The portal is a catalog, not a guarantee that live provider slots, workshop prices, or trip outcomes are published. For those, onboard providers and record first-party confirmations (price, duration, slot/capacity, `confirmed_at`, expiry) in the application. The ZIP supplied with the task also contains an OSM POI crawler, an Open-Meteo context collector, and a permission-first official-page crawler; review its allowlist, robots handling, rate limits, licenses, and source fields before using it.

To create labels, log eligible alternatives the system showed for a trip (not just the chosen result), then collect consented actions: selected, booked, completed, canceled, and post-trip feedback. Alternatively, have trained reviewers assign the 0–3 rubric to real candidate records. Store at least `query_id`, candidate/provider IDs, actual query constraints, observed price/slot timestamps, source URL/license, collection timestamp, `label_status`, rubric version, reviewer IDs, and adjudication. Double-label a sample and resolve disagreements. Keep user IDs pseudonymous, avoid exporting names/emails/chat transcripts, and set retention/access rules. Do not use LLM-created grades as ground truth.

Do not scrape Google Maps, booking marketplaces, or social media without an authorized API/license and permission. Do not crawl official provider websites merely because they are public; honor their terms and robots rules. The crawler in the training ZIP intentionally requires an explicit `allowed_to_crawl=YES` entry.

### Flood observations and features

The [HCMC open-data portal](https://data.hochiminhcity.gov.vn/) is the first place to check for data releases and access instructions. HCMC's drainage/flood-response portal is at [thongtinthoatnuoc.tphcm.gov.vn](https://thongtinthoatnuoc.tphcm.gov.vn/); it may require an account and is not automatically an open bulk-download/API. The city research summary on flood warning marks and hydrometeorological/GIS datasets is described by the [HCMC Department of Science and Technology](https://dost.hochiminhcity.gov.vn/hoat-dong-so-khcn/tp-ho-chi-minh-xay-dung-he-thong-moc-canh-bao-ngap-lut-tang-kha-nang-ung-pho-thien-tai-do-thi/); ask the custodian about research access and reuse terms rather than scraping a dashboard.

A public research dataset, [Historical database of urban flooding in Ho Chi Minh City, Vietnam (2002–2026)](https://doi.org/10.23708/8Y16HU), describes 425 geolocated reported observations from 53 sources, with dates, locations, reported depths/causes and geocoding precision. Its page lists a CC BY-NC 4.0 license, so review the non-commercial restriction and citation requirement before reuse. It is useful as a real-event starting point, but reports alone are positive events—not verified no-flood samples for every nearby road/time. Spatially joining those points to OSM roads is approximate and should be reviewed; it still does not supply reliable hourly road-passability labels.

For an explicitly weak-label experiment, `data/experimental/flood_training_weak_labels.csv` labels whether the public source contains a report at a named location-month. Its 0 labels mean only “no matching record in this source,” not “confirmed dry.” It is not compatible with the verified Flood Colab schema or the production flood-risk API; see `data/experimental/README.md` for sampling, exclusions, attribution, and limitations.

If you want to run that limited experiment anyway, open [`notebooks/LocalExplorerAI_Flood_Report_Weak_Label_Experiment_Colab.ipynb`](../notebooks/LocalExplorerAI_Flood_Report_Weak_Label_Experiment_Colab.ipynb) in Colab and upload `data/experimental/flood_training_weak_labels.csv`, or place it at `MyDrive/LocalExplorerAI/dataset/experimental/flood_training_weak_labels.csv`. It exports a research artifact to `MyDrive/LocalExplorerAI/models/flood-report-experiment/`. Do not install it in `models/flood-risk/` or use it to make route-safety decisions.

The provided report-presence artifact is stored in `models/flood-report-experiment/` for reference only. The API does not load or serve this model.

For weather inputs, Open-Meteo's [Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api) archives operational model runs and is designed for forecast evaluation/training; forecasts must be joined by their actual issue time so that no future information leaks into a decision. It is model output, not a street-level rain gauge or flood label. The [Global Flood API](https://open-meteo.com/en/docs/flood-api) is based on GloFAS daily river discharge at roughly 5 km grid scale, so it should not be treated as street-level urban flood truth. Review [Open-Meteo usage terms](https://open-meteo.com/en/terms): free API use is non-commercial, attribution applies, and commercial use requires an appropriate plan.

For a credible street-level classifier, arrange access to time-stamped road/flood observations (e.g. flood depth sensors, verified road closures, or audited reports), plus meaningful observed no-flood periods on the same monitored edges. Join only rainfall/forecast/tide/terrain data known at `decision_time`, record `issued_at`/`received_at`, and retain `event_id` for grouped chronological holdouts. Keep `unknown` and conflicting reports out of supervised labels. A model prediction is advisory; confirmed closure/flood must remain a hard route block.

## Label table contract

| Dataset | Label | Group split | Important source fields |
|---|---|---|---|
| Ranker | `relevance_grade` integer 0–3 | `query_id` (add a time/provider holdout when timestamps exist) | `source_url`, `collected_at`, `label_source`, `reviewer_id`, `rubric_version`, `hard_feasible` |
| Flood | `label_status` = `verified_flood` / `verified_no_flood`; `target_flood` = 1/0 | `event_id`, chronological event order; consider edge/region holdout | `source_id`, `source_url`, `observed_at`, `label_window_end`, `decision_time`, `issued_at`, `received_at`, `spatial_precision`, `provenance_type` |

The ranker notebook uses the fields in the user's current CSV and saves source status in model metadata. Improve the collection schema before claiming real operational learning. The flood notebook implements the separate schema in the supplied flood guide; it explicitly rejects synthetic/heuristic rows and unknown labels.
