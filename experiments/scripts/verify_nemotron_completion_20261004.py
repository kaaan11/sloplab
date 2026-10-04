"""Offline verification of the authorized repeat replacement block and mutation continuation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from verify_nemotron_followups_20261004 import summarize as summarize_original

from sloplab.experiments.bundle import verify_bundle
from sloplab.experiments.input_identity import build_input_identity
from sloplab.models.run import CaseRecord
from sloplab.scoring.comparison import repeat_stability
from sloplab.scoring.harness import build_cases
from sloplab.scoring.metrics import compute_metrics

BASE = Path("experiments/results/llm-pilot/2026-10-04")


def load_cases(root):
    cases = build_cases(
        root / "benchmarks/results/v1-core-example/suite-index.jsonl",
        root / "corpus",
        root / "benchmarks/results/v1-core-example",
    )
    canonical = [case for case in cases if case.kind == "canonical"]
    mutated = [case for case in cases if case.kind == "mutated"]
    assert len(canonical) == 60 and len(mutated) == 237
    return canonical, mutated


def json_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def stability(rows, repeats):
    return repeat_stability(
        [
            [
                CaseRecord.model_validate(row)
                for row in rows
                if row["evaluation_metadata"]["repeat_index"] == repeat
            ]
            for repeat in range(repeats)
        ]
    ).as_dict()


def summarize(root, name):
    archive = root / BASE / name
    protocol = json.loads((archive / "protocol.json").read_text())
    for field in ("runner", "verifier", "prompt"):
        assert (
            hashlib.sha256((root / protocol[field + "_file"]).read_bytes()).hexdigest()
            == (protocol[field + "_sha256"])
        )
    canonical, mutated = load_cases(root)
    selected = (
        [case for case in canonical if case.case_id == "canonical-racecond-018"]
        if protocol["study"] == "recovery-repeats"
        else canonical + mutated
    )
    ids = [case.case_id for case in selected]
    assert ids == protocol["selected_case_ids"]
    assert build_input_identity(selected) == protocol["input_identity"]
    repeats = protocol["repeats"]
    assert repeats == (3 if protocol["study"] == "recovery-repeats" else 1)
    expected = {(case_id, repeat) for case_id in ids for repeat in range(repeats)}
    rows, outcomes, requests = [], [], 0
    recorded_batches = []
    for planned in protocol["batches"]:
        bundle = archive / planned["directory"]
        if not bundle.exists():
            continue
        verify_bundle(bundle, kind="llm-pilot")
        manifest = json.loads((bundle / "manifest.json").read_text())
        assert manifest["selected_case_ids"] == planned["case_ids"]
        assert manifest["commit_sha"] == protocol["source_commit"]
        assert manifest["model_id"] == protocol["model"]
        assert manifest["prompt_hash"] == protocol["prompt_sha256"]
        config = planned["config"]
        for key in (
            "repeats",
            "budget",
            "output_mode",
            "provider_require_parameters",
            "temperature",
        ):
            assert manifest[key] == config[key]
        assert config["budget"]["max_retries_per_case"] == 0
        batch_rows = json_lines(bundle / "records.jsonl")
        batch_outcomes = json_lines(bundle / "outcomes.jsonl")
        batch_keys = {(row["case_id"], row["repeat_index"]) for row in batch_outcomes}
        assert len(batch_outcomes) == len(batch_keys) == len(planned["case_ids"]) * repeats
        assert batch_keys == {
            (case_id, repeat) for case_id in planned["case_ids"] for repeat in range(repeats)
        }
        assert manifest["successful"] == len(batch_rows)
        statuses = Counter(row["status"] for row in batch_outcomes)
        assert manifest["failed"] == statuses["failed"]
        assert manifest["not_run"] == statuses["not_run"]
        count = manifest["counters"]["physical_dispatches"]
        assert 0 <= count <= config["budget"]["max_requests"]
        assert manifest["coverage_sufficient"] == (len(batch_rows) == len(batch_outcomes))
        recomputed = (
            stability(batch_rows, repeats)
            if repeats > 1 and statuses["success"] == (len(batch_outcomes))
            else {}
        )
        assert manifest["stability"] == recomputed
        requests += count
        rows.extend(batch_rows)
        outcomes.extend(batch_outcomes)
        recorded_batches.append(planned["directory"])
    outcome_keys = {(row["case_id"], row["repeat_index"]) for row in outcomes}
    row_keys = {(row["case_id"], row["evaluation_metadata"]["repeat_index"]) for row in rows}
    assert len(outcomes) == len(outcome_keys) and outcome_keys <= expected
    assert len(rows) == len(row_keys)
    assert row_keys == {
        (row["case_id"], row["repeat_index"]) for row in outcomes if row["status"] == "success"
    }
    targets = {case.case_id: case for case in selected}
    for row in rows:
        case = targets[row["case_id"]]
        assert row["expected_decision"] == case.expected_decision
        assert row["correct"] == (row["decision"] == case.expected_decision)
        assert row["case_kind"] == case.kind
        assert row["parent_id"] == case.parent_id and row["operator"] == case.operator
        assert row["expected_dimensions"] == {}  # Existing pilot omits dimension targets.
    assert 0 <= requests <= protocol["max_requests"]
    statuses = Counter(row["status"] for row in outcomes)
    full = len(rows) == len(expected)
    result = {
        "study": protocol["study"],
        "planned_cases": len(ids),
        "repeats": repeats,
        "planned_evaluations": len(expected),
        "physical_requests": requests,
        "valid_responses": len(rows),
        "failed_evaluations": statuses["failed"],
        "not_run_in_batches": statuses["not_run"],
        "unstarted_evaluations": [
            {"case_id": case_id, "repeat_index": repeat}
            for case_id, repeat in sorted(expected - outcome_keys)
        ],
        "complete_success_coverage": full,
        "recorded_batches": recorded_batches,
        "authored_target_matches": sum(row["correct"] for row in rows),
        "decision_counts": dict(Counter(row["decision"] for row in rows)),
        "failure_counts": dict(
            Counter(
                row.get("detail") or row["error_kind"]
                for row in outcomes
                if row["status"] == ("failed")
            )
        ),
        "disagreements": [
            {key: row[key] for key in ("case_id", "expected_decision", "decision")}
            | {"repeat_index": row["evaluation_metadata"]["repeat_index"]}
            for row in rows
            if not row["correct"]
        ],
        "protocol_sha256": hashlib.sha256((archive / "protocol.json").read_bytes()).hexdigest(),
    }
    if protocol["study"] == "recovery-repeats":
        result["recovery_stability"] = stability(rows, 3) if full else None
        result["combined_60_stability"] = None
        result["per_case"] = [
            {
                "case_id": case_id,
                "decisions": [row["decision"] for row in rows if row["case_id"] == case_id],
                "confidences": [row["confidence"] for row in rows if row["case_id"] == case_id],
            }
            for case_id in ids
        ]
        if full:
            prior = root / BASE / "nemotron-repeat-01"
            assert (
                hashlib.sha256((prior / "protocol.json").read_bytes()).hexdigest()
                == (protocol["prior_protocol_sha256"])
            )
            verify_bundle(prior / "bundle", kind="llm-pilot")
            old = json_lines(prior / "bundle/records.jsonl")
            old_manifest = json.loads((prior / "bundle/manifest.json").read_text())
            assert old_manifest["coverage_sufficient"] and len(old) == 30
            assert old_manifest["model_id"] == protocol["model"]
            assert old_manifest["prompt_hash"] == protocol["prompt_sha256"]
            assert {row["case_id"] for row in old} == {case.case_id for case in canonical[:10]}
            assert (
                len({(r["case_id"], r["evaluation_metadata"]["repeat_index"]) for r in old}) == 30
            )
            remaining = root / BASE / "nemotron-repeat-remaining-01"
            assert (
                hashlib.sha256((remaining / "protocol.json").read_bytes()).hexdigest()
                == (protocol["remaining_protocol_sha256"])
            )
            original_summary = summarize_original(root, "nemotron-repeat-remaining-01")
            assert original_summary["physical_requests"] == 150
            assert original_summary["valid_responses"] == 149
            retained = []
            for path in sorted(remaining.glob("batch-*/records.jsonl")):
                retained.extend(json_lines(path))
            replacement_ids = set(ids)
            excluded = [row for row in retained if row["case_id"] in replacement_ids]
            retained = [row for row in retained if row["case_id"] not in replacement_ids]
            assert len(excluded) == 2 and len(retained) == 147
            matrix = old + retained + rows
            matrix_keys = {
                (row["case_id"], row["evaluation_metadata"]["repeat_index"]) for row in matrix
            }
            assert len(matrix) == len(matrix_keys) == 180
            assert matrix_keys == {
                (case.case_id, repeat) for case in canonical for repeat in range(3)
            }
            result["combined_60_stability"] = stability(matrix, 3)
            result["combined_matrix_target_matches"] = sum(row["correct"] for row in matrix)
            result["original_valid_observations_retained_outside_matrix"] = len(excluded)
            result["combined_per_case"] = [
                {
                    "case_id": case.case_id,
                    "decisions": [
                        row["decision"] for row in matrix if row["case_id"] == case.case_id
                    ],
                    "confidences": [
                        row["confidence"] for row in matrix if row["case_id"] == case.case_id
                    ],
                }
                for case in canonical
            ]
    else:
        records = [CaseRecord.model_validate(row) for row in rows]
        result["case_kind_counts"] = dict(Counter(row["case_kind"] for row in rows))
        result["operator_results"] = {
            operator: {
                "valid": sum(row["operator"] == operator for row in rows),
                "matches": sum(row["correct"] for row in rows if row["operator"] == operator),
            }
            for operator in sorted({row["operator"] for row in rows if row["operator"]})
        }
        result["metrics"] = asdict(compute_metrics(records, "llm-json")) if full else None
    stored = archive / "summary.json"
    if stored.exists():
        assert json.loads(stored.read_text()) == result
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=["nemotron-repeat-recovery-01", "nemotron-mutations-02"])
    args = parser.parse_args()
    print(json.dumps(summarize(Path(__file__).resolve().parents[2], args.name), indent=2))


if __name__ == "__main__":
    main()
