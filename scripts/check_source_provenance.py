"""Verify pinned numerical oracle functions and recorded source hashes via Git."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(source_root):
    info = json.loads((ROOT / "docs/source_hashes.json").read_text())
    source_root = source_root.resolve()
    def pinned(path):
        return subprocess.check_output(["git", "-c", "safe.directory=" + source_root.as_posix(),
                                        "-C", str(source_root), "show", info["commit"] + ":" + path]).decode("utf-8")
    for entry in info["files"]:
        assert hashlib.sha256(pinned(entry["path"]).encode()).hexdigest() == entry["pinned_sha256"]
    for entry in info["archived_inputs"]:
        assert hashlib.sha256((source_root / entry["source"]).read_bytes()).hexdigest() == entry["sha256"]
    for name, digest in info["portable_fixture_sha256"].items():
        assert hashlib.sha256((ROOT / "evidence/minimal_regression_fixtures" / name).read_bytes()).hexdigest() == digest
    assert hashlib.sha256((ROOT / "tests/original_oracle.py").read_bytes()).hexdigest() == info["oracle_sha256"]
    oracle = ast.parse((ROOT / "tests/original_oracle.py").read_text())
    functions = {n.name: ast.dump(n, include_attributes=False) for n in oracle.body if isinstance(n, ast.FunctionDef)}
    for path, names in {
        "DigitalTwin/analysis/service_timing_budget_study.py": ["wrap", "relative", "delivered_indices", "episodes", "evaluate"],
        "scripts/build_review_revision_20261109.py": ["reference_mask_evaluation"],
    }.items():
        original = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(pinned(path)).body if isinstance(n, ast.FunctionDef)}
        for name in names:
            assert functions[name] == original[name], f"Oracle changed: {path}:{name}"
    result = dict(commit=info["commit"], pinned_files=len(info["files"]), verbatim_oracle_functions=len(functions), status="PASS")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    run(parser.parse_args().source_root)
