"""Level A: recompute the primary centered ledger from archived seed rows."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from dt_fidelity import ServiceContract, classify
from dt_fidelity.evaluator import outcome

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evidence/minimal_regression_fixtures"
METRICS = ("coverage", "physical_satisfaction", "freshness_satisfaction", "joint_satisfaction")
CONDITIONS = {"degraded": (2, 200), "practical": (5, 50), "ideal": (10, 0)}


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def selected(rows):
    return [r for r in rows if r["outer_sequence"] == r["sequence"] and
            (float(r["rate_hz"]), float(r["delay_ms"])) in CONDITIONS.values()]


def aggregate(rows):
    groups = defaultdict(list)
    for row in rows:
        key = row["sequence"], row["service"], float(row["rate_hz"]), float(row["delay_ms"])
        groups[key].append(row)
    result = {}
    for key, seeds in groups.items():
        if len(seeds) != 3 or len({r["replicate"] for r in seeds}) != 3:
            raise AssertionError(f"Expected exactly three distinct frozen seeds: {key}")
        values = {m: float(np.mean([float(s[m]) for s in seeds])) for m in METRICS}
        c = ServiceContract(key[1], {"unused": 0}, 1)
        values["outcome"] = outcome(*(values[m] for m in METRICS), c)
        result[key] = values
    return result


def summarize(cells):
    labels, patterns, restored = Counter(), Counter(), 0
    cases = sorted({(k[0], k[1]) for k in cells})
    for sequence, service in cases:
        v = {name: SimpleNamespace(**cells[sequence, service, *pair]) for name, pair in CONDITIONS.items()}
        label = classify(v["degraded"], v["ideal"], v["practical"])
        labels[label] += 1
        pattern = "".join(str(int(v[name].outcome == "qualified")) for name in CONDITIONS)
        patterns[pattern] += 1
        restored += label == "delivery_remediable" and v["practical"].outcome == "qualified"
    return dict(cases=len(cases), classifications=dict(labels), practical_restored=int(restored), patterns=dict(patterns))


def verify(folder=FIXTURES):
    folder = Path(folder)
    runs = selected(read_rows(folder / "per_run_response_surface.csv"))
    sequence_rows = selected(read_rows(folder / "per_sequence_response_surface.csv"))
    ledger = read_rows(folder / "sequence_service_case_ledger.csv")
    cells = aggregate(runs)
    assert len(runs) == 360 and len(cells) == 120 and len(sequence_rows) == 120 and len(ledger) == 40
    max_difference = 0.0
    seen = set()
    for row in sequence_rows:
        key = row["sequence"], row["service"], float(row["rate_hz"]), float(row["delay_ms"])
        assert key not in seen
        seen.add(key)
        for metric in METRICS:
            difference = abs(cells[key][metric] - float(row[metric]))
            max_difference = max(max_difference, difference)
            assert difference <= 1e-12, (key, metric, difference)
        assert (cells[key]["outcome"] == "qualified") == bool(int(row["qualified"]))
    seen = set()
    for row in ledger:
        key = row["sequence"], row["service"]
        assert key not in seen
        seen.add(key)
        values = {name: SimpleNamespace(**cells[*key, *pair]) for name, pair in CONDITIONS.items()}
        assert classify(values["degraded"], values["ideal"], values["practical"]) == row["classification"]
        for name in CONDITIONS:
            assert int(values[name].outcome == "qualified") == int(row[name + "_qualified"])
            for metric in METRICS:
                difference = abs(getattr(values[name], metric) - float(row[name + "_" + metric]))
                max_difference = max(max_difference, difference)
                assert difference <= 1e-12
    result = summarize(cells)
    assert result["classifications"] == dict(delivery_remediable=30, persistent_under_ideal=6, already_qualified_degraded=4)
    assert result["practical_restored"] == 27
    assert result["patterns"] == {"000": 6, "001": 3, "011": 27, "111": 4}
    manifest = json.loads((folder / "evidence_manifest.json").read_text())
    assert manifest["sequence_service_cases"] == result["cases"]
    assert manifest["remediability_counts"] == result["classifications"]
    return dict(level="A: archived evidence verification", seed_rows=len(runs), cells=len(cells),
                max_absolute_difference=max_difference, **result,
                input_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.csv"))})


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--evidence", type=Path, default=FIXTURES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.evidence)
    content = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    print(content)


if __name__ == "__main__":
    main()
