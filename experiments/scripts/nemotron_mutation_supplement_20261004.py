"""Offline replay by default; --dispatch records the authorized missing-case supplement."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from nemotron_completion_20261004 import free_catalog
from verify_nemotron_completion_20261004 import BASE, json_lines, load_cases, summarize

from sloplab.evaluators.llm.adapter import HttpLLMClient, LlmEvaluator
from sloplab.experiments.bundle import verify_bundle
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.input_identity import build_input_identity
from sloplab.experiments.pilot import build_pilot_client_chain, run_llm_pilot
from sloplab.experiments.runner import current_commit_sha
from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import compute_metrics

NAME = "nemotron-mutation-supplement-01"


def original_data(root):
    original = root / BASE / "nemotron-mutations-02"
    summary = summarize(root, "nemotron-mutations-02")
    assert summary["physical_requests"] == 297 and not summary["unstarted_evaluations"]
    rows, outcomes = [], []
    for directory in summary["recorded_batches"]:
        rows.extend(json_lines(original / directory / "records.jsonl"))
        outcomes.extend(json_lines(original / directory / "outcomes.jsonl"))
    failures = [row for row in outcomes if row["status"] == "failed"]
    assert 1 <= len(failures) <= 3
    assert all(row["error_kind"] == "transport" for row in failures)
    missing_ids = {row["case_id"] for row in failures}
    canonical, mutated = load_cases(root)
    selected = [case for case in mutated if case.case_id in missing_ids]
    assert len(selected) == len(missing_ids) == len(failures)
    return original, rows, selected, canonical + mutated


def replay(root):
    archive = root / BASE / NAME
    protocol = json.loads((archive / "protocol.json").read_text())
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == protocol["script_sha256"]
    original, rows, selected, all_cases = original_data(root)
    assert (
        hashlib.sha256((original / "protocol.json").read_bytes()).hexdigest()
        == (protocol["original_protocol_sha256"])
    )
    assert build_input_identity(selected) == protocol["input_identity"]
    assert [case.case_id for case in selected] == protocol["selected_case_ids"]
    config = protocol["config"]
    assert config["repeats"] == 1 and config["budget"]["max_retries_per_case"] == 0
    assert config["budget"]["max_requests"] == len(selected) <= 3
    assert (
        hashlib.sha256((root / config["prompt_file"]).read_bytes()).hexdigest()
        == (protocol["prompt_sha256"])
    )
    bundle = archive / "bundle"
    verify_bundle(bundle, kind="llm-pilot")
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["selected_case_ids"] == protocol["selected_case_ids"]
    assert manifest["model_id"] == protocol["model"]
    assert manifest["commit_sha"] == protocol["source_commit"]
    assert manifest["prompt_hash"] == protocol["prompt_sha256"]
    for key in ("budget", "repeats", "output_mode", "temperature", "provider_require_parameters"):
        assert manifest[key] == config[key]
    extra = json_lines(bundle / "records.jsonl")
    outcomes = json_lines(bundle / "outcomes.jsonl")
    assert len(outcomes) == len(selected)
    assert {(row["case_id"], row["repeat_index"]) for row in outcomes} == {
        (case.case_id, 0) for case in selected
    }
    assert {(row["case_id"], row["evaluation_metadata"]["repeat_index"]) for row in extra} == {
        (row["case_id"], 0) for row in outcomes if row["status"] == "success"
    }
    assert len(extra) == manifest["successful"]
    statuses = Counter(row["status"] for row in outcomes)
    assert manifest["failed"] == statuses["failed"]
    assert manifest["not_run"] == statuses["not_run"]
    requests = manifest["counters"]["physical_dispatches"]
    assert 0 <= requests <= len(selected) <= 3 and 450 + requests <= 453
    combined = rows + extra
    targets = {case.case_id: case for case in all_cases}
    assert len(combined) == len({row["case_id"] for row in combined})
    for row in combined:
        case = targets[row["case_id"]]
        assert row["expected_decision"] == case.expected_decision
        assert row["correct"] == (row["decision"] == case.expected_decision)
        assert row["parent_id"] == case.parent_id and row["operator"] == case.operator
        assert row["case_kind"] == case.kind
        assert row["evaluation_metadata"]["repeat_index"] == 0
    full = len(combined) == 297
    if full:
        assert {row["case_id"] for row in combined} == set(targets)
    result = {
        "original_physical_requests": 297,
        "original_valid_responses": len(rows),
        "original_failed_evaluations": len(selected),
        "supplement_physical_requests": requests,
        "supplement_valid_responses": len(extra),
        "supplement_failed_evaluations": statuses["failed"],
        "combined_success_coverage": full,
        "combined_valid_responses": len(combined),
        "total_authorized_continuation_requests": 450 + requests,
        "selected_case_ids": protocol["selected_case_ids"],
        "case_kind_results": {
            kind: {
                "valid": sum(row["case_kind"] == kind for row in combined),
                "matches": sum(row["correct"] for row in combined if row["case_kind"] == kind),
            }
            for kind in ("canonical", "mutated")
        },
        "metrics": asdict(
            compute_metrics([CaseRecord.model_validate(row) for row in combined], "llm-json")
        )
        if full
        else None,
        "protocol_sha256": hashlib.sha256((archive / "protocol.json").read_bytes()).hexdigest(),
    }
    stored = archive / "summary.json"
    if stored.exists():
        assert json.loads(stored.read_text()) == result
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    archive = root / BASE / NAME
    if not args.dispatch:
        if archive.exists():
            print(json.dumps(replay(root), indent=2))
        else:
            print("No requests made; explicit --dispatch is required for a new supplement.")
        return
    assert not archive.exists(), "Existing supplement; refusing to overwrite or rerun"
    original, _, selected, _ = original_data(root)
    original_protocol = json.loads((original / "protocol.json").read_text())
    catalog, endpoints = free_catalog()
    config_data = original_protocol["batches"][0]["config"]
    config_data.update(name=NAME, case_offset=0, max_cases=len(selected), repeats=1)
    config_data["budget"].update(max_requests=len(selected), deadline_s=60 * len(selected) + 100)
    config = LLMPilotConfig.model_validate(config_data)
    protocol = {
        "registered_at": datetime.now(UTC).isoformat(),
        "source_commit": current_commit_sha(root),
        "model": original_protocol["model"],
        "endpoint": original_protocol["endpoint"],
        "catalog": catalog,
        "endpoints": endpoints,
        "config": config.model_dump(),
        "selected_case_ids": [case.case_id for case in selected],
        "input_identity": build_input_identity(selected),
        "script_file": str(Path(__file__).resolve().relative_to(root)),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "original_protocol_sha256": hashlib.sha256(
            (original / "protocol.json").read_bytes()
        ).hexdigest(),
        "prompt_sha256": hashlib.sha256((root / config.prompt_file).read_bytes()).hexdigest(),
        "authorization": "User approved at most three further free calls, total ceiling 453",
        "selection_rule": (
            "Every missing mutated case classified transport.error; one new observation each"
        ),
        "limitations": [
            "Original failure retained; supplement is a distinct later observation",
            "Metrics combine original fresh controls with supplemental child observations",
            "No provider decoding seed, exact response billing, or dimension-error metrics",
        ],
    }
    archive.mkdir(parents=True)
    (archive / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    http = HttpLLMClient(
        model=protocol["model"],
        endpoint=protocol["endpoint"],
        api_key_env=config.api_key_env,
        timeout_s=60,
        output_mode="json_schema",
        provider_require_parameters=True,
        temperature=0,
    )
    client = build_pilot_client_chain(http, min_interval_ms=3100, max_requests=len(selected))
    evaluator = LlmEvaluator(client=client, enabled=True, max_retries=0)
    print(f"Registered {len(selected)} new observation(s); no automatic retries.", flush=True)
    run_llm_pilot(config, evaluator, selected, root, archive / "bundle", model_id=protocol["model"])
    result = replay(root)
    (archive / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
