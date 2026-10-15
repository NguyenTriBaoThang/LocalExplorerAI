# Model artifacts

This directory stores model files and metadata. The presence of an artifact in Git does not mean that the API has selected it or that it is production-approved.

## Current status

- ai-ranker/: contains an XGBoost bootstrap ranker and its evaluation metadata. Its labels are weak/bootstrap labels. The API defaults to rule-baseline-v1; the bootstrap artifact is not production-eligible and requires the explicitly documented opt-in to test.
- e5/: contains a placeholder only; model weights are not included.
- flood-risk/: contains a placeholder only; no road-flood model trained on suitable, verified observations is included.
- flood-report-experiment/: contains a separate experimental classifier about historical public-report presence. It is not a physical flood or road-passability model.

## Promotion policy

Before promoting any model, review its model card, dataset provenance, feature schema, preprocessing, checksum, data split, and metrics. A production experience ranker requires reviewed labels from real outcomes, query-disjoint evaluation, a fair comparison against the baseline, and explicit approval. A ranker only orders candidates that have already passed the planner's hard feasibility checks.

See the [ranker benchmark](../docs/experience-ranker-benchmark.md), [ML training and data guide](../docs/ml-training-and-data.md), and [model versioning policy](../MODEL_VERSIONING.md).
