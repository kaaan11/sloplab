"""Verify the recorded ten-case repeat pilot offline and print its derived summary."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from sloplab.experiments.bundle import verify_bundle
from sloplab.experiments.input_identity import build_input_identity
from sloplab.models.run import CaseRecord
from sloplab.scoring.comparison import repeat_stability
from sloplab.scoring.harness import build_cases


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    archive = root / "experiments/results/llm-pilot/2026-10-04/nemotron-repeat-01"
    protocol = json.loads((archive / "protocol.json").read_text())
    assert (
        hashlib.sha256((root / protocol["runner_file"]).read_bytes()).hexdigest()
        == protocol["runner_sha256"]
    )
    config = protocol["config"]
    assert (
        hashlib.sha256((root / config["prompt_file"]).read_bytes()).hexdigest()
        == protocol["prompt_sha256"]
    )
    selected = [
        case
        for case in build_cases(
            root / "benchmarks/results/v1-core-example/suite-index.jsonl",
            root / "corpus",
            root / "benchmarks/results/v1-core-example",
        )
        if case.kind == "canonical"
    ][:10]
    ids = [case.case_id for case in selected]
    assert ids == protocol["selected_case_ids"]
    assert build_input_identity(selected) == protocol["input_identity"]
    bundle = archive / "bundle"
    verify_bundle(bundle, kind="llm-pilot")
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["selected_case_ids"] == ids
    assert manifest["commit_sha"] == protocol["source_commit"]
    assert manifest["model_id"] == protocol["model"]
    assert manifest["prompt_hash"] == protocol["prompt_sha256"]
    for key in ("repeats", "output_mode", "provider_require_parameters", "temperature", "budget"):
        assert manifest[key] == config[key]
    assert config["repeats"] == 3 and config["max_cases"] == 10
    assert config["budget"]["max_requests"] == 30
    assert config["budget"]["max_retries_per_case"] == 0
    rows = [json.loads(line) for line in (bundle / "records.jsonl").read_text().splitlines()]
    outcomes = [json.loads(line) for line in (bundle / "outcomes.jsonl").read_text().splitlines()]
    expected = {(case_id, repeat) for repeat in range(3) for case_id in ids}
    outcome_keys = {(row["case_id"], row["repeat_index"]) for row in outcomes}
    record_keys = {(row["case_id"], row["evaluation_metadata"]["repeat_index"]) for row in rows}
    assert len(outcomes) == len(outcome_keys) == 30 and outcome_keys == expected
    assert len(rows) == len(record_keys)
    assert record_keys == {
        (row["case_id"], row["repeat_index"]) for row in outcomes if row["status"] == "success"
    }
    by_id = {case.case_id: case for case in selected}
    for row in rows:
        assert row["expected_decision"] == by_id[row["case_id"]].expected_decision
        assert row["correct"] == (row["decision"] == row["expected_decision"])
    status_counts = Counter(row["status"] for row in outcomes)
    assert manifest["successful"] == status_counts["success"] == len(rows)
    assert manifest["failed"] == status_counts["failed"]
    assert manifest["not_run"] == status_counts["not_run"]
    requests = manifest["counters"]["physical_dispatches"]
    assert 0 <= requests <= 30
    full = len(rows) == 30
    assert manifest["coverage_sufficient"] == full
    stability = {}
    if full:
        assert requests == 30
        stability = repeat_stability(
            [
                [
                    CaseRecord.model_validate(row)
                    for row in rows
                    if row["evaluation_metadata"]["repeat_index"] == repeat
                ]
                for repeat in range(3)
            ]
        ).as_dict()
    assert manifest["stability"] == stability
    summary = {
        "planned_cases": 10,
        "repeats": 3,
        "planned_evaluations": 30,
        "physical_requests": requests,
        "valid_responses": len(rows),
        "failed_evaluations": status_counts["failed"],
        "not_run": status_counts["not_run"],
        "authored_target_matches": sum(row["correct"] for row in rows),
        "stability": stability,
        "per_case": [
            {
                "case_id": case_id,
                "decisions": [row["decision"] for row in rows if row["case_id"] == case_id],
                "confidences": [row["confidence"] for row in rows if row["case_id"] == case_id],
            }
            for case_id in ids
        ],
        "protocol_sha256": hashlib.sha256((archive / "protocol.json").read_bytes()).hexdigest(),
    }
    stored = archive / "summary.json"
    if stored.exists():
        assert json.loads(stored.read_text()) == summary
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
