"""Replay the recorded study offline after later commits, using its frozen sources.

Reconstruct the hash-checked public inputs and registered study sources in a
temporary directory. Run the original verifier in a fresh Python
process, keeping imported maintenance code out of the historical calculation.
No model calls, archive writes, or changes to the current checkout are made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT = "experiments/results/llm-pilot/2026-10-07/nemotron-mutation-repeats-01"
SNAPSHOT = "experiments/frozen/nemotron-mutation-repeats-2026-10-07"


def source_files(archive, snapshot):
    protocol = json.loads((archive / "protocol.json").read_text())
    manifest = json.loads((snapshot / "snapshot-manifest.json").read_text())
    protocol_sha = hashlib.sha256((archive / "protocol.json").read_bytes()).hexdigest()
    if (
        manifest["protocol_sha256"] != protocol_sha
        or manifest["source_commit"] != protocol["source_commit"]
        or manifest["files"] != protocol["source_sha256"]
    ):
        raise ValueError("Snapshot manifest differs from registered protocol")
    if not re.fullmatch(r"[0-9a-f]{40}", protocol["source_commit"]):
        raise ValueError("Invalid recorded commit")
    expected_files = dict(manifest["files"])
    for relative, digest in manifest["input_files"].items():
        if (
            not (
                relative.startswith("corpus/")
                or relative.startswith("benchmarks/results/v1-core-example/")
            )
            or relative in expected_files
        ):
            raise ValueError("Invalid snapshot input path")
        expected_files[relative] = digest
    files = {}
    for relative, expected in expected_files.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Snapshot path escapes root")
        data = (snapshot / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Frozen source/input changed: {relative}")
        files[relative] = data
    actual = {str(p.relative_to(snapshot)) for p in snapshot.rglob("*") if p.is_file()}
    if actual != set(files) | {"snapshot-manifest.json"} or any(
        p.is_symlink() for p in snapshot.rglob("*")
    ):
        raise ValueError("Snapshot inventory changed")
    return files


def reconstruct(destination, files):
    for relative, data in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def replay(archive, snapshot):
    files = source_files(archive, snapshot)
    with tempfile.TemporaryDirectory(prefix="sloplab-repeat-replay-") as temporary:
        reconstructed = Path(temporary)
        reconstruct(reconstructed, files)
        code = """
import json, sys
from pathlib import Path
root, archive = Path(sys.argv[1]), Path(sys.argv[2])
sys.path[:0] = [str(root / 'src'), str(root / 'experiments/scripts')]
import verify_nemotron_mutation_repeats as verifier
protocol = verifier.read(archive / 'protocol.json')
# This root is a reconstruction, not a Git checkout. Source commit is the
# original recorded metadata. Every source hash is checked, and the original
# verifier recomputes the registered report/target/input identities below.
# Only the checkout-HEAD lookup is replaced; all source/input/bundle/metric
# checks remain in the original, hash-bound verifier.
verifier.current_commit_sha = lambda _: protocol['source_commit']
print(json.dumps(verifier.replay(root, archive), allow_nan=False))
"""
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-c", code, str(reconstructed), str(archive.resolve())],
            cwd=reconstructed,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    summary = replay(args.archive or root / DEFAULT, args.snapshot or root / SNAPSHOT)
    if not args.full:
        summary = {
            "physical_requests": summary["physical_requests"],
            "valid": summary["valid"],
            "failed": summary["failed"],
            "not_run": summary["not_run"],
            "full_response_coverage": summary["full_response_coverage"],
            "stability": {
                kind: {
                    key: value[key]
                    for key in ("eligible", "complete", "incomplete", "unanimous", "changed")
                }
                for kind, value in summary["stability"].items()
            },
        }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
