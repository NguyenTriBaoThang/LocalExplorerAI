# Model artifacts

This directory stores model artifacts and metadata. The presence of an artifact in Git does not mean that the API accepts it or that it has been evaluated for production.

## Current status

- ai-ranker/: contains a bootstrap XGBoost ranker and its metadata. Its labels are weak/bootstrap labels. The API uses the rule baseline by default and blocks models that do not meet the deployment gate. Do not promote this artifact as a production model.
- e5/: currently contains only a placeholder; the model weights are not in the repository.
- flood-risk/: currently contains only a placeholder; no road-flood prediction model has been trained with suitable observed labels.
- The flood-report experiment, if present, is under data/experimental/. It is a separate task and is not a flood-risk model.

## Promotion principles

Review the model card, dataset provenance, schema, preprocessing, checksum, split, and metrics. A production ranking model requires appropriate labels, query-disjoint evaluation, a fair comparison with the baseline, and explicit approval. Every model may only rank candidates that have passed the planner's hard feasibility checks.

See the [ranker benchmark](../docs/experience-ranker-benchmark.md), [training guide](../docs/ml-training-and-data.md), and [model versioning](../MODEL_VERSIONING.md).
