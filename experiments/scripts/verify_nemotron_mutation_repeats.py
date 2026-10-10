"""Independent offline replay for fresh Nemotron mutation repeats. Never dispatches."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from verify_nemotron_followups_20261004 import load_cases

from sloplab.experiments.bundle import verify_bundle
from sloplab.experiments.input_identity import build_input_identity
from sloplab.experiments.runner import current_commit_sha
from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import compute_metrics

PRIOR = "experiments/results/llm-pilot/2026-10-04/nemotron-mutations-02/protocol.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def loads(text):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=unique)


def read(path):
    return loads(path.read_text())


def is_zero_price(value):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return False
    return number.is_finite() and number == 0


def validate_protocol(root, protocol, cases=None):
    require(protocol["schema_version"] == "nemotron-mutation-repeats-v1", "Unknown schema")
    require(protocol["model"] == "nvidia/nemotron-3-super-120b-a12b:free", "Wrong model")
    require(
        protocol["endpoint"] == "https://openrouter.ai/api/v1/chat/completions", "Wrong endpoint"
    )
    require(protocol["max_requests"] == 891 and protocol["repeats"] == 3, "Wrong budget")
    require(protocol["source_commit"] == current_commit_sha(root), "Source commit changed")
    prior = read(root / PRIOR)
    expected_paths = {str(p.relative_to(root)) for p in root.glob("src/sloplab/**/*.py")}
    expected_paths.update(
        {
            "experiments/scripts/nemotron_mutation_repeats.py",
            "experiments/scripts/verify_nemotron_mutation_repeats.py",
            "experiments/scripts/verify_nemotron_followups_20261004.py",
            "uv.lock",
            "pyproject.toml",
            prior["prompt_file"],
            PRIOR,
        }
    )
    require(set(protocol["source_sha256"]) == expected_paths, "Source inventory changed")
    for relative, digest in protocol["source_sha256"].items():
        require(sha(root / relative) == digest, f"Source changed: {relative}")
    if cases is None:
        canonical, mutations = load_cases(root)
        cases = canonical + mutations
    ids = [c.case_id for c in cases]
    require(protocol["selected_case_ids"] == ids == prior["selected_case_ids"], "Selection changed")
    require(
        protocol["input_identity"] == build_input_identity(cases) == prior["input_identity"],
        "Input identities changed",
    )
    expected = []
    for repeat in range(3):
        for offset in range(0, 297, 10):
            count = min(10, 297 - offset)
            config = json.loads(json.dumps(prior["batches"][0]["config"]))
            config.update(
                name="nemotron-mutation-repeats", case_offset=offset, max_cases=count, repeats=1
            )
            config["budget"].update(max_requests=count, deadline_s=count * 60 + 100)
            expected.append(
                {
                    "directory": f"r{repeat}-b{offset // 10 + 1:02d}",
                    "repeat_index": repeat,
                    "case_ids": ids[offset : offset + count],
                    "config": config,
                }
            )
    require(protocol["batches"] == expected, "Batch plan/config changed")
    return cases


def analyze(cases, rows):
    """rows keyed by (case_id, global repeat); missing rows never become decisions."""
    stability = {}
    for kind in ("canonical", "mutated"):
        selected = [c for c in cases if c.kind == kind]
        details = []
        operators = {}
        for case in selected:
            decisions = [
                rows[(case.case_id, r)]["decision"] if (case.case_id, r) in rows else None
                for r in range(3)
            ]
            complete = all(d is not None for d in decisions)
            changed = len(set(decisions)) > 1 if complete else None
            details.append(
                {
                    "case_id": case.case_id,
                    "operator": case.operator,
                    "decisions": decisions,
                    "complete": complete,
                    "changed": changed,
                }
            )
            key = case.operator or "canonical"
            counts = operators.setdefault(key, {"eligible": 0, "complete": 0, "changed": 0})
            counts["eligible"] += 1
            counts["complete"] += int(complete)
            counts["changed"] += int(changed is True)
        complete_count = sum(d["complete"] for d in details)
        changed_count = sum(d["changed"] is True for d in details)
        stability[kind] = {
            "eligible": len(selected),
            "complete": complete_count,
            "incomplete": len(selected) - complete_count,
            "unanimous": complete_count - changed_count,
            "changed": changed_count,
            "by_operator": operators,
            "per_case": details,
        }
    by_id = {c.case_id: c for c in cases}
    repeats = []
    for repeat in range(3):
        current = [rows[(c.case_id, repeat)] for c in cases if (c.case_id, repeat) in rows]
        eligible = [
            c
            for c in cases
            if c.kind == "mutated" and c.expected_decision == by_id[c.parent_id].expected_decision
        ]
        paired = [
            c for c in eligible if (c.case_id, repeat) in rows and (c.parent_id, repeat) in rows
        ]
        drift = sum(
            rows[(c.case_id, repeat)]["decision"] != rows[(c.parent_id, repeat)]["decision"]
            for c in paired
        )
        repeats.append(
            {
                "repeat_index": repeat,
                "valid": len(current),
                "target_agreement": {
                    kind: {
                        "valid": sum(row["case_kind"] == kind for row in current),
                        "matches": sum(
                            row["correct"] for row in current if row["case_kind"] == kind
                        ),
                    }
                    for kind in ("canonical", "mutated")
                },
                "decision_preserving_drift": {
                    "eligible": len(eligible),
                    "paired": len(paired),
                    "missing_pairs": len(eligible) - len(paired),
                    "changed": drift,
                },
                "metrics": asdict(
                    compute_metrics([CaseRecord.model_validate(row) for row in current], "llm-json")
                )
                if len(current) == len(cases)
                else None,
            }
        )
    return {"stability": stability, "per_repeat": repeats}


def replay(root, archive):
    protocol_path = archive / "protocol.json"
    protocol = read(protocol_path)
    cases = validate_protocol(root, protocol)
    targets = {c.case_id: c for c in cases}
    start = read(archive / "execution-started.json")
    require(start["protocol_sha256"] == sha(protocol_path), "Registered protocol changed")
    execution = read(archive / "execution.json")
    rows, statuses, requests = {}, Counter(), 0
    missing, saw_gap = [], False
    non_dispatch_failures = 0
    terminal_http = None
    allowed = {"protocol.json", "execution-started.json", "execution.json", "summary.json"}
    for batch in protocol["batches"]:
        name = batch["directory"]
        allowed.update({name, name + "-route.json"})
        bundle = archive / name
        repeat = batch["repeat_index"]
        if not bundle.exists():
            saw_gap = True
            missing.extend(
                {
                    "case_id": c,
                    "repeat_index": repeat,
                    "status": "not_run",
                    "reason": "batch_not_started",
                }
                for c in batch["case_ids"]
            )
            statuses["not_run"] += len(batch["case_ids"])
            continue
        require(not saw_gap, "Non-prefix batch execution")
        require(terminal_http is None, "Batch dispatched after HTTP halt")
        route = read(archive / (name + "-route.json"))
        # Price checks are recomputed offline from retained catalog observations.
        require(
            route["catalog"]["id"] == protocol["model"] and route["endpoints"],
            "Wrong or missing route",
        )
        for entry in [route["catalog"], *route["endpoints"]]:
            pricing = entry.get("pricing")
            require(
                isinstance(pricing, dict) and {"prompt", "completion"} <= pricing.keys(),
                "Missing prices",
            )
            require(all(is_zero_price(v) for v in pricing.values()), "Nonzero route price")
            require(
                {"response_format", "structured_outputs"}
                <= set(entry.get("supported_parameters", [])),
                "Unsupported route",
            )
        verify_bundle(bundle, kind="llm-pilot")
        manifest = read(bundle / "manifest.json")
        config = batch["config"]
        for key in (
            "budget",
            "repeats",
            "case_offset",
            "output_mode",
            "provider_require_parameters",
            "temperature",
            "base_seed",
            "model_env",
        ):
            require(manifest[key] == config[key], f"Manifest config mismatch: {key}")
        require(manifest["commit_sha"] == protocol["source_commit"], "Wrong source commit")
        require(manifest["model_id"] == protocol["model"], "Wrong model identity")
        require(
            manifest["prompt_hash"] == protocol["source_sha256"][config["prompt_file"]],
            "Wrong prompt",
        )
        require(manifest["selected_case_ids"] == batch["case_ids"], "Wrong batch selection")
        require(
            manifest["effective_max_requests"] == config["budget"]["max_requests"],
            "Wrong effective cap",
        )
        outcomes = [loads(line) for line in (bundle / "outcomes.jsonl").read_text().splitlines()]
        records = [loads(line) for line in (bundle / "records.jsonl").read_text().splitlines()]
        keys = [(row["case_id"], row["repeat_index"]) for row in outcomes]
        require(
            len(keys) == len(set(keys)) and set(keys) == {(c, 0) for c in batch["case_ids"]},
            "Duplicate/missing/local-repeat outcome",
        )
        counts = Counter(row["status"] for row in outcomes)
        require(set(counts) <= {"success", "failed", "not_run"}, "Invalid outcome status")
        for key, status in (
            ("successful", "success"),
            ("failed", "failed"),
            ("not_run", "not_run"),
        ):
            require(manifest[key] == counts[status], "Outcome counts mismatch")
        physical = manifest["counters"]["physical_dispatches"]
        require(
            physical
            == counts["success"]
            + sum(
                row["status"] == "failed" and row.get("error_kind") not in {"budget", "deadline"}
                for row in outcomes
            )
            <= len(batch["case_ids"]),
            "Invalid physical dispatch count",
        )
        for outcome in outcomes:
            if terminal_http is not None:
                require(
                    outcome["status"] == "not_run"
                    or outcome.get("error_kind") in {"budget", "deadline"},
                    "Physical dispatch after HTTP halt",
                )
            if outcome.get("detail") in {"http.401", "http.402", "http.403", "http.404"}:
                terminal_http = outcome["detail"]
            elif outcome.get("error_kind") == "rate-limit":
                terminal_http = "http.429"
            if outcome["status"] == "failed" and outcome.get("error_kind") in {
                "budget",
                "deadline",
            }:
                non_dispatch_failures += 1
        requests += physical
        statuses.update(counts)
        record_keys = [
            (row["case_id"], row["evaluation_metadata"]["repeat_index"]) for row in records
        ]
        require(len(record_keys) == len(set(record_keys)), "Duplicate records")
        require(
            set(record_keys)
            == {(row["case_id"], 0) for row in outcomes if row["status"] == "success"},
            "Records/outcomes mismatch",
        )
        for row in records:
            CaseRecord.model_validate(row)
            case = targets[row["case_id"]]
            require(
                row["expected_decision"] == case.expected_decision
                and row["correct"] == (row["decision"] == case.expected_decision),
                "Target/correctness mismatch",
            )
            require(
                row["case_kind"] == case.kind
                and row["parent_id"] == case.parent_id
                and row["operator"] == case.operator
                and row["expected_dimensions"] == {},
                "Case linkage mismatch",
            )
            require(row["evaluator_name"] == "llm-json", "Wrong evaluator")
            # Preserve disk records. Global repeat identity belongs to this protocol.
            normalized = dict(
                row, evaluation_metadata=dict(row["evaluation_metadata"], repeat_index=repeat)
            )
            key = (case.case_id, repeat)
            require(key not in rows, "Duplicate global repeat record")
            rows[key] = normalized
        missing.extend(
            dict(row, repeat_index=repeat) for row in outcomes if row["status"] != "success"
        )
    require({p.name for p in archive.iterdir()} <= allowed, "Unexpected archive entries")
    require(requests == execution["physical_requests"] <= 891, "Global physical cap/count mismatch")
    require(sum(statuses.values()) == 891, "Coverage accounting mismatch")
    if terminal_http is not None:
        require(execution["stop_reason"] == terminal_http, "HTTP stop reason mismatch")
    result = {
        "protocol_sha256": sha(protocol_path),
        "physical_requests": requests,
        "planned": 891,
        "valid": len(rows),
        "failed": statuses["failed"],
        "non_dispatch_failures": non_dispatch_failures,
        "not_run": statuses["not_run"],
        "full_response_coverage": len(rows) == 891,
        "stop_reason": execution["stop_reason"],
        "missing_observations": missing,
        **analyze(cases, rows),
    }
    if (archive / "summary.json").exists():
        require(read(archive / "summary.json") == result, "Saved summary differs from replay")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(replay(root, args.archive), indent=2))


if __name__ == "__main__":
    main()
