# DATA_ngay17 offline model experiments

**Status: synthetic experiment only. Not production eligible.**

Offline experiment only. The supplied generator creates simulated impressions, synthetic flood labels, placeholder evidence URLs, and fabricated verification metadata. Metrics measure imitation of that generator, not real user preference, real flood risk, or operational readiness. Do not deploy or use for decisions.

## Ranker

- Algorithm: LightGBM LambdaMART.
- Split: held-out `request_id` groups; only viewable impressions; `position` excluded as a feature.
- Test NDCG@5: model `0.2852`, rule baseline `0.3078`.
- Input mapping: uses the project's `ranker-features-v2` builder. Missing ETA, remaining time, weather and AQI remain missing.
- Labels: simulated clicks, saves and bookings from `generate_datasets.py`, not real behavior.

## Flood risk

- Algorithm: scikit-learn HistGradientBoostingClassifier.
- Split: held-out `group_id` groups.
- Test Average Precision: `1.0000`; Brier: `0.0001`; recall at 0.40: `1.0000`.
- The generator defines the label using a hard-coded score made from these same weather/terrain predictors. The evidence URLs and `verified_*` status are generated placeholders.
- The data schema is not the production Flood API schema.

## Runtime gate

The ranker metadata sets `deployment_eligible=false` and `pilot_runtime_eligible=false`. The flood metadata sets `demo_mode=true` and `deployment_eligible=false`. The application's existing services must refuse both artifacts. Keep the rule-based ranker and existing flood behavior active.

## Files

- `ranker/ranker_model.pkl`, `ranker/ranker_model.txt`, `ranker/model_metadata.json`, `ranker/feature_schema.json`, `ranker/ranker_metrics.json`
- `flood-risk/flood_model.pkl`, `flood-risk/model.joblib`, `flood-risk/preprocessor.joblib`, `flood-risk/metadata.json`, `flood-risk/feature_schema.json`, `flood-risk/calibration.json`, `flood-risk/threshold.json`, `flood-risk/flood_metrics.json`
- `experiment_report.json`, `MODEL_CARD.md`

## Promotion requirements

Replace these simulations with consented, real impression outcomes and audited source-backed flood observations; align flood features to the API contract; use time and spatially separated evaluation; independently review provenance, calibration, thresholds, and model card. Do not promote by changing metadata flags.
