# All-50 catalogue evidence

Read the [results report](../../../docs/indicator_catalogue_results_20261031.md)
and [validation contract](../../../docs/indicator_catalogue_validation_spec_20261031.md).

- `idea_progress.csv`, `feature_registry.yml`: all 50 implemented definitions,
  controls, targets, support, decisions and evidence links.
- `comparisons_final.csv`: all 2,250 catalogue comparisons with final global
  q-values. Earlier batch files retain their interim q-values.
- `adjusted_findings.csv`: every one of the 22 adjusted catalogue findings.
- `numerical_audit.json`, `validation_audit.json`: independent estimates and
  decisions, then full five-batch replay evidence.
- `numerical_verification_source.py`, `verification_source.py`: exact verifier
  source bytes identified by the respective audit SHA-256 values.
- `session_dst_audit.json`: synthetic-timestamp reproduction of the old DST
  boundary problem and corrected grouping.
- `regression_checks.json`, `test_sources/`: software-regression counts and
  exact sources of the 34 new tests.
- `manifest.yml`: aggregate artifact/document hashes and five parent manifests.

Final result: 43 reject, 7 revise, zero retained under the full replication
rule. All output/data replays are byte-identical; no protected holdout rows or
OOS token were used. Existing Gold files were not rebuilt.
