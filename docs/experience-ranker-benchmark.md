# Experience-ranker benchmark: initial weak-label run

## Decision

The selected reference is the deterministic tag/category baseline. No new ML artifact was emitted or promoted. On the six held-out intent contexts, the baseline reached validation NDCG@5=1.000 and NDCG@10=1.000, then test NDCG@5=1.000 and NDCG@10=1.000. This is expected because the CSV's relevance grades were generated from a closely matching category rule. These scores measure reproduction of that rule, not recommendation quality for travelers.

## Local diagnostic

The local environment had XGBoost 3.1.3, but no LightGBM; connecting to PyPI to add LightGBM timed out. The full, fair LightGBM-versus-XGBoost comparison therefore remains to be run in Colab. The run below is explicitly partial and is not a final model selection between the requested rankers.

| Candidate | Validation NDCG@5 | Validation NDCG@10 | Stability across three seeds (NDCG@5 SD) | Median inference for 128 rows | Native model size |
|---|---:|---:|---:|---:|---:|
| Rule/category baseline | 1.0000 | 1.0000 | 0.0000 | deterministic rule; no model artifact | 0 bytes |
| XGBoost Ranker, depth 2, 100 trees | 0.9806 | 0.9709 | 0.0485 | 1.78 ms | 66,258 bytes |

The XGBoost test set was not evaluated because the baseline won validation and the configured selection rule requires a 0.01 NDCG@5 improvement before any ML candidate can be selected. Only the selected baseline was measured on test. The POI split was 446 train, 95 validation, and 97 test POIs; all six assumed contexts appeared in each split. No POI crossed a split.

## Compared with existing artifacts

The current repository bundle is an XGBoost ranker trained on the different 877-row `dataset_ranking_tphcm.csv`; its stored NDCG@5=0.9516 comes from 34 held-out query groups on that older, unverified source. That number is not a same-data comparison. The user-supplied weak-model ZIP reports NDCG@10=1.0 for a `RandomForestRegressor` against the category-rule labels. It is also not directly comparable to this LambdaMART/NDCG benchmark. Its joblib file was not deserialized.

## What remains

Run `notebooks/LocalExplorerAI_Ranking_Benchmark_Colab.ipynb` after pushing the repository changes so Colab can clone the training code and CSV. It will install both ranker libraries, compare four configurations per algorithm under the same POI split and feature builder, select using validation NDCG@5, then inspect test only for the selected model. The baseline is already at the NDCG@5 ceiling on validation; an ML model cannot be justified by this weak-label benchmark unless the full validation run exposes a material data/implementation discrepancy.

Before using ML ranking for real trips, collect consented or human-reviewed query/candidate judgments with real experience and slot IDs, confirmed price/duration/capacity, planner feasibility evidence, source timestamps, and reviewer/rubric provenance. Split those examples by `query_id`. Keep the current weak-label files and artifacts out of production.
