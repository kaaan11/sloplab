"""Keep the published lexical control bound to actual code, inputs and metrics."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.base import get_evaluator
from sloplab.experiments.input_identity import build_input_identity
from sloplab.mutations.materialize import load_suite_config, materialize_suite
from sloplab.reporting.writers import metrics_to_dict
from sloplab.scoring.harness import build_cases, run_suite
from sloplab.scoring.metrics import compute_metrics

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "experiments/results/deterministic/text-quality-control-2026-10-03"


def test_text_control_snapshot_reproduces_code_inputs_and_metrics(tmp_path: Path) -> None:
    config = load_suite_config(ROOT / "benchmarks/suites/v1-core.yaml")
    canonical, _ = discover_fixtures(ROOT / "corpus")
    materialize_suite(config, canonical, tmp_path, corpus_root_resolved=ROOT / "corpus")
    cases = build_cases(tmp_path / "suite-index.jsonl", ROOT / "corpus", tmp_path)
    records = run_suite(get_evaluator("text-quality-baseline"), cases)
    assert len(records) == 297
    fresh_bytes = "".join(r.model_dump_json() + "\n" for r in records).encode()
    assert fresh_bytes == (SNAPSHOT / "records.jsonl").read_bytes()
    assert build_input_identity(cases) == json.loads((SNAPSHOT / "input-identity.json").read_text())
    assert metrics_to_dict(compute_metrics(records, "text-quality-baseline")) == json.loads(
        (SNAPSHOT / "metrics-text-quality-baseline.json").read_text()
    )
    provenance = json.loads((SNAPSHOT / "provenance.json").read_text())
    assert provenance["decision_counts"] == dict(Counter(str(r.decision) for r in records))
    assert provenance["authored_target_counts"] == dict(
        Counter(str(r.expected_decision) for r in records)
    )
    for path, digest in provenance["artifact_sha256"].items():
        assert hashlib.sha256((SNAPSHOT / path).read_bytes()).hexdigest() == digest
    for path, digest in provenance["source_file_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
