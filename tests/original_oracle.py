"""Verbatim numerical functions from the pinned source; TEST ONLY. See NOTICE."""
import numpy as np
PREFIX_S=30.0
def wrap(x): return (np.asarray(x) + np.pi) % (2*np.pi) - np.pi

def relative(x, y, th, i, j):
    dx, dy = x[j]-x[i], y[j]-y[i]; c, s = np.cos(th[i]), np.sin(th[i])
    return c*dx+s*dy, -s*dx+c*dy, wrap(th[j]-th[i])

def delivered_indices(t, rate, delay_s):
    stride = int(round(10/rate))
    src = np.arange(0, len(t), stride)
    clock_ns = np.rint(np.asarray(t) * 1_000_000_000).astype(np.int64)
    arrivals = clock_ns[src] + int(round(delay_s * 1_000_000_000))
    p = np.searchsorted(arrivals, clock_ns, side="right") - 1
    idx = np.full(len(t), -1, int); valid = p >= 0; idx[valid] = src[p[valid]]
    return idx

def episodes(mask, dt=.1):
    if not len(mask): return (0, 0.0, 0.0)
    z = np.r_[False, mask, False].astype(int); edges = np.diff(z)
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    lengths = (ends-starts)*dt
    return len(lengths), float(lengths.sum()), float(lengths.max()) if len(lengths) else 0.0

def evaluate(a, service, rate, delay_ms, start_s=PREFIX_S, end_s=None):
    t = a["time_s"]; idx = delivered_indices(t, rate, delay_ms/1000)
    horizon_n = int(round(service["horizon_s"]*10))
    eligible = np.arange(len(t)) >= int(round(start_s*10)) + horizon_n
    if end_s is not None: eligible &= np.arange(len(t)) < int(round(end_s*10))
    observable = eligible & (idx >= 0)
    if horizon_n: observable &= np.r_[np.zeros(horizon_n,bool), idx[:-horizon_n] >= 0]
    pos = np.full(len(t), np.nan); head = np.full(len(t), np.nan)
    use = np.flatnonzero(observable)
    if service["family"] == "global":
        k = idx[use]
        pos[use] = np.hypot(a["estimate_east_m"][k]-a["gt_east_m"][use], a["estimate_north_m"][k]-a["gt_north_m"][use])
        head[use] = np.abs(np.rad2deg(wrap(a["estimate_heading_rad"][k]-a["gt_heading_rad"][use])))
    else:
        i = use-horizon_n; ki, kj = idx[i], idx[use]
        gp = relative(a["gt_east_m"],a["gt_north_m"],a["gt_heading_rad"],i,use)
        ep = relative(a["estimate_east_m"],a["estimate_north_m"],a["estimate_heading_rad"],ki,kj)
        pos[use] = np.hypot(ep[0]-gp[0], ep[1]-gp[1])
        head[use] = np.abs(np.rad2deg(wrap(ep[2]-gp[2])))
    age = np.full(len(t), np.inf)
    clock_ns = np.rint(t * 1_000_000_000).astype(np.int64)
    age[use] = (clock_ns[use] - clock_ns[idx[use]]) / 1_000_000_000
    physical = observable & (pos <= service["pos_tol_m"]) & (head <= service["heading_tol_deg"])
    fresh = observable & (age <= service["aoi_limit_s"])
    joint = physical & fresh
    denom = max(1, int(observable.sum()))
    fail_count, fail_s, fail_max = episodes(observable & ~joint)
    return {"coverage":float(observable.sum()/max(1,eligible.sum())),
            "physical_satisfaction":float(physical.sum()/denom), "freshness_satisfaction":float(fresh.sum()/denom),
            "joint_satisfaction":float(joint.sum()/denom), "failure_episodes":fail_count,
            "failure_duration_s":fail_s, "max_failure_episode_s":fail_max,
            "mean_position_discrepancy_m":float(np.mean(pos[observable])) if observable.any() else np.nan,
            "p95_position_discrepancy_m":float(np.quantile(pos[observable],.95)) if observable.any() else np.nan,
            "mean_heading_discrepancy_deg":float(np.mean(head[observable])) if observable.any() else np.nan,
            "p95_heading_discrepancy_deg":float(np.quantile(head[observable],.95)) if observable.any() else np.nan,
            "mean_aoi_s":float(np.mean(age[observable])) if observable.any() else np.nan,
            "max_aoi_s":float(np.max(age[observable])) if observable.any() else np.nan,
            "eligible_samples":int(eligible.sum()), "observable_samples":int(observable.sum())}


from types import SimpleNamespace
base=SimpleNamespace(PREFIX_S=30., MIN_COVERAGE=.95, TARGET=.8, relative=relative, wrap=wrap)

def reference_mask_evaluation(a, service, reference_valid):
    """Full-rate source-time replay, retaining the original scored query set."""
    t = a["time_s"]
    reference_valid = np.asarray(reference_valid, bool)
    if reference_valid.shape != t.shape:
        raise ValueError("Reference mask must match the query clock")
    reference_valid = reference_valid & np.isfinite(np.column_stack([
        a["gt_east_m"], a["gt_north_m"], a["gt_heading_rad"]])).all(axis=1)
    h = int(round(service["horizon_s"] * 10))
    eligible = np.arange(len(t)) >= int(round(base.PREFIX_S * 10)) + h
    observable = eligible & reference_valid
    if h:
        observable &= np.r_[np.zeros(h, bool), reference_valid[:-h]]
    use = np.flatnonzero(observable)
    if h:
        gt = base.relative(a["gt_east_m"], a["gt_north_m"], a["gt_heading_rad"], use-h, use)
        twin = base.relative(a["estimate_east_m"], a["estimate_north_m"],
                             a["estimate_heading_rad"], use-h, use)
        pos = np.hypot(twin[0]-gt[0], twin[1]-gt[1])
        heading = np.abs(np.rad2deg(base.wrap(twin[2]-gt[2])))
    else:
        pos = np.hypot(a["estimate_east_m"][use]-a["gt_east_m"][use],
                       a["estimate_north_m"][use]-a["gt_north_m"][use])
        heading = np.abs(np.rad2deg(base.wrap(
            a["estimate_heading_rad"][use]-a["gt_heading_rad"][use])))
    physical = (pos <= service["pos_tol_m"]) & (heading <= service["heading_tol_deg"])
    coverage = len(use) / max(1, eligible.sum())
    satisfaction = float(physical.mean()) if len(use) else np.nan
    status = ("unobservable" if coverage < base.MIN_COVERAGE or not len(use) else
              "qualified" if satisfaction >= base.TARGET else "unqualified")
    return dict(eligible_samples=int(eligible.sum()), observable_samples=len(use),
                coverage=coverage, physical_satisfaction=satisfaction,
                freshness_satisfaction=1. if len(use) else np.nan,
                joint_satisfaction=satisfaction, status=status)
