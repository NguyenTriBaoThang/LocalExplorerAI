# LocalExplorerAI bootstrap ranker (experimental)

- Mode: `bootstrap_pilot`
- Dataset status: `bootstrap_weak_labeled`
- Selected runtime by validation NDCG@5: `bootstrap_xgboost_pilot`
- Validation NDCG@5: XGBoost `1.0000`; rule baseline `0.5717`
- Test NDCG@5 (read after validation selection): XGBoost `0.6667`; rule baseline `0.4932`
- POIs: 11; queries: 120; scenario families: 60

## Limitations

The labels come from deterministic `bootstrap_rule_v1`, not travelers. Scenario, ETA, slot, and capacity inputs include synthetic/estimated values; no candidate is operationally verified by this CSV. This benchmark measures imitation of the bootstrap labeling process only. The family split prevents related scenario variants crossing splits, but POIs repeat between splits and this small sample does not establish generalization to new places, users, or intents. The feature allowlist excludes IDs, labels/rationales, and provenance.

This artifact is explicitly **not production eligible**. The API accepts it only when `ENABLE_BOOTSTRAP_RANKER=true` and reports a warning; production eligibility and deployment eligibility remain false. The planner must continue to enforce hard time, budget, availability, capacity, locked-stop, and route constraints before scoring.

## Next data collection

Log the alternatives actually shown, planner decisions, booking/completion/cancellation outcomes, consented post-trip feedback, and reviewed human grades. Replace weak labels only with adjudicated evidence; do not promote by editing metadata.
