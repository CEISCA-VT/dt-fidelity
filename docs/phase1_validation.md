# Phase 1 validation

Assessment: **PASS** for all ten definition-of-done items. Validation ran on
Windows with Python 3.13.3, NumPy 2.5.5, and pytest 9.2.0. Linux installation
commands are documented but were not executed on this Windows host.

| # | Definition of done | Assessment | Evidence |
|---|---|---|---|
| 1 | Minimal package installs | PASS | Editable install, built wheel, separate wheel install, dependency check |
| 2 | External trajectories/delivery histories | PASS | Public example; pose and custom thermal callback tests; external arrival histories |
| 3 | Original qualification semantics | PASS | 80 service/rate/delay oracle comparisons, threshold tests, explicit native-clock horizons, documented manuscript resolutions |
| 4 | Three outcomes | PASS | Qualified, unqualified, unobservable; undefined satisfaction when no evidence |
| 5 | Receiver and remediability | PASS | Ordering, duplicates, losses, source availability vs transmission, causality, frozen paired histories, label precedence |
| 6 | Regression suite | PASS | 106 tests pass both editable package and installed wheel; zero remaining failures |
| 7 | Archived evidence independently checked | PASS | Read original full saved tables and portable subset; recompute 360 seed rows into 120 cells and 40 ledger cases |
| 8 | Available trajectories replayed | PASS | All 30 required primary outer-test exports verified by SHA-256 and replayed; 360 per-run results compared |
| 9 | Runs without importing old repository | PASS | Wheel loaded from separate site-packages under isolated Python; runtime imports exclude DigitalTwin, pandas, sklearn, torch; all tests use bundled oracle |
| 10 | Provenance/reproduction documented | PASS | Exact commit and hashes, function map, extraction/rights notice, row-level outputs and report |

No missing external inputs prevented primary replay. Frozen trajectory files
remain external and are deliberately omitted from this repository. For reruns
they must be supplied at the paths in the bundled trajectory manifest. No
training, source-state alteration, or Phase 2 security work was performed.

Runtime: **296 Python lines**, across five modules. Reproduction/example/audit
scripts: **303 lines**, across four files. Total production Python: **599 physical
lines**, including docstrings, comments, and blank lines; excluding tests,
test-only oracle, generated build copies, and virtual environments. See
[file inventory](file_inventory.md).

## Required regression coverage

| Requested test | Implemented evidence |
|---|---|
| 1. Legitimate expected result | Perfect motion, including degraded delivery; runnable example |
| 2. Identical states have zero discrepancy | Exact vector comparison at ideal delivery |
| 3. Inaccurate fresh source fails | Global offset, fresh, unqualified; pinned original comparison |
| 4. Accurate stale source fails | Constant trajectory with two-second delay; pinned original comparison |
| 5. Out-of-order arrivals cannot replace newer state | Explicit shuffled/duplicate delivery history and newest-source expected indices |
| 6. Availability distinct from transmission | 100-ms availability plus 100-ms transmission; original index comparison and pre-availability rejection |
| 7. Insufficient missing evidence | Reference gaps, source-valid mask, absent named evidence, no reference |
| 8. Observable satisfaction denominator | Thermal example: 3/5 observable, 2/3 satisfying; missing evidence kept out of satisfaction |
| 9. Local frame and heading wrap | Direct original relative/wrap comparison, rigid frame transformation, all four contracts |
| 10. Inclusive thresholds | Position tolerance and next representable float, age boundary/one nanosecond beyond, eta/gamma boundaries and joint-only failure |
| 11. Remediability | All historical labels rederived from fractions; observable label branches and manuscript nonmonotonic precedence |
| 12. Original fixtures | 360 seed rows, 120 cells, 40 cases, primary pattern/restoration assertions |

Additional tests cover timestamp jitter, exact timestamp history gaps on general
clocks, invalid inputs, short/empty trajectories, and fixture/oracle hashes.
The original oracle is verbatim at the pinned commit and its ASTs are checked
with `scripts/check_source_provenance.py`. Tests for newly introduced interfaces
use explicit expected values; there is no original general-purpose callback or
availability object to import. The three documented semantic resolutions
(empty satisfaction, missing evidence, ledger precedence) follow the manuscript
and reference-mask implementation rather than preserving conflicting helper
behavior. They do not change any primary historical measurement or label.

## Executed checks

```text
editable installation: PASS
pytest against editable package: 106 passed
pytest against independently installed wheel: 106 passed
isolated wheel example: qualified, joint=1.0, observability=0.9900990099009901
wheel dependency check: No broken requirements found
compileall src scripts tests: PASS
archived audit of original full tables: PASS
archived audit of portable subsets: PASS
pinned provenance: 9 files, 6 verbatim oracle functions, PASS
independent trajectory replay: 30 exports, 360 seed measurements, PASS
```

The numerical results and precise scope are in
[reproduction_report.md](reproduction_report.md). Stored machine-readable
reports contain maximum numerical differences and trajectory hashes.

Rights are a remaining distribution limitation: no applicable source license
was found; no new redistribution grant has been asserted. See [NOTICE](../NOTICE).
Phase 1 validates a local research foundation, not a security guarantee or a
claim about reference accuracy. General timestamp mode does not interpolate
reference gaps. Callers must supply evidence masks and discrepancies appropriate
to their process; the evaluator cannot infer missing timing/quality metadata.
