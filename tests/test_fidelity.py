import json
import hashlib
from pathlib import Path
from dataclasses import replace
import sys
from types import SimpleNamespace
import numpy as np
import pytest
from dt_fidelity import (ServiceContract, Trajectory, Delivery, nanoseconds, evaluate,
                         reconstruct, periodic_delivery, classify, compare_delivery)
from dt_fidelity.evaluator import relative, wrap, outcome
import original_oracle as original

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = [ServiceContract(**s) for s in json.loads((ROOT / "configs/original_services.json").read_text())]


def trace(n=1001, offset=0., angular=False):
    t = np.arange(n) * .1
    head = wrap(t * .23 + 3.) if angular else np.zeros(n)
    x, y = (np.sin(t), np.cos(t)) if angular else (t.copy(), np.zeros(n))
    a = dict(time_s=t, gt_east_m=x, gt_north_m=y, gt_heading_rad=head,
             estimate_east_m=x + offset, estimate_north_m=y.copy(), estimate_heading_rad=head.copy())
    return a


def streams(a, mask=None, available=None):
    t = nanoseconds(a["time_s"])
    return (Trajectory(t, {k: a["gt_"+k] for k in ("east_m", "north_m", "heading_rad")}, valid=mask),
            Trajectory(t, {k: a["estimate_"+k] for k in ("east_m", "north_m", "heading_rad")}, available_ns=available))


def run(a, c, rate=10, delay=0, **kwargs):
    ref, src = streams(a)
    return evaluate(physical_reference=ref, source_states=src, delivery=periodic_delivery(src, rate, delay),
                    contract=c, start_index=300, horizon_steps=int(round(c.horizon_s*10)), **kwargs)


def old_service(c):
    return dict(family="local" if c.horizon_s else "global", horizon_s=c.horizon_s,
                pos_tol_m=c.tolerances["position_m"], heading_tol_deg=c.tolerances["heading_deg"],
                aoi_limit_s=c.max_age_s)


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.name)
@pytest.mark.parametrize("rate", [1, 2, 5, 10])
@pytest.mark.parametrize("delay", [0, 25, 50, 100, 200])
def test_original_numerical_equivalence(contract, rate, delay):
    a = trace(1209, angular=True)
    a["estimate_east_m"] += .13 * np.sin(a["time_s"] * 3)
    a["estimate_heading_rad"] += .03 * np.cos(a["time_s"])
    a["time_s"] += 1e-12 * np.sin(np.arange(len(a["time_s"])))
    result = run(a, contract, rate, delay)
    expected = original.evaluate(a, old_service(contract), rate, delay)
    for metric in ("coverage", "physical_satisfaction", "freshness_satisfaction", "joint_satisfaction",
                   "eligible_samples", "observable_samples"):
        np.testing.assert_allclose(getattr(result, metric), expected[metric], rtol=0, atol=1e-12)
    for quantity, suffix in [("position_m", "position_discrepancy_m"), ("heading_deg", "heading_discrepancy_deg")]:
        errors = result.diagnostics["discrepancies"][quantity]
        np.testing.assert_allclose(errors.mean(), expected["mean_"+suffix], rtol=0, atol=1e-12)
        np.testing.assert_allclose(np.quantile(errors, .95), expected["p95_"+suffix], rtol=0, atol=1e-12)
    np.testing.assert_array_equal(result.diagnostics["held_indices"], original.delivered_indices(a["time_s"], rate, delay/1000))


def test_legitimate_and_identical_states():
    result = run(trace(), CONTRACTS[0], 2, 200)
    assert result.outcome == "qualified" and result.joint_satisfaction == 1
    result = run(trace(angular=True), CONTRACTS[0])
    for errors in result.diagnostics["discrepancies"].values():
        np.testing.assert_array_equal(errors, np.zeros(len(errors)))


def test_native_index_clock_preserves_original_with_timestamp_jitter():
    a = trace(1001, angular=True)
    a["time_s"] += 1e-5 * np.sin(np.arange(1001))
    result = run(a, CONTRACTS[1], 2, 200)
    expected = original.evaluate(a, old_service(CONTRACTS[1]), 2, 200)
    assert result.observable_samples == expected["observable_samples"]
    assert result.joint_satisfaction == expected["joint_satisfaction"]


def test_general_clock_missing_historical_query_counts_against_coverage():
    t = nanoseconds([0, 1, 3, 4])
    values = {"east_m": np.zeros(4), "north_m": np.zeros(4), "heading_rad": np.zeros(4)}
    ref, src = Trajectory(t, values), Trajectory(t, values)
    c = replace(CONTRACTS[0], horizon_s=1.)
    result = evaluate(physical_reference=ref, source_states=src, delivery=Delivery(np.arange(4), t), contract=c)
    assert result.eligible_samples == 3 and result.observable_samples == 2
    assert result.coverage == 2/3 and result.outcome == "unobservable"


def test_fresh_but_physically_inaccurate():
    result = run(trace(offset=2), CONTRACTS[-1])
    assert result.outcome == "unqualified"
    assert result.freshness_satisfaction == 1 and result.physical_satisfaction == 0
    assert original.evaluate(trace(offset=2), old_service(CONTRACTS[-1]), 10, 0)["joint_satisfaction"] == 0


def test_accurate_but_stale():
    a = trace()
    for key in list(a):
        if key != "time_s":
            a[key][:] = 0
    result = run(a, CONTRACTS[-1], delay=2000)
    expected = original.evaluate(a, old_service(CONTRACTS[-1]), 10, 2000)
    assert result.outcome == "unqualified" and result.physical_satisfaction == 1 and result.freshness_satisfaction == 0
    assert expected["physical_satisfaction"] == 1 and expected["freshness_satisfaction"] == 0


def test_out_of_order_duplicates_missing_and_query_order():
    _, src = streams(trace(5))
    delivery = Delivery(np.array([0, 2, 1, 2]), nanoseconds([0, .2, .4, .5]))
    np.testing.assert_array_equal(reconstruct(src, delivery, nanoseconds([-.1, 0, .2, .4, .6])), [-1, 0, 2, 2, 2])
    np.testing.assert_array_equal(reconstruct(src, delivery, nanoseconds([.6, -.1, .2])), [2, -1, 2])
    np.testing.assert_array_equal(reconstruct(src, Delivery(np.array([], int), np.array([], int)), src.time_ns), [-1]*5)


def test_availability_distinguished_from_transmission():
    a = trace(5)
    t = nanoseconds(a["time_s"])
    _, src = streams(a, available=t + 100_000_000)
    delivery = periodic_delivery(src, 10, 100)
    np.testing.assert_array_equal(delivery.arrival_ns, t + 200_000_000)
    np.testing.assert_array_equal(reconstruct(src, delivery, t), [-1, -1, 0, 1, 2])
    np.testing.assert_array_equal(reconstruct(src, delivery, t), original.delivered_indices(a["time_s"], 10, .2))
    with pytest.raises(ValueError, match="Causal"):
        reconstruct(src, Delivery(np.arange(5), t), t)


@pytest.mark.parametrize("mask_end,missing,status", [(620, 30, "qualified"), (700, 110, "unobservable"), (1000, 400, "unobservable")])
def test_missing_reference_both_endpoints_and_denominators(mask_end, missing, status):
    a = trace(1000)
    mask = np.ones(1000, bool); mask[600:mask_end] = False
    ref, src = streams(a, mask)
    result = evaluate(physical_reference=ref, source_states=src, delivery=periodic_delivery(src, 10),
                      contract=CONTRACTS[0], start_index=300)
    assert result.eligible_samples - result.observable_samples == missing
    assert result.joint_satisfaction == 1 and result.outcome == status
    expected = original.reference_mask_evaluation(a, old_service(CONTRACTS[0]), mask)
    for metric in ("coverage", "physical_satisfaction", "freshness_satisfaction", "joint_satisfaction",
                   "eligible_samples", "observable_samples"):
        assert getattr(result, metric) == expected[metric]
    assert result.outcome == expected["status"]


def test_no_evidence_is_undefined():
    ref, src = streams(trace(501), np.zeros(501, bool))
    result = evaluate(physical_reference=ref, source_states=src, delivery=periodic_delivery(src, 10), contract=CONTRACTS[0])
    assert result.outcome == "unobservable" and result.coverage == 0
    assert np.isnan(result.joint_satisfaction)
    expected = original.reference_mask_evaluation(trace(501), old_service(CONTRACTS[0]), np.zeros(501, bool))
    assert expected["status"] == result.outcome and np.isnan(expected["joint_satisfaction"])


def test_observable_satisfaction_denominator_and_named_evidence():
    ref = Trajectory(np.arange(5, dtype=np.int64), {"temperature": [0, 0, 0, 0, 0]})
    src = Trajectory(ref.time_ns, {"temperature": [0, 0, 10, 0, 0]})
    c = ServiceContract("thermal", {"temperature": 1}, 1, minimum_observability=.5,
                        units={"temperature": "K"}, evidence_rules=("synchronized",))
    def difference(r, s, now, old, held, old_held):
        return {"temperature": np.abs(r.values["temperature"][now]-s.values["temperature"][held])}
    kwargs = dict(physical_reference=ref, source_states=src, delivery=periodic_delivery(src, 10), contract=c,
                  discrepancy=difference, required_fields=("temperature",))
    result = evaluate(**kwargs, evidence_masks={"synchronized": [1, 1, 1, 0, 0]})
    assert result.coverage == .6 and result.joint_satisfaction == 2/3 and result.outcome == "unqualified"
    assert evaluate(**kwargs).outcome == "unobservable"


def test_relative_motion_and_wrap_directly():
    a = trace(angular=True)
    i, j = np.array([0, 10, 50]), np.array([10, 60, 150])
    args = (a["gt_east_m"], a["gt_north_m"], a["gt_heading_rad"], i, j)
    np.testing.assert_array_equal(relative(*args), original.relative(*args))
    np.testing.assert_array_equal(wrap(np.array([-3*np.pi, -np.pi, np.pi, 3*np.pi])), [-np.pi]*4)
    # A rigidly transformed trajectory has identical motion in its own body frame.
    x, y, th = a["gt_east_m"], a["gt_north_m"], a["gt_heading_rad"]
    a["estimate_east_m"], a["estimate_north_m"] = -y+100, x-20
    a["estimate_heading_rad"] = wrap(th+np.pi/2)
    result = run(a, CONTRACTS[1])
    assert result.joint_satisfaction == 1
    np.testing.assert_allclose(result.diagnostics["discrepancies"]["position_m"], 0, rtol=0, atol=3e-14)


@pytest.mark.parametrize("offset,passes", [(1., True), (np.nextafter(1., np.inf), False)])
def test_inclusive_physical_boundary(offset, passes):
    a = trace()
    a["gt_east_m"][:] = 0; a["estimate_east_m"][:] = offset
    result = run(a, CONTRACTS[-1])
    assert (result.physical_satisfaction == 1) == passes
    assert original.evaluate(a, old_service(CONTRACTS[-1]), 10, 0)["physical_satisfaction"] == result.physical_satisfaction


def test_inclusive_age_satisfaction_and_observability_boundaries():
    a = trace()
    c = replace(CONTRACTS[-1], max_age_s=.2)
    assert run(a, c, delay=200).freshness_satisfaction == 1
    assert run(a, c, delay=200.000001).freshness_satisfaction == 0
    assert original.evaluate(a, old_service(c), 10, 200)["freshness_satisfaction"] == 1
    assert outcome(.95, .8, .8, .8, c) == "qualified"
    assert outcome(np.nextafter(.95, 0), 1, 1, 1, c) == "unobservable"
    assert outcome(1, .8, .8, np.nextafter(.8, 0), c) == "unqualified"
    # Marginal passes do not guarantee sufficient overlap.
    assert outcome(1, .8, .8, .6, c) == "unqualified"


@pytest.mark.parametrize("d,i,p,label", [(0,1,1,"delivery_remediable"), (0,0,0,"persistent_under_ideal"),
                         (1,1,1,"already_qualified_degraded"), (1,0,0,"already_qualified_degraded"),
                         (0,1,None,"unobservable")])
def test_remediability_precedence(d,i,p,label):
    result = lambda v: SimpleNamespace(outcome="unobservable" if v is None else "qualified" if v else "unqualified")
    assert classify(result(d), result(i), result(p)) == label


def test_comparison_uses_same_frozen_source():
    ref, src = streams(trace())
    before = {k: v.copy() for k,v in src.values.items()}
    result = compare_delivery(physical_reference=ref, source_states=src, contract=CONTRACTS[-1], start_index=300,
              deliveries={"degraded": periodic_delivery(src, 2, 200), "ideal": periodic_delivery(src, 10),
                          "practical": periodic_delivery(src, 5, 50)})
    assert result["classification"] == "already_qualified_degraded"
    for k in before:
        np.testing.assert_array_equal(before[k], src.values[k])


def test_archived_original_regression_fixtures():
    sys.path.insert(0, str(ROOT / "scripts"))
    from verify_archived_evidence import verify
    result = verify()
    assert result["cases"] == 40 and result["practical_restored"] == 27


def test_fixtures_and_oracle_match_recorded_hashes():
    provenance = json.loads((ROOT / "docs/source_hashes.json").read_text())
    for name, digest in provenance["portable_fixture_sha256"].items():
        assert hashlib.sha256((ROOT / "evidence/minimal_regression_fixtures" / name).read_bytes()).hexdigest() == digest
    assert hashlib.sha256((ROOT / "tests/original_oracle.py").read_bytes()).hexdigest() == provenance["oracle_sha256"]


def test_short_empty_and_missing_source_evidence():
    ref, src = streams(trace(5))
    result = evaluate(physical_reference=ref, source_states=src, delivery=periodic_delivery(src, 10), contract=CONTRACTS[2])
    assert result.outcome == "unobservable" and result.eligible_samples == 0
    src.valid[:] = False
    assert evaluate(physical_reference=ref, source_states=src, delivery=periodic_delivery(src, 10), contract=CONTRACTS[-1]).outcome == "unobservable"
    empty = Trajectory(np.array([], dtype=np.int64), {"east_m": [], "north_m": [], "heading_rad": []})
    assert evaluate(physical_reference=empty, source_states=empty, delivery=periodic_delivery(empty, 10), contract=CONTRACTS[0]).outcome == "unobservable"


def test_input_validation():
    with pytest.raises(ValueError):
        Trajectory(np.array([1, 1]), {"x": [0, 0]})
    with pytest.raises(ValueError):
        Trajectory(np.array([1., 2.]), {"x": [0, 0]})
    with pytest.raises(ValueError):
        ServiceContract("invalid", {"x": -1}, 1)
    _, src = streams(trace(5))
    with pytest.raises(ValueError):
        periodic_delivery(src, 3)
    with pytest.raises(ValueError):
        reconstruct(src, Delivery(np.array([5]), np.array([10])), src.time_ns)
