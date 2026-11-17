"""Componentwise qualification, with explicit offline reference evidence.

Numerical SE(2) logic extracted from service_timing_budget_study; see NOTICE
and docs/extraction_manifest.json for source attribution and adaptations.
"""
from dataclasses import dataclass
from collections.abc import Mapping
import numpy as np
from .receiver import reconstruct


def wrap(x):
    return (np.asarray(x) + np.pi) % (2 * np.pi) - np.pi


def relative(x, y, th, i, j):
    dx, dy = x[j] - x[i], y[j] - y[i]
    c, s = np.cos(th[i]), np.sin(th[i])
    return c * dx + s * dy, -s * dx + c * dy, wrap(th[j] - th[i])


def pose_discrepancy(reference, source, current, previous, held, old_held):
    """Meters and degrees; each local displacement uses its own starting frame."""
    r, s = reference.values, source.values
    if previous is None:
        pos = np.hypot(s["east_m"][held] - r["east_m"][current],
                       s["north_m"][held] - r["north_m"][current])
        head = np.abs(np.rad2deg(wrap(s["heading_rad"][held] - r["heading_rad"][current])))
    else:
        gp = relative(r["east_m"], r["north_m"], r["heading_rad"], previous, current)
        ep = relative(s["east_m"], s["north_m"], s["heading_rad"], old_held, held)
        pos = np.hypot(ep[0] - gp[0], ep[1] - gp[1])
        head = np.abs(np.rad2deg(wrap(ep[2] - gp[2])))
    return {"position_m": pos, "heading_deg": head}


def outcome(coverage, physical, fresh, joint, contract, observable_samples=1):
    if not observable_samples or coverage < contract.minimum_observability:
        return "unobservable"
    return "qualified" if all(x >= contract.satisfaction for x in (physical, fresh, joint)) else "unqualified"


@dataclass
class FidelityResult:
    outcome: str
    physical_satisfaction: float
    freshness_satisfaction: float
    joint_satisfaction: float
    observability: float
    eligible_samples: int
    observable_samples: int
    diagnostics: dict

    @property
    def coverage(self):
        return self.observability


def evaluate(*, physical_reference, source_states, delivery, contract,
             start_index=0, end_index=None, discrepancy=None,
             required_fields=None, evidence_masks: Mapping | None = None,
             horizon_steps=None):
    """Evaluate at the reference clock, with exact historical endpoint queries.

    start_index declares the scoring prefix BEFORE the horizon. Reference valid
    masks cover offline reference evidence; source valid masks cover receiver
    evidence. Named evidence rules must have explicit masks on the query clock.
    A custom discrepancy callback receives the same six arguments as
    pose_discrepancy and returns one nonnegative vector per contract quantity.
    required_fields declares only the fields needed by that callback.
    horizon_steps selects the original index-based native-clock convention;
    otherwise historical endpoints are looked up by exact query timestamp.
    """
    ref, src = physical_reference, source_states
    n = len(ref.time_ns)
    if start_index < 0 or (end_index is not None and end_index < start_index):
        raise ValueError("Invalid scoring window")
    if discrepancy is None:
        discrepancy = pose_discrepancy
        required_fields = ("east_m", "north_m", "heading_rad")
    elif required_fields is None:
        raise ValueError("Custom discrepancies must declare required_fields")
    for field in required_fields:
        if field not in ref.values or field not in src.values:
            raise ValueError(f"Required state field missing: {field}")
    t = ref.time_ns
    h = int(round(contract.horizon_s * 1e9))
    if horizon_steps is not None:
        if not isinstance(horizon_steps, (int, np.integer)) or horizon_steps < 0 or bool(horizon_steps) != bool(h):
            raise ValueError("horizon_steps must be nonnegative and consistent with horizon_s")
        eligible = np.arange(n) >= start_index + horizon_steps
        previous = np.arange(n) - horizon_steps
        history = previous >= 0
    else:
        # Keep queries with missing historical evidence in the denominator.
        boundary = t[start_index] + h if n and start_index < n else None
        eligible = np.zeros(n, bool) if boundary is None else (np.arange(n) >= start_index) & (t >= boundary)
        previous = np.searchsorted(t, t - h)
        history = (previous < n)
        if n:
            history &= t[np.minimum(previous, n - 1)] == t - h
    if end_index is not None:
        eligible &= np.arange(n) < end_index
    held = reconstruct(src, delivery, t)
    valid_ref, valid_src = ref.valid.copy(), src.valid.copy()
    for field in required_fields:
        valid_ref &= np.isfinite(ref.values[field])
        valid_src &= np.isfinite(src.values[field])
    masks = {} if evidence_masks is None else evidence_masks
    for rule in contract.evidence_rules:
        mask = np.asarray(masks.get(rule, np.zeros(n, bool)), bool)
        if mask.shape != (n,):
            raise ValueError(f"Evidence rule {rule} must match query clock")
        valid_ref &= mask
    observable = eligible & valid_ref & (held >= 0)
    use = np.flatnonzero(observable)
    observable[use] &= valid_src[held[use]]
    if h:
        observable &= history
        use = np.flatnonzero(observable)
        old = previous[use]
        observable[use] &= valid_ref[old] & (held[old] >= 0)
        use = np.flatnonzero(observable)
        observable[use] &= valid_src[held[previous[use]]]
    use = np.flatnonzero(observable)
    errors = discrepancy(ref, src, use, previous[use] if h else None,
                         held[use], held[previous[use]] if h else None)
    physical = np.ones(len(use), bool)
    for quantity, tolerance in contract.tolerances.items():
        if quantity not in errors:
            raise ValueError(f"Discrepancy did not return {quantity}")
        values = np.asarray(errors[quantity], float)
        if values.shape != (len(use),) or not np.isfinite(values).all() or np.any(values < 0):
            raise ValueError("Discrepancies must be finite nonnegative vectors on observable samples")
        physical &= values <= tolerance
    age = (t[use] - src.time_ns[held[use]]) / 1e9
    fresh = age <= contract.max_age_s
    joint = physical & fresh
    fractions = [float(x.mean()) if len(use) else float("nan") for x in (physical, fresh, joint)]
    coverage = len(use) / max(1, int(eligible.sum()))
    diagnostics = dict(query_indices=use, held_indices=held, discrepancies=errors,
                       age_s=age, physical_pass=physical, freshness_pass=fresh, joint_pass=joint,
                       eligible_mask=eligible, observable_mask=observable,
                       mean_aoi_s=float(age.mean()) if len(use) else float("nan"),
                       max_aoi_s=float(age.max()) if len(use) else float("nan"))
    return FidelityResult(outcome(coverage, *fractions, contract, len(use)), *fractions,
                          coverage, int(eligible.sum()), len(use), diagnostics)
