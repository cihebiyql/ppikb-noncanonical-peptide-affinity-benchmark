# Data health — reviewed 24 aggregate rows

Rows: 24; selected columns: 13; full source bytes: 14290953.
Selected serialized UTF-8 bytes (not in-memory RSS): 22186.

| Column | Runtime types | Missing | Distinct |
| --- | --- | --- | --- |
| category | str | 0 | 2 |
| dataset_id | str | 0 | 1 |
| panel | str | 0 | 2 |
| method_id | str | 0 | 6 |
| regime | str | 0 | 2 |
| cohort | str | 0 | 1 |
| aggregation | str | 0 | 1 |
| metric | str | 0 | 1 |
| mean | float | 0 | 24 |
| sample_sd | float | 0 | 24 |
| completed_seed_count | int | 0 | 1 |
| defined_seed_count | int | 0 | 1 |
| n_unit | str | 0 | 1 |

Duplicate panel/method/regime coordinates: 0. All 24 required groups present.
Each group has completed=defined=10; n_by_seed is 303 or 332 in the matching panel. Mean and sample SD are finite/nonnegative, retained directly without recalculation.

MAE mean range: 1.2978462195821006 to 1.5729373509695943; sample-SD range: 0.011055515683490856 to 0.14799826014824047.

Normality tests, outlier deletion, numeric-predictor correlation and VIF: not applicable to this descriptive figure of already audited aggregates. No cleaning, fitting, seed selection, significance tests or summary recalculation.
