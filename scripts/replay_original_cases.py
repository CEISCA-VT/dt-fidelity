"""Level B: hash-verified frozen outer-test replay; no training or data copying."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from dt_fidelity import ServiceContract, Trajectory, nanoseconds, periodic_delivery, evaluate

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_archived_evidence import FIXTURES, ROOT, METRICS, CONDITIONS, aggregate, read_rows, summarize


def load_export(path):
    columns = ["time_s", "gt_east_m", "gt_north_m", "gt_heading_rad",
               "estimate_east_m", "estimate_north_m", "estimate_heading_rad"]
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        data = np.asarray([[float(row[c]) for c in columns] for row in reader], float)
    a = dict(zip(columns, data.T))
    a["time_s"] -= a["time_s"][0]
    if not np.all(np.diff(a["time_s"]) > 0) or abs(np.median(np.diff(a["time_s"])) - .1) > .005:
        raise ValueError("Historical exports must use their native 10-Hz clock")
    t = nanoseconds(a["time_s"])
    ref = Trajectory(t, {k: a["gt_" + k] for k in ("east_m", "north_m", "heading_rad")})
    src = Trajectory(t, {k: a["estimate_" + k] for k in ("east_m", "north_m", "heading_rad")})
    return a, ref, src


def run(data_root, output, manifest_path=FIXTURES / "trajectory_manifest.json"):
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("feature_derivative_mode", "centered") != "centered":
        raise ValueError("Primary regression requires source-time centered states")
    entries = [e for e in manifest["trajectories"] if e["role"] == "outer_test"]
    assert len(entries) == 30
    paths = [data_root / Path(e["trajectory"].replace("\\", "/")) for e in entries]
    missing = [str(p.relative_to(data_root)) for p in paths if not p.is_file()]
    output.mkdir(parents=True, exist_ok=True)
    if missing:
        (output / "missing_inputs.json").write_text(json.dumps(missing, indent=2) + "\n")
        raise FileNotFoundError(f"{len(missing)} required exports absent; see {output / 'missing_inputs.json'}")
    spec = importlib.util.spec_from_file_location("original_oracle", ROOT / "tests/original_oracle.py")
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    contracts = [ServiceContract(**s) for s in json.loads((ROOT / "configs/original_services.json").read_text())]
    rows, maximum, hashes = [], 0.0, {}
    saved = {(r["sequence"], r["service"], r["replicate"], float(r["rate_hz"]), float(r["delay_ms"])): r
             for r in read_rows(FIXTURES / "per_run_response_surface.csv")}
    archive_difference = 0.0
    for entry, path in zip(entries, paths):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["sha256"], f"Frozen trajectory hash mismatch: {entry['trajectory']}"
        hashes[entry["trajectory"]] = digest
        a, ref, src = load_export(path)
        replicate = path.parent.parent.name
        for contract in contracts:
            service = dict(family="local" if contract.horizon_s else "global", horizon_s=contract.horizon_s,
                           pos_tol_m=contract.tolerances["position_m"], heading_tol_deg=contract.tolerances["heading_deg"],
                           aoi_limit_s=contract.max_age_s)
            for condition, (rate, delay) in CONDITIONS.items():
                result = evaluate(physical_reference=ref, source_states=src,
                                  delivery=periodic_delivery(src, rate, delay), contract=contract, start_index=300,
                                  horizon_steps=int(round(contract.horizon_s * 10)))
                original = oracle.evaluate(a, service, rate, delay)
                row = dict(sequence=entry["target"], service=contract.name, replicate=replicate,
                           condition=condition, rate_hz=rate, delay_ms=delay, outcome=result.outcome)
                for metric in (*METRICS, "eligible_samples", "observable_samples"):
                    value = getattr(result, metric)
                    difference = abs(value - original[metric])
                    maximum = max(maximum, difference)
                    assert difference <= 1e-12, (entry["target"], contract.name, condition, metric, difference)
                    row[metric] = value
                for quantity, suffix in [("position_m", "position_discrepancy_m"), ("heading_deg", "heading_discrepancy_deg")]:
                    values = result.diagnostics["discrepancies"][quantity]
                    for stat, val in [("mean", np.mean(values)), ("p95", np.quantile(values, .95))]:
                        difference = abs(val - original[f"{stat}_{suffix}"])
                        maximum = max(maximum, float(difference))
                        assert difference <= 1e-12
                for metric in ("mean_aoi_s", "max_aoi_s"):
                    difference = abs(result.diagnostics[metric] - original[metric])
                    maximum = max(maximum, difference)
                    assert difference <= 1e-12
                archive = saved[entry["target"], contract.name, replicate, rate, delay]
                for metric in (*METRICS, "eligible_samples", "observable_samples"):
                    difference = abs(row[metric] - float(archive[metric]))
                    archive_difference = max(archive_difference, difference)
                    assert difference <= 1e-12
                assert (result.outcome == "qualified") == bool(int(archive["qualified"]))
                rows.append(row)
        print(f"Replayed {entry['target']} seed {entry['seed']}", flush=True)
    cells = aggregate(rows)
    maximum_case_difference = 0.0
    for row in read_rows(FIXTURES / "per_sequence_response_surface.csv"):
        key = row["sequence"], row["service"], float(row["rate_hz"]), float(row["delay_ms"])
        for metric in METRICS:
            difference = abs(cells[key][metric] - float(row[metric]))
            maximum_case_difference = max(maximum_case_difference, difference)
            assert difference <= 1e-12
        assert (cells[key]["outcome"] == "qualified") == bool(int(row["qualified"]))
    summary = summarize(cells)
    assert summary["classifications"] == dict(delivery_remediable=30, persistent_under_ideal=6, already_qualified_degraded=4)
    assert summary["practical_restored"] == 27
    with (output / "per_run_replay.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (output / "per_case_replay.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["sequence", "service", "rate_hz", "delay_ms", *METRICS, "outcome"])
        writer.writeheader()
        writer.writerows(dict(sequence=k[0], service=k[1], rate_hz=k[2], delay_ms=k[3], **v) for k, v in sorted(cells.items()))
    report = dict(level="B: independent frozen trajectory replay", trajectories=len(entries), seed_cases=len(rows),
                  max_absolute_difference_original=maximum, max_absolute_difference_archived=archive_difference,
                  max_absolute_difference_sequence=maximum_case_difference,
                  **summary, trajectory_sha256=hashes)
    (output / "replay_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k:v for k,v in report.items() if k != "trajectory_sha256"}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--data-root", type=Path, required=True, help="Root containing manifest-relative export paths")
    parser.add_argument("--manifest", type=Path, default=FIXTURES / "trajectory_manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/validation")
    args = parser.parse_args()
    run(args.data_root, args.output, args.manifest)


if __name__ == "__main__":
    main()
