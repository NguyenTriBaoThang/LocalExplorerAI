# ML training and FastAPI model bundles

## Two separate models

Local Explorer AI has two distinct supervised-learning tasks. Do not combine their CSVs or metrics:

| Task | Input labels/data | Output | Colab notebook |
|---|---|---|---|
| Replacement-experience ranker (human labels) | `query_id`, planner-feasible candidates, human relevance grades 0–3 | Relative candidate order (`rank_score`) | `notebooks/LocalExplorerAI_Ranking_Training_Colab.ipynb` |
| Ranking weak-label benchmark (experiment only) | Six assumed intents and category-rule grades on OSM POIs | Baseline/LightGBM/XGBoost comparison; never production-ready | `notebooks/LocalExplorerAI_Ranking_Benchmark_Colab.ipynb` |
| Flood-risk classifier | Road-edge/time samples with verified flood and verified no-flood labels | Calibrated probability estimate for a road segment/time/horizon | `notebooks/LocalExplorerAI_Flood_Training_Colab.ipynb` |

## Experience ranker benchmark and current model

The repository's current ranker is an optional `XGBRanker(objective="rank:ndcg")` bundle. Its metadata identifies `local-explorer-ranker-v1-20261003T014631Z`, trained from the older `data/dataset_ranking_tphcm.csv` with `dataset_status=unverified_user_dataset`. Its stored NDCG@5 of 0.9516 was measured on 34 held-out queries from that older source. Do not compare that number directly to the new POI-held-out experiment: source, labels, candidate coverage, and split unit differ.

The supplied `LocalExplorerAI_Weak_Ranking_Model.zip` contains a `RandomForestRegressor` weak-label prototype, not an XGBoost/LightGBM learning-to-rank model. Its NDCG@10=1.0 and MAE≈0.0036 are agreement with the category-rule labels only. Its `joblib` file is not loaded by this project; deserializing untrusted joblib/pickle files can execute code.

The new dataset is stored under `data/experimental/ranking/`. It has 638 OSM POIs crossed with six analyst-assumed intents, not real queries. The category-rule labels are weak. Price, duration, ETA, and some indoor values are estimates; hands-on status is unknown, and activity/slot/planner verification is absent. See the folder README for license and field-level provenance. Only the explicit `--mode weak_label` run accepts it, and the output metadata always says `deployment_eligible=false`.

`scripts/train_experience_ranker.py` compares the tag/category rule baseline, LightGBM LambdaRank, and XGBoost NDCG ranking with the same shared v2 API feature function, four configurations per algorithm, and a deterministic POI-disjoint 70/15/15 split. It selects by validation NDCG@5. NDCG@10, latency, model size, and three-seed validation stability are supporting checks. It reads the test split only after selection. A weak-data model is exported only if it exceeds baseline validation NDCG@5 by at least 0.01; otherwise the rule baseline is selected and no new ML artifact is created. The test output is therefore not a real-world quality claim.

Run the complete comparison in Google Colab using `notebooks/LocalExplorerAI_Ranking_Benchmark_Colab.ipynb`, or install `apps/api/requirements-ranking-training.txt` and run the script locally. The full run requires both LightGBM and XGBoost. CatBoost is not included because the present shared feature matrix is numeric, the dataset has only six assumed contexts, and its target is a deterministic category rule; another learner cannot supply missing human labels.

The ranker adapter accepts native XGBoost JSON or LightGBM text bundles and preserves the v1 feature contract for the existing XGBoost artifact. The new v2 builder represents unknown hands-on/indoor facts as missing with explicit known flags. Production remains fail-closed for every dataset status other than verified human labels; `weak_label_experiment` is non-deployable even when an unverified-model override is set. The itinerary planner and replanner continue to check route/time/budget/capacity/locked-stop rules first; the model only scores the remaining candidates. If no artifact loads, deterministic ranking remains in effect.

See [the initial benchmark report](experience-ranker-benchmark.md) for local results and the missing LightGBM run.

The supplied `dataset_ranking_tphcm.csv` has 877 rows and 170 query groups. It includes 639 rows marked `hard_feasible=1` and 238 rows marked infeasible; all 238 infeasible rows have grade 0. Among feasible rows, grades are 0: 69, 1: 170, 2: 199, 3: 201. The file has no source URL, collection timestamp, reviewer ID, label-method, or provenance field. Its origin/label process therefore cannot be verified from the file alone. The new notebook marks the resulting bundle `unverified_user_dataset`; it does not create synthetic rows. Treat its metric as a pipeline check, not evidence of real-world ranking quality.

The supplied flood notebook is not compatible with that ranking CSV. Flood training also requires independently verified negative observations; missing flood reports cannot be relabeled as no-flood. The new flood notebook has no simulated-data fallback and refuses simulated/heuristic rows.

## Public HCMC flood reports (raw, not training-ready)

`data/raw/hcmc_flood_reports_2002_2026.csv` is a CSV conversion of the 425-row, 22-column `Flood_event_locations.tab` published in DataSuds (Hardy & Radziute, 2026, [DOI 10.23708/8Y16HU](https://doi.org/10.23708/8Y16HU)). `data/raw/flood_training.csv` is a duplicate with the exact requested filename, **not a training-ready dataset**. The source compiles reported observations from 53 sources; 63 rows have no exact `Date` value in the downloaded table. The source file checksum is verified by `scripts/download_hcmc_flood_reports.py`; run that script to download and convert the original file again.

This is real historical event-report data, but it is **not** the Flood notebook's `flood_training.csv`: it has no independently observed no-flood windows, no project `edge_id`, and insufficient exact timestamps for the required decision-time/horizon labels. Do not create those values by inference from absent reports. The source is licensed CC BY-NC 4.0; cite the dataset and check the non-commercial restriction before redistribution or commercial use. See `data/raw/README.md` for attribution and limitations.

The strongest local candidate for richer, real event data is HCMC's Flood Data Exchange System (FEDS). A [World Bank implementation note](https://documents1.worldbank.org/curated/en/099052625225018333/pdf/P176260-dffa6f4e-18b1-412f-ab75-4e4dfe34167d.pdf) describes field-officer flood point/segment reports, WebGIS manager exports, and 954 reports submitted by April 2025 after a July 2024 restart. The note does not publish the underlying records as a public download; request an authorized export from the city data custodian. Confirm whether the export includes verified no-flood status observations and full observation coverage—flood reports alone still cannot train this binary classifier. The [public SCFC alert map](https://chongngap.hochiminhcity.gov.vn/baongap/) shows current flood/rain/tide/camera/report layers, but is not evidence of a downloadable historical training archive.

## FastAPI endpoints

- `GET /api/ml/status` — reports which local model bundles are present and their version/provenance state.
- `POST /api/ml/rank-experiences` — ranks replacement candidates with a compatible local XGBoost or LightGBM ranker. It filters `hard_feasible=false`, over-budget candidates, and candidates where `eta_min + duration_min > remaining_time_min`. Pass the exact group price, time budget, and current weather only when known. The score is not a probability.
- `POST /api/ml/flood-risk` — batch flood-risk inference using the flood bundle. A predicted risk is not a verified flood report or road closure and must never override a hard block. Unknown observations remain unknown.

Flood inference returns `risk_state=unknown` when `coverage_ratio` is absent; a low model probability alone is not evidence that a road is clear. The caller must supply a meaningful coverage measurement from the data pipeline.

The ranker is used by the normal itinerary planner only as a tie-break among candidates at the earliest feasible time; hard filters for budget, return deadline, slot, capacity, and locked experiences remain authoritative. It is also used by `ReplanningService` after its database checks. If no ranker bundle is present or the model fails to load, both flows retain their deterministic heuristics; `/api/ml/status` reports the model state. Its current dataset remains unverified, so production blocks it by default.

## Exact artifact placement

On the project host, unzip/copy the Colab ranker files here:

```text
models/ai-ranker/
  local_explorer_ranker.json
  model_metadata.json
  feature_schema.json
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

For production (`APP_ENV=production`), the ranker requires metadata `dataset_status=verified_human_labeled`; otherwise it refuses to load unless `ALLOW_UNVERIFIED_RANKER=true` is set explicitly. The Colab output from the current CSV stays unverified by default. Do not change the metadata flag merely to bypass this safeguard.

Only load joblib artifacts created by your own trusted Colab run. Python joblib/pickle files can execute code when deserialized.

## Train the ranker in Colab

1. Upload `dataset_ranking_tphcm.csv` to Google Drive at `MyDrive/LocalExplorerAI/dataset/training/` (or change `DATA_PATH` in the notebook).
2. Open `notebooks/LocalExplorerAI_Ranking_Training_Colab.ipynb` in Google Colab and run cells in order.
3. Inspect the feasibility-by-grade counts and test NDCG@5/Recall@5/Top1/MRR against the tag-overlap baseline. Do not report these as real-world quality unless the underlying labels and records have been sourced and audited.
4. Download `local_explorer_ranker_bundle.zip`, unzip it, and copy its three files to `models/ai-ranker/`.
5. Set `INSTALL_ML=true`, rebuild/restart the API, and check `GET /api/ml/status`.

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
