# Weak-label experiment for experience ranking

## Dataset

ranking_candidates_labeled.csv contains 3,828 rows: 638 OSM candidate places crossed with six assumed intent profiles. Labels are rule-generated categories/scores, not real customer ratings. Some prices, durations, and ETAs are estimated; see estimation_parameters.json and source_audit.json.

There is no evidence of actual slots, capacity, planner decisions, or verified operating status. Do not duplicate queries to inflate the sample. POIs are kept separate between splits, but this evaluation does not measure generalization to new intents.

## Existing benchmark

The colab-results/ directory stores the supplied metadata, metrics, feature schema, preprocessing, model card, test predictions, and validation comparison. Interpret them only as a weak-label benchmark; do not use these metrics to claim recommendation quality for real users.

The API's default ranking method is the rule baseline. The bootstrap artifact is not production-eligible. Use the [benchmark guide](../../../docs/experience-ranker-benchmark.md) to reproduce the experiment and record dependency versions and hashes.
