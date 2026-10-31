# Indicator research attempts

Start with the [research report](../../docs/indicator_research_20261031_report.md)
and [definitions](../../docs/indicator_research_P1_spec.md).

- `IR-20261031-P1-v1`: initial complete 2,160-comparison study, 1,999 bootstrap
  resamples. Retained with source snapshots and the original successful
  development replay/data audit.
- `IR-20261031-P1-v2`: final study, 199,999 resamples after review found a
  numerical-resolution gap. The hypotheses, data, parameter grid and point
  estimates are identical to v1. Additional audit files record the refinement,
  final replay and regressions. No output met the promotion rule.

Run artifacts and source snapshots are research evidence intended for version
control. Derived Parquets live under the existing ignored `data/` tree.
Use new destinations for future attempts; the runner refuses overwrites.
No protected holdout data or OOS token was used.

The [all-50 catalogue report](../../docs/indicator_catalogue_results_20261031.md)
records the subsequent five stages, `IR-20261031-CATALOGUE-B1-v1` through
`IR-20261031-CATALOGUE-B5-v1`. Aggregate progress, final q-values, registries,
audits and regression evidence are in `CATALOGUE-50-20261031/`. All fifty initial
versions were evaluated: 43 reject, 7 revise, none passed the complete
replication rule. The earlier P1 files remain unchanged.
