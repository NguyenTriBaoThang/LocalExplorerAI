# LocalExplorerAI experience-ranker benchmark

This is a weak-label pipeline experiment, not a real-user quality evaluation.

- Dataset SHA-256: `0b52faae9729326ba96b7c1438a137c959770d30b277a56db358155c7358260d`
- Rows / POIs / query contexts: 3828 / 638 / 6
- Split: POI-disjoint; counts `{'train': 446, 'validation': 95, 'test': 97}`; no duplicated query contexts added.
- Selected by validation NDCG@5: `rule_baseline`.
- Deployment eligible: `false`.

## Validation comparison

| Model/config | NDCG@5 | NDCG@10 | Latency ms / 128 | Model bytes |
|---|---:|---:|---:|---:|
| lightgbm / {"max_depth": 2, "n_estimators": 50} | 0.9806 | 0.9829 | 2.1949 | 26638 |
| lightgbm / {"max_depth": 2, "n_estimators": 100} | 0.9806 | 0.9829 | 2.5667 | 50329 |
| lightgbm / {"max_depth": 3, "n_estimators": 100} | 0.9806 | 0.9824 | 2.4607 | 63578 |
| lightgbm / {"max_depth": 3, "n_estimators": 50} | 0.9806 | 0.9717 | 2.5691 | 30585 |
| rule_baseline / tags/category only | 1.0000 | 1.0000 | 0.0000 | 0 |
| xgboost / {"max_depth": 3, "n_estimators": 100} | 0.9806 | 0.9623 | 1.1126 | 71668 |
| xgboost / {"max_depth": 2, "n_estimators": 100} | 0.8690 | 0.9274 | 1.1131 | 66244 |
| xgboost / {"max_depth": 3, "n_estimators": 50} | 0.8383 | 0.8163 | 1.0600 | 35675 |
| xgboost / {"max_depth": 2, "n_estimators": 50} | 0.7381 | 0.7656 | 1.0459 | 33651 |

## Limits

- The 0/2/3 grades are rule-generated, not human preference labels.
- The six query contexts are analyst assumptions; results do not generalize to new intents.
- POIs are real OSM records but operational status is unverified; experience and slot IDs are absent.
- Duration, ETA, price, indoor state, and relevance grade are estimated or rule-derived as listed in estimated_columns.
- Metrics measure imitation of the category rule only and are not real recommendation quality.

A model bundle is emitted only if the selected ML candidate beats the tag/category rule baseline by at least 0.01 validation NDCG@5. Weak-label bundles are never marked deployment eligible.
