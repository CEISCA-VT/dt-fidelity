# dt-fidelity

A NumPy-only receiver-side fidelity evaluator for frozen source states. It keeps
physical error, state age, and observability separate. Phase 1 reproduces the
original source-time centered 40-case service ledger; see
[reproduction report](docs/reproduction_report.md) and [validation](docs/phase1_validation.md).

Install on Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m pytest -q
python scripts/example.py
```

Install on Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
python scripts/example.py
```

Python 3.10+ is required. The runtime dependency is NumPy. Pytest is for tests.
No original repository, training framework, simulator, or sensor dataset is
needed to install, evaluate external data, or verify the bundled archived rows.
Python code is MIT licensed. Documentation and evidence are CC BY 4.0; see
[LICENSE](LICENSE), [LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0), and [NOTICE](NOTICE).

```python
import numpy as np
from dt_fidelity import ServiceContract, Trajectory, Delivery, nanoseconds, evaluate

t = nanoseconds(np.arange(101) / 10)
values = {"east_m": np.arange(101) / 10,
          "north_m": np.zeros(101), "heading_rad": np.zeros(101)}
reference = Trajectory(t, values)  # offline measurement evidence
twin = Trajectory(t, {k: v.copy() for k, v in values.items()})
delivery = Delivery(np.arange(len(t)), t + 50_000_000)
contract = ServiceContract("pose", {"position_m": 1., "heading_deg": 5.}, 1.)
result = evaluate(physical_reference=reference, source_states=twin,
                  delivery=delivery, contract=contract)
print(result.outcome, result.joint_satisfaction, result.observability)
```

`Trajectory.time_ns` contains strictly increasing integer source timestamps
(source) or query timestamps (reference). Optional `available_ns` describes when
each source state can first be sent. Default availability equals source time;
real computation/look-ahead delay must be supplied for deployment experiments.
`Delivery` maps source indices to arrival times, in any order. Omit lost packets;
duplicate transmissions are permitted. Arrival before availability is rejected.
`nanoseconds` rounds seconds with the original `np.rint(seconds * 1e9)` rule.
Integer epochs must fit int64; use a common relative origin for long recordings.

The receiver holds the arrived state with the greatest source timestamp. Cached
reads do not refresh its age. It neither interpolates nor extrapolates states.
Global pose uses Euclidean position error (meters) and wrapped heading error
(degrees, with input headings in radians). Local pose compares displacement in
each trajectory's own starting body frame and wrapped endpoint rotation.
Freshness applies only at the current endpoint. All thresholds are inclusive.

`horizon_s` declares the completed motion interval. Historical reference queries
must exist at exactly `t-H`; absent endpoints reduce observability. Queries are
never filled. `start_index` selects the scoring prefix **before** adding the
horizon; `end_index` is an exclusive end. The original fixtures use a 10-Hz
clock with `start_index=300` (30 seconds), so local scoring starts at `30+H`.
Historical replay explicitly sets `horizon_steps=round(H*10)` to preserve the
original index-based horizon even with timestamp jitter; eligibility then starts
at `start_index+horizon_steps`. Without it, the general API uses exact timestamps.
Other processes may supply other clocks. Query phase is part of the protocol;
this API does not silently interpolate a shifted reference clock.

`valid` masks mark missing reference or source evidence. Nonfinite required
fields also mark a sample unavailable. Local evaluation requires both reference
and receiver endpoints. Contract `evidence_rules` name additional Boolean query
masks passed as `evidence_masks`; omitted named evidence is unavailable. For
local services these masks must hold at both endpoints. Insufficient coverage
returns `unobservable`. Satisfaction fractions divide by observable samples;
coverage divides by all eligible queries. No observable samples means NaN
satisfaction and an unobservable outcome. Diagnostics expose component errors,
sample masks, held indices, ages, and pass indicators, without combining units.

For another process, provide a `discrepancy` callback and `required_fields`:

```python
def temperature_error(ref, src, current, previous, held, old_held):
    return {"temperature_K": np.abs(ref.values["temperature_K"][current]
                                     - src.values["temperature_K"][held])}

thermal = ServiceContract("thermal", {"temperature_K": 0.5}, max_age_s=2,
                          units={"temperature_K": "K"})
# evaluate(..., contract=thermal, discrepancy=temperature_error,
#          required_fields=("temperature_K",))
```

The callback receives observable endpoint index arrays; historical arrays are
`None` for global checks. It returns finite, nonnegative discrepancy vectors,
one per required contract quantity. The callback defines the physical meaning
of a custom finite-horizon quantity. The numerical core handles evidence,
delivery, ages, thresholds, and fractions independently of physical-system names.

`compare_delivery` accepts `deliveries={"degraded": ..., "ideal": ...,
"practical": ...}` and the same evaluation arguments. It reuses the same
reference and source arrays, returning per-condition results, a classification,
and practical restoration. Any unobservable tested condition is reported
separately. Already qualified under degraded delivery takes precedence;
otherwise ideal qualification distinguishes remediable from persistent.
"Ideal" always means the tested ideal-available stream, not a guarantee of
monotonic accuracy or an optimal delivery policy.

Run the reproducibility checks from this repository:

```bash
python scripts/verify_archived_evidence.py --output evidence/validation/archive_report.json
python scripts/replay_original_cases.py --data-root ../DigitalTwinDivergence --output evidence/validation
python scripts/check_source_provenance.py --source-root ../DigitalTwinDivergence
```

The last two commands require external inputs; `--data-root` must contain the
manifest-relative export paths. `--manifest` accepts a supplied centered bank
manifest. Hash mismatches fail; missing files are enumerated in
`missing_inputs.json`, never replaced by synthetic data. The test suite uses a
small pinned numerical oracle and works after the old repository is removed.
Archived subsets, manifests, and generated replay summaries are bundled;
trajectories and model checkpoints are not.

The reference is offline evaluation evidence and is never passed to receiver
reconstruction. It may contain measurement uncertainty; users must document
its timing, supported quantities, quality, and valid intervals. Source states
and delivery histories can come from any external experiment. No attack,
defense, attestation, or security guarantee is implemented. Future security
outcomes must be reported separately from physical-fidelity outcomes.
