# Public peptide–protein benchmark: agent entry

This repository contains historical snapshots and additive result updates. Read
[the current four-task index](four-task-20261022/LATEST.md) before interpreting a
result. A snapshot describes its own frozen evidence; it is not a live job monitor.

The v11 completion scope is T3 chemical pKd benchmarking with ordinary affinity
task adaptation. It does not complete all eight originally requested papers or
all four tasks. Historical DTA models remain supplementary comparisons.

- [Current v11 report](four-task-20261022/chemical-benchmarks-complete-v11/README.zh-CN.md)
- [Frozen data and attribution](four-task-20261022/chemical-benchmarks-complete-v11/data/DATA-LICENSE-AND-PROVENANCE.json)
- [Executed scientific source index](four-task-20261022/chemical-benchmarks-complete-v11/source/execution/SOURCE-MAPPING.json)
- [Evaluation and independent-audit source index](four-task-20261022/chemical-benchmarks-complete-v11/source/evaluation/SOURCE-MAPPING.json)
- [Complete logs, predictions and generated-cache assets](four-task-20261022/chemical-benchmarks-complete-v11/RELEASE-ASSETS.json)

## Current v11 publication gate

The v11 snapshot records completed scientific results. Verify public availability
via LATEST and the Release/file verification receipt.
The expanded cohort is531 train/570 validation/685 test; the coverage-control
cohort is497/495/656. Keep their scores and sample counts separate.

Expanded frozen heads have200 selected models from400 validation candidates.
Three chemical encoders' expanded full fine-tuning completed60 candidates and30
validation-selected TEST evaluations, all seeds0–9, with independent raw-prediction
and combined230 audits. The expanded230 models supply157550 TEST rows; the
coverage-control230 supply150880. Keep both actual audits and separate data scopes.

## Tasks, models and comparisons

- The current chemical benchmark predicts pKd. Ki and IC50 remain separate
  endpoints; binary interaction, contact/interface and mutation-effect tasks
  require their own labels and frozen evaluations.
- Three chemical weight variants come from two papers: PeptideCLM-2 Hybrid-small,
  PeptideCLM-2 MLM-small, and PeptideCLM2025. Chiral Morgan is the matched manual
  descriptor reference. These are four representations, not four reproduced papers.
- Chemical identity is retained for the peptide through its complete supplied
  SMILES. Targets remain AA20 reference sequences; this does not automatically
  encode protein-side PTMs or certify the actual experimental construct.
- Frozen heads compare constant, Ridge, random forest, ExtraTrees and HistGB,
  two validation candidates per family and seeds0–9. Full fine-tuning compares
  two learning rates per seed. The test set never selects parameters or epochs.
- Separate standard, non-natural/D/backbone, PTM, mixed and other categories.
  Expanded TEST contains572/45/41/20/7 cases and155 dependency groups. Keep the
  21 annotation-discordance flags and report sensitivity; do not delete by error.
- Do not tune or select retained models from observed TEST rankings. The fixed
  comparison protocol was written after frozen-head results were known and while
  expanded full fine-tuning was incomplete; it is not blind preregistration.

## Frozen data and lineage

Global v3 retains554/579/695 target rows before representation coverage. Source
closure has zero training rows and remains blocked. Two discovered VAL–external
homology links quarantine five standard validation rows; never move them to train.
The expanded1786 rows add138 existing PPIKB observations whose47 valid proteins
were incorrectly skipped by older paired-AA20 preparation. Original cache5159
vectors remain bit-identical; merged cache has5206 vectors. Twelve proteins/42
rows exceed the fixed2048-residue limit and remain excluded with reasons.
All1786 retained rows have target_sequence_scope=
database_reference_not_certified_assay_construct. The experimental protein
construct has not been certified record by record.

The former conditional external6 set is historical. Two2018 points have a
suspected fluorescent-label chemical-identity mismatch; they remain isolated.
The remaining2017 four are diagnostic reference views, not certified gold.
The current independent external-gold count is zero.
New external predictions require the new v3 selected-model and qualification
contracts. No IC50-to-Kd conversion supplies missing labels.

## Files, logs and reproducibility

Use each packet's README, FILE-MANIFEST and SOURCE-MAPPING for exact files and
hashes. Restore self-authored source with the disclosed restoration helper; obtain
third-party source/tokenizers/weights from the pinned official references under
their licenses. Tiny mock/metadata tests are not formal model reproduction.

The exact target-runtime input asset preserves39 original scientific files,
including93/963/e2 cohort manifests,8 feature specs, bindings, receipts, canaries
and five generated feature caches. The explicit execution-only path bridge maps
recorded project positions into the recovered tree without changing original
bytes or SHA guards. Scientific project paths are not credentials. This exception
does not apply to unrelated process data in resource logs: third-party usernames,
commands and device UUIDs are pseudonymized; numeric PID/Unix UID and resource
usage remain as recorded. Use the published official acquisition lock to fetch
upstream assets; do not regenerate original timestamped asset receipts.

Verification levels are separate: original CSV predictions have been numerically
recomputed; original self-authored source, input SHA guards and generated caches
have passed restoration checks. A complete neural retraining from the public
archives on a new machine has not been run. The Path bridge was tested for
metadata/NPZ/guard paths; direct string paths passed to Torch or safetensors were
not thereby tested. IO-local was an unused fallback PREP, not an executed source
change. Large trained checkpoints remain in their recorded storage with SHA
indexes; do not state that all weights were uploaded to GitHub.

All selected per-record predictions, candidate validation/selection metadata,
actual epoch histories and actual failure logs belong to the result delivery.
Four head processes emit four stdout and four stderr files;200 candidates.json
files contain400 candidate records. Do not claim400 separate process stdout files.
Large checkpoints may remain indexed by original production
hashes; never claim a fresh byte verification unless it was actually performed.

PPIKB v5 data are CC BY4.0: [official source](https://doi.org/10.6084/m9.figshare.31082407.v5),
[local attribution and policy](permissions/policy.json). Original licensed GT and
prediction CSV bytes may be shared with attribution. Third-party source/PDF/
weights do not inherit that license. Public copies remove private paths and
credentials with source→public hash mappings. Preserve failed and adverse results.

## Editing this repository

Add new versioned packets; leave historical snapshot bytes unchanged. Keep
repository-relative links portable. Do not put private hosts, SSH configuration,
credentials, upstream weights or unlicensed full papers into Git. Record actual
scientific completion, local delivery and public publication separately. Consult
the corresponding active private compute owner before launching new resource jobs;
this public document grants no cluster lease or permission to terminate jobs.
