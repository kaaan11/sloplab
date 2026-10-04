"""Verify the recorded canonical study offline; do not execute the live runner."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from sloplab.experiments.bundle import verify_bundle
from sloplab.experiments.input_identity import build_input_identity
from sloplab.scoring.harness import build_cases


def main() -> None:
    archive = Path(__file__).resolve().parent
    root = archive.parents[4]
    protocol = json.loads((archive / "protocol.json").read_text())
    summary_path = archive / "summary.json"
    summary = json.loads(summary_path.read_text())
    provenance = json.loads((archive / "runner-provenance.json").read_text())
    assert provenance["original_runner_sha256"] == protocol["runner_sha256"]
    assert (
        hashlib.sha256((archive / "runner-source.txt").read_bytes()).hexdigest()
        == provenance["public_runner_sha256"]
    )
    assert (
        hashlib.sha256((root / protocol["config_base"]["prompt_file"]).read_bytes()).hexdigest()
        == protocol["prompt_sha256"]
    )
    cases = [
        case
        for case in build_cases(
            root / "benchmarks/results/v1-core-example/suite-index.jsonl",
            root / "corpus",
            root / "benchmarks/results/v1-core-example",
        )
        if case.kind == "canonical"
    ]
    assert build_input_identity(cases) == protocol["input_identity"]
    assert [case.case_id for case in cases] == protocol["planned_case_ids"]
    by_id = {case.case_id: case for case in cases}
    records, outcomes, selections = [], [], []
    requests = 0
    batches = sorted(archive.glob("batch-*"))
    assert len(batches) == len(protocol["batches"]) == 6
    for batch, planned in zip(batches, protocol["batches"], strict=True):
        verify_bundle(batch, kind="llm-pilot")
        manifest = json.loads((batch / "manifest.json").read_text())
        assert manifest["selected_case_ids"] == planned["case_ids"]
        assert manifest["model_id"] == protocol["model"]
        assert manifest["commit_sha"] == protocol["source_commit"]
        assert manifest["prompt_hash"] == protocol["prompt_sha256"]
        assert manifest["repeats"] == 1
        assert manifest["output_mode"] == "json_schema"
        assert manifest["provider_require_parameters"] is True
        assert manifest["temperature"] == 0
        selections.extend(manifest["selected_case_ids"])
        requests += manifest["counters"]["physical_dispatches"]
        records.extend(
            json.loads(line) for line in (batch / "records.jsonl").read_text().splitlines()
        )
        outcomes.extend(
            json.loads(line) for line in (batch / "outcomes.jsonl").read_text().splitlines()
        )
    assert selections == protocol["planned_case_ids"]
    assert len(records) == len(outcomes) == requests == protocol["max_requests"] == 60
    assert [row["case_id"] for row in records] == selections
    assert [row["case_id"] for row in outcomes] == selections
    assert all(row["status"] == "success" for row in outcomes)
    for row in records:
        case = by_id[row["case_id"]]
        assert row["expected_decision"] == case.expected_decision
        # The existing pilot records decisions, but omits dimensional targets.
        # Their provenance is checked through the frozen input identity above.
        assert row["expected_dimensions"] == {}
        assert row["correct"] == (row["decision"] == case.expected_decision)
        assert row["evaluation_metadata"]["repeat_index"] == 0
    correct = sum(row["correct"] for row in records)
    recomputed = {
        "completed_at": summary["completed_at"],  # Retain recorded wall-clock metadata.
        "model": protocol["model"],
        "planned_cases": len(selections),
        "physical_requests": requests,
        "valid_responses": len(records),
        "failed_evaluations": 0,
        "not_run_in_batches": 0,
        "unstarted_cases": [],
        "authored_target_matches": correct,
        "authored_target_agreement_on_valid": correct / len(records),
        "decision_counts": dict(Counter(row["decision"] for row in records)),
        "failure_counts": {},
        "disagreements": [
            {key: row[key] for key in ("case_id", "expected_decision", "decision")}
            for row in records
            if not row["correct"]
        ],
        "case_outcomes": [
            {key: row.get(key) for key in ("case_id", "status", "error_kind", "detail")}
            for row in outcomes
        ],
        "protocol_sha256": hashlib.sha256((archive / "protocol.json").read_bytes()).hexdigest(),
    }
    assert json.dumps(recomputed, indent=2).encode() == summary_path.read_bytes()
    print(
        f"Verified six bundles: {len(records)}/60 valid, "
        f"{correct}/60 target matches, {requests} requests."
    )


if __name__ == "__main__":
    main()
