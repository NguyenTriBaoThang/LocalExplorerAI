# Experience-ranker benchmark and deployment decision

## Decision

The selected ranker is the versioned deterministic intent/category baseline, `rule-baseline-v1`. The Colab comparison completed for LightGBM and XGBoost, but neither ML candidate beat the baseline on validation NDCG@5. Accordingly, no ML artifact was selected (`selected_model_bundle=null`) and the test set was evaluated only for the selected baseline. The project now serves this rule baseline through FastAPI, planner tie-breaking, and re-plan candidate ranking; it is not described as a trained model.

## Colab results supplied with the project

The run reports 3,828 rows, 638 unique OSM POIs, six analyst-assumed intent contexts, and a POI-disjoint 446/95/97 train/validation/test split. The labels are category-rule-generated grades, not human preferences. Test metrics for the baseline were NDCG@5=1.000 and NDCG@10=1.000 across six assumed contexts. ML test metrics were intentionally not computed because no ML candidate won validation.

| Candidate | Validation NDCG@5 | Validation NDCG@10 | Stability (NDCG@5 SD) | Inference per 128 candidates | Model size |
|---|---:|---:|---:|---:|---:|
| Rule/category baseline | 1.0000 | 1.0000 | 0.0000 | deterministic | 0 bytes |
| LightGBM LambdaRank, depth 2 / 50 trees | 0.9806 | 0.9829 | 0.0000 | 2.195 ms | 26,638 bytes |
| XGBoost best reported configuration | 0.9806 | 0.9623 | see run artifacts | 1.113 ms | 71,668 bytes |

The baseline's perfect scores show that this weak-label experiment reproduces its labeling rule; they do not demonstrate quality for real travelers, new intent types, live experiences, or bookable slots. The current run reports zero human preference labels, zero verified experiences and slots, and no verified planner-feasibility evidence.

## Provenance and reproducibility caveat

The supplied `benchmark_metadata.json` records dataset SHA-256 `0b52faae9729326ba96b7c1438a137c959770d30b277a56db358155c7358260d`. The workspace CSV currently hashes to `0F2A966DD2925862B587CBE7CF96B099525C0D845E3D944209EA4165B1335CD1` (SHA-256); normalizing its line endings to LF also does not match the report. The report says it used 3,828 rows, matching the workspace file's row count, but the exact dataset bytes are not verified. Re-run the benchmark against the committed workspace CSV before treating its metrics as reproducible.

The report's `existing_model_reference` is null, so this run did not compare the old ignored XGBoost artifact on the same split/data. Its historical score from a different, unverified dataset must not be compared directly.

## Review of bootstrap artifacts (2026-10-10)

The supplied `experience_ranker_verified.csv` is **not verified human feedback**, despite its filename. The CSV has 960 rows across 120 generated query contexts, 26 experiences, and 11 POIs. All rows use `label_status=bootstrap_weak_labeled` and `label_method=bootstrap_rule_v1`; `training_eligible=false`, planner feasibility is `NOT_VERIFIED`, slots are `simulated_open`, and estimated operational fields are present. The accompanying audit reports zero human labels, real queries, or real bookings. Its SHA-256 is `a8a0c766db580b64d00ce9923f25481dacfb4aca54362217f184346a86731fb6`.

The benchmark's validation NDCG@5 for XGBoost is approximately 1.0, but the rule baseline scores the same; on test, XGBoost scores 0.9903 while the rule baseline scores 1.0. These scores show imitation of the bootstrap label generator, not predicted traveler satisfaction. The candidate also uses `bootstrap_features_v1` (23 features), which does not match the API's `ranker-features-v2` contract (15 features). The verified trainer correctly rejects this CSV because it does not declare `label_status=verified_human_labeled`.

**Deployment decision: do not install this XGBoost artifact.** Keep `rule-baseline-v1` for cold start and collect reviewed trip outcomes over time. The API remains responsible for hard feasibility checks before ranking. The source CSV and supplied ZIP/notebook remain in the user's Desktop folder; they were not copied into the production model directory or relabeled. Only benchmark facts are recorded here.

For cleanup, the obsolete unverified bundle under `models/ai-ranker/` and the unreferenced root `models/xgb_ranker_v3.json` were removed. `models/ai-ranker/.gitkeep` remains. The separate flood-report experiment was left untouched because it is a distinct research task.

## Runtime and next data needed

`GET /api/ml/status` identifies the active ranker. `POST /api/ml/rank-experiences`, itinerary planning, and re-planning all use the same rule baseline when there is no deployment-eligible ML bundle. Weak-label artifacts remain blocked. Planner checks time, budget, slot/capacity, locked stops, and return routing before ranking; the ranker cannot make an infeasible option eligible.

To train a credible ML ranker, collect consented or human-reviewed query/candidate judgments tied to real POIs, experiences, and slots, with confirmed prices/durations/capacity, planner-feasibility evidence, source timestamps, and reviewer/rubric provenance. Split real judgments by `query_id`; keep label text and IDs out of the feature matrix. Re-run the same baseline/LightGBM/XGBoost comparison, choose by validation NDCG@5, and only then measure test. A future bundle must explicitly declare `dataset_status=verified_human_labeled` and `deployment_eligible=true`; weak labels cannot be promoted by changing a flag.

The complete verified-data path is now implemented in `scripts/train_verified_experience_ranker.py`, with a header-only CSV contract at `data/training/experience_ranker_verified_template.csv` and the Colab runner at `notebooks/LocalExplorerAI_Train_Verified_Ranker_Colab.ipynb`. The trainer refuses the current weak dataset and does not fabricate labels. It exports a deployable native XGBoost/LightGBM ZIP only when the human-label validation gain and untouched-test non-degradation gates pass. No verified human-label dataset was present during this implementation, so no production ML model has been trained or included in the repository yet.
