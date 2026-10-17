# Behavior ranker experiment

This bundle contains the XGBoost artifact copied from `D:\Downloads\TrainModel_AI`.
It is registered as a **local-only experiment** and is separate from the active
planner ranker.

## Data and evaluation caveat

The source pipeline generates synthetic users, candidate lists, and interactions.
Its reported XGBoost `NDCG@5` is 0.8716 versus 0.8288 for its synthetic heuristic
baseline, but this is not evidence of performance on LocalExplorerAI users. The
synthetic generator also supplies the labels and some matching features, so the
comparison is useful for checking the training/inference path only. Consent
fields in that generated dataset are simulated and are not real-user consent.

Do not use this artifact in production or present its scores as probabilities.
The API refuses to serve it outside `development`/`test`; Explore requires the
signed-in traveler to enable personal recommendations. Inference only reranks
the candidate IDs already returned by the existing catalog filters.

## Bundle

- `xgb_ranker.json`: trained XGBoost ranker.
- `model_metadata.json`: source evaluation results and non-deployable marker.
- `feature_schema.json`: exact 17-feature contract used by the API adapter.

The runtime needs the optional ML dependencies in `apps/api/requirements-ml.txt`.
