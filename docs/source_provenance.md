# Source provenance

The original repository is `DigitalTwinDivergence`, associated with *Digital Twin
Fidelity for Networked IoT Services*. The exact extraction commit is
`639bc9d92886adf83debcbec8219736efa5cae1e`.

The source working tree contained a modified `manuscript/main.tex`. No source
files were changed. All copied numerical oracle functions were read with
`git show <commit>:<path>`, not taken from an unpinned working tree. The inspected
numerical modules and reproducibility notes match the pinned commit. The
working/pinned manuscript hashes differ and are recorded in
[source_hashes.json](source_hashes.json); module/document hashes there normalize
text to UTF-8/LF. Evidence and trajectory hashes use raw bytes. Original bank
generation provenance lists commit `8a363b0446f9fd2353993e794cd3672fe29c86b6`;
this is distinct from the evaluator extraction commit.

The authoritative primary route is:

1. `docs/paper_submission.md` identifies `manuscript/main.tex` as the claims
   source and `service_evidence_from_bank.py` as the receiver evidence driver.
2. `service_evidence_from_bank.build_nested_tables` calls
   `service_timing_budget_study.response_rows` per outer fold. The primary
   ledger uses only entries where outer recording equals test recording.
3. `service_timing_budget_study.evaluate`, `delivered_indices`, `relative`, and
   `wrap` implement the scored discrepancies, freshness, and reconstruction.
   `sequence_rows` averages each fraction over the three seeds **before**
   qualification. It does not average binary seed qualification decisions.
4. `_remediability` delegates to `service_timing_budget_study.remediability`.
   The archived primary evidence is `results/doubly_nested_loso_evidence/`,
   backed by `results/doubly_nested_loso_slurm/merged_manifest.json`.
5. `scripts/audit_review_evidence.py` checks saved seed aggregation and
   degraded/practical/ideal pass patterns. The source-time centered primary
   conditions are 2 Hz/200 ms, 5 Hz/50 ms, and 10 Hz/0 ms.

`deterministic_delivery_replay.sampled_delivery` supplies the arrival-order,
newest-source handling for a separate jitter/loss experiment. Its floating
comparison allowance and stochastic conditions are not the primary ledger
protocol. This extraction uses the primary integer-nanosecond clock and a
deterministic arrival-order reconstruction accepting external packet histories.
`delivery_feasibility.passes/replay` corroborate the same SE(2) discrepancy,
but its arrival-block schedules, bounded-age search, MILP optimizer, and plotting
are outside Phase 1. The original ordinary-LOSO discovery path and older
standalone timing diagnostics are not substitutes for the nested outer-test bank.
Past-only and buffered-centered screening use different availability/training
protocols and are not mixed into the primary regression.

The pinned original tests inspected include `test_service_timing_budget_study`,
`test_review_reference_mask`, `test_buffered_centered_heldout`, and the delivery
and timing reviewer tests. The extracted suite retains native-clock boundary
comparisons and the reference-mask endpoint checks without their heavy imports.

## Deliberate adaptations

The manuscript and supplementary reproducibility protocol resolve these cases:

- The primary evaluator represents no observable satisfaction as zero through a
  guarded denominator. The manuscript explicitly makes it undefined, and
  `scripts/build_review_revision_20261109.reference_mask_evaluation` implements
  NaN with an unobservable outcome. The new API follows that evidence rule.
- Primary trajectory files are fully observable. The new API adds explicit
  validity and named evidence masks, checks finite required fields, and requires
  both reference and receiver endpoints for local motion. No missing reference
  is filled or counted as a physical failure.
- The old `remediability` helper tests ideal failure before degraded success,
  contrary to the manuscript's explicit precedence. The new API gives degraded
  qualification precedence, because more frequent updates need not improve
  physical accuracy. This changes the nonmonotonic synthetic edge case and
  changes **zero** historical case labels. The old `unresolved` missing-evidence
  label becomes `unobservable`, reported separately, as the manuscript requires.
- Source availability is explicit. Arrival cannot precede availability or
  source time. Subsampling selects the original source states; added availability
  and transmission delays never modify their timestamps or values.
- `horizon_steps` preserves the primary index-based horizon/prefix convention.
  The general API additionally supports exact timestamp-based horizons on other
  clocks, with missing endpoints marked unavailable. Historical replay always
  selects the former convention. No reference alignment or interpolation occurs.
- Pose fields are generic east/north/heading names. Discrepancy callbacks allow
  other physical processes without importing i2Nav or modifying the core.

The [extraction manifest](extraction_manifest.json) maps original functions to
destinations. The small verbatim oracle is confined to tests and excluded from
the wheel. `check_source_provenance.py` verifies its function ASTs against the
pinned Git objects, checks original table hashes, and verifies portable fixture
hashes. Runtime modules have no dependency on the old repository or the oracle.

## Scope and rights

Before extraction, repository-root license files and tracked license/copyright
paths were checked. No repository-wide license or grant was found. Numerical
modules carry no additional copyright/license notices. The only tracked
`LICENSE` is in the unrelated `ugv01_gps_dev` subtree, which was not copied.
The author confirms they created the code and have rights to publish the
extracted code and evidence in this repository. Python source is MIT licensed;
documentation, configuration, and evidence are CC BY 4.0. Scope is recorded in
[LICENSE](../LICENSE), [LICENSE-CC-BY-4.0](../LICENSE-CC-BY-4.0), and
[NOTICE](../NOTICE).

Copied evidence is restricted to the three primary delivery points: 360 seed
rows, 120 sequence cells, 40 ledger cases, a sanitized evidence manifest, and
30 outer-test trajectory identities/hashes. Unneeded features, calibration
columns, source paths in response tables, development folds, other delivery
settings, and manuscript assets are omitted. The trajectory manifest keeps
portable repository-relative paths needed for future replay. Manifest summary
totals are cross-checks, never the source of recomputed results.

Excluded: trajectory CSVs, raw sensors, checkpoints, model/training code,
firmware, dashboards, neural libraries, optimization, screening, bootstrap and
plotting suites, manuscript sources/figures, and unrelated utilities. No source
trajectory was retrained or changed.
