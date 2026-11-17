# Phase 1 reproduction report

Validation date: 2026-11-17. Source commit:
`639bc9d92886adf83debcbec8219736efa5cae1e`.

The original source-time centered primary ledger was independently reproduced.
No trajectory, checkpoint, raw sensor dataset, or training pipeline was copied
into this repository. Required external primary exports were available locally;
there are **no missing inputs for the completed primary regression**. They are
not bundled here and must be supplied again for a subsequent Level B replay.

| Check | Inputs and calculation | Result |
|---|---|---|
| Level A: archived verification | 360 saved outer-test seed rows; recompute 120 three-seed cells, qualifications, 40 ledger labels and restoration | PASS |
| Level B: independent replay | 30 SHA-256-verified centered outer-test exports; four services and three delivery conditions | PASS, 360 seed measurements |
| Pinned implementation comparison | Newly extracted evaluator vs six verbatim test-oracle functions verified against pinned Git | PASS |
| Per-sequence comparison | Replay fractions averaged over three seeds vs all 120 saved primary cells | PASS |

| Primary ledger quantity | Recomputed archived rows | Independent replay |
|---|---:|---:|
| Sequence-service cases | 40 | 40 |
| Delivery-remediable | 30 | 30 |
| Persistent under tested ideal-available | 6 | 6 |
| Already qualified under degraded | 4 | 4 |
| Practical restorations among remediable | 27/30 | 27/30 |
| Unobservable cases | 0 | 0 |

Degraded/practical/ideal patterns are `000: 6`, `001: 3`, `011: 27`, and
`111: 4`. All other patterns have zero cases. Conditions are fixed-delay,
loss-free 2 Hz/200 ms, 5 Hz/50 ms, and 10 Hz/0 ms. Availability equals source
time for this historical protocol only. Query rate is 10 Hz, with a 30-second
prefix and an additional complete service horizon for local scoring.

Maximum absolute differences:

- Archived seed-to-sequence and ledger fraction recomputation: `2.220446049250313e-16`.
- Replay vs pinned original on compared seed metrics: `0.0`.
- Replay vs archived seed fractions and counts: `0.0`.
- Replay three-seed fractions vs saved sequence cells: `2.220446049250313e-16`.

The tolerance is fixed at absolute `1e-12`, relative zero. Compared original
metrics include physical, freshness, and joint satisfaction, coverage, eligible
and observable counts, mean/max age, and mean/95th-percentile position and
heading discrepancy. Every seed qualification and every sequence qualification
agrees. Tiny aggregate differences reflect floating reduction/CSV representation.
No tolerance was weakened during debugging. A synthetic test's expected count
was corrected from 410 to 400: a gap continuing to the recording end has no
additional ten historical-endpoint queries beyond the recording.

Machine-readable outputs are [archive_report.json](../evidence/validation/archive_report.json),
[replay_report.json](../evidence/validation/replay_report.json),
[per_run_replay.csv](../evidence/validation/per_run_replay.csv), and
[per_case_replay.csv](../evidence/validation/per_case_replay.csv).
The primary ledger is the historical original evaluator's row-level output;
new labels are recomputed from measured fractions, not entered as constants.
Expected aggregate numbers appear only as regression assertions.

Run:

```bash
python -m pytest -q
python scripts/verify_archived_evidence.py --output evidence/validation/archive_report.json
python scripts/replay_original_cases.py --data-root ../DigitalTwinDivergence --output evidence/validation
python scripts/check_source_provenance.py --source-root ../DigitalTwinDivergence
```

`--data-root` is any directory containing the portable paths recorded in
`evidence/minimal_regression_fixtures/trajectory_manifest.json`; the adjacent
repository name is only an example. The replay accepts `--manifest` for an
externally supplied centered bank manifest. It verifies all required hashes,
refuses a different feature protocol, and enumerates missing exports in
`missing_inputs.json` before failing. Acquire frozen exports rather than
retraining Twin V2 to run this regression.

This report covers the primary three-condition ledger, not reproduction of
24,000 nested measurements, predictor fitting, past-only/buffered experiments,
query-phase sensitivity, network captures, or optimization claims. Synthetic
unit-test traces establish edge-case behavior only; none is counted as
historical i2Nav reproduction. Reference quality/uncertainty and availability
remain the responsibility of each future experiment. The author confirms rights
to publish this extraction. Code uses MIT; documentation and evidence use CC BY
4.0, as explained in [source provenance](source_provenance.md).
