"""Explicit-dispatch, bounded Nemotron followups; freezes both protocols before calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from verify_nemotron_completion_20261004 import BASE, load_cases, summarize

from sloplab.evaluators.llm.adapter import HttpLLMClient, LlmEvaluator
from sloplab.evaluators.llm.failures import BudgetExhausted, DeadlineExceeded
from sloplab.experiments.bundle import verify_bundle
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.input_identity import build_input_identity
from sloplab.experiments.pilot import build_pilot_client_chain, run_llm_pilot
from sloplab.experiments.runner import current_commit_sha

MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def free_catalog():
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        catalog = next(model for model in json.load(response)["data"] if model["id"] == MODEL)
    with urllib.request.urlopen(
        "https://openrouter.ai/api/v1/models/" + MODEL + "/endpoints", timeout=30
    ) as response:
        endpoints = json.load(response)["data"]["endpoints"]
    assert endpoints and "structured_outputs" in catalog["supported_parameters"]
    for entry in [catalog, *endpoints]:
        assert all(
            key in entry["pricing"] and float(entry["pricing"][key]) == 0
            for key in ("prompt", "completion")
        ), "Nonzero or missing route pricing; no dispatch authorized"
        assert float(entry["pricing"].get("request", "0")) == 0
    return catalog, endpoints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch", action="store_true")
    args = parser.parse_args()
    if not args.dispatch:
        parser.exit(message="No requests made. Explicit --dispatch is required.\n")
    root = Path.cwd()
    assert os.environ.get("OPENROUTER_API_KEY"), "OpenRouter key unavailable"
    canonical, mutated = load_cases(root)
    studies = [
        (
            "nemotron-repeat-recovery-01",
            "recovery-repeats",
            [case for case in canonical if case.case_id == "canonical-racecond-018"],
            3,
        ),
        ("nemotron-mutations-02", "mutations", canonical + mutated, 1),
    ]
    assert all(not (root / BASE / name).exists() for name, _, _, _ in studies), (
        "Existing archive; refusing to rerun or overwrite"
    )
    catalog, endpoints = free_catalog()
    protocols = {}
    for name, study, selected, repeats in studies:
        batches = []
        for offset in range(0, len(selected), 10):
            count = min(10, len(selected) - offset)
            config = LLMPilotConfig.model_validate(
                {
                    "name": name,
                    "suite": {
                        "config_path": "benchmarks/suites/v1-core.yaml",
                        "corpus_root": "corpus",
                    },
                    "base_seed": 20260825,
                    "repeats": repeats,
                    "case_offset": offset,
                    "max_cases": count,
                    "model_env": "SLOPLAB_LLM_MODEL",
                    "endpoint_env": "SLOPLAB_LLM_ENDPOINT",
                    "api_key_env": "OPENROUTER_API_KEY",
                    "output_mode": "json_schema",
                    "provider_require_parameters": True,
                    "temperature": 0,
                    "prompt_file": "experiments/prompts/triage-v1.md",
                    "budget": {
                        "max_requests": count * repeats,
                        "request_timeout_s": 60,
                        "max_retries_per_case": 0,
                        "min_interval_ms": 3100,
                        "deadline_s": count * repeats * 60 + 100,
                    },
                }
            )
            batches.append(
                {
                    "directory": f"batch-{offset:03d}",
                    "case_ids": [case.case_id for case in selected[offset : offset + count]],
                    "config": config.model_dump(),
                }
            )
        protocol = {
            "registered_at": datetime.now(UTC).isoformat(),
            "study": study,
            "source_commit": current_commit_sha(root),
            "model": MODEL,
            "endpoint": ENDPOINT,
            "catalog": catalog,
            "endpoints": endpoints,
            "repeats": repeats,
            "max_requests": len(selected) * repeats,
            "global_max_requests": 450,
            "prior_physical_requests": 150,
            "authorization": (
                "User approved at most three supplemental free calls and mutation completion"
            ),
            "remaining_protocol_sha256": hashlib.sha256(
                (root / BASE / "nemotron-repeat-remaining-01/protocol.json").read_bytes()
            ).hexdigest(),
            "selected_case_ids": [case.case_id for case in selected],
            "input_identity": build_input_identity(selected),
            "batches": batches,
            "runner_file": "experiments/scripts/nemotron_completion_20261004.py",
            "verifier_file": "experiments/scripts/verify_nemotron_completion_20261004.py",
            "prompt_file": "experiments/prompts/triage-v1.md",
            "prior_protocol_sha256": hashlib.sha256(
                (root / BASE / "nemotron-repeat-01/protocol.json").read_bytes()
            ).hexdigest(),
            "selection_rule": (
                "Three new observations for the single operationally incomplete case; "
                "original two successes and failure preserved outside the coverage-normalized matrix"
            )
            if repeats == 3
            else ("All 60 canonical controls then all 237 existing derived cases; suite order"),
            "stop_policy": (
                "Stop both studies after HTTP 401/402/403/404/429 or changed route pricing"
            ),
            "mutation_gate": (
                "Require complete replacement block and <=6/60 flipped cases "
                "in coverage-normalized matrix"
            ),
            "limitations": [
                "Public synthetic authored targets; not independent real-world accuracy",
                "No provider decoding seed; base_seed is benchmark provenance only",
                "Mutation study is single-observation with fresh canonical parent controls",
                "Matrix uses prior first-ten repeats, 49 complete remaining cases, "
                "and a fresh three-observation replacement block for racecond-018; "
                "original two successes are retained outside that matrix",
                "No Jev, raw responses, automatic retries or target changes",
                "Response-level usage/cost fields are not retained",
                "Dimension-error metrics undefined: existing pilot omits dimensional targets",
            ],
        }
        for field in ("runner", "verifier", "prompt"):
            protocol[field + "_sha256"] = hashlib.sha256(
                (root / protocol[field + "_file"]).read_bytes()
            ).hexdigest()
        protocols[name] = protocol
        archive = root / BASE / name
        archive.mkdir(parents=True)
        (archive / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    print(
        "Registered continuation: 3 replacement + 297 mutation/control; prior 150, total cap 450.",
        flush=True,
    )

    class ObservedClient(HttpLLMClient):
        started = 0
        halted = False
        last_start = None
        stop_reason = None

        def complete(self, prompt):
            if self.halted or self.started >= 300:
                raise BudgetExhausted("Registered global stop policy")
            if self.last_start is not None:
                wait = max(0, 3.1 - (time.monotonic() - self.last_start))
                if self._deadline_monotonic is not None and time.monotonic() + wait >= (
                    self._deadline_monotonic
                ):
                    raise DeadlineExceeded("Cross-batch pacing would exceed deadline")
                time.sleep(wait)
            if (
                self._deadline_monotonic is not None
                and time.monotonic() >= self._deadline_monotonic
            ):
                raise DeadlineExceeded("Deadline before observed dispatch")
            self.started += 1
            self.last_start = time.monotonic()
            print(f"Dispatch {150 + self.started}/450", flush=True)
            try:
                return super().complete(prompt)
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 402, 403, 404, 429}:
                    self.halted = True
                    self.stop_reason = f"http.{exc.code}"
                raise
            except (BudgetExhausted, DeadlineExceeded):
                self.started -= 1
                raise

    http = ObservedClient(
        model=MODEL,
        api_key_env="OPENROUTER_API_KEY",
        endpoint=ENDPOINT,
        timeout_s=60,
        output_mode="json_schema",
        provider_require_parameters=True,
        temperature=0,
    )
    counted = 0
    for name, study, selected, _repeats in studies:
        archive = root / BASE / name
        if study == "mutations" and not http.halted:
            repeat_summary = summarize(root, studies[0][0])
            combined = repeat_summary["combined_60_stability"]
            if not repeat_summary["complete_success_coverage"] or combined["flipped_cases"] > 6:
                http.halted = True
                http.stop_reason = "mutation-gate-incomplete-replacement-or-high-flip-rate"
        for batch in protocols[name]["batches"]:
            if http.halted:
                break
            try:
                checked_catalog, checked_endpoints = free_catalog()
            except Exception as exc:
                http.halted = True
                http.stop_reason = f"route-preflight-{type(exc).__name__}"
                break
            (archive / (batch["directory"] + "-route-check.json")).write_text(
                json.dumps(
                    {
                        "checked_at": datetime.now(UTC).isoformat(),
                        "catalog": checked_catalog,
                        "endpoints": checked_endpoints,
                    },
                    indent=2,
                )
                + "\n"
            )
            config = LLMPilotConfig.model_validate(batch["config"])
            client = build_pilot_client_chain(
                http, min_interval_ms=3100, max_requests=config.budget.max_requests
            )
            evaluator = LlmEvaluator(client=client, enabled=True, max_retries=0)
            result = run_llm_pilot(
                config, evaluator, selected, root, archive / batch["directory"], model_id=MODEL
            )
            verify_bundle(archive / batch["directory"], kind="llm-pilot")
            manifest = json.loads(result.manifest_path.read_text())
            counted += manifest["counters"]["physical_dispatches"]
            assert counted == http.started <= 300
            print(
                f"{name} {batch['directory']}: {result.successful} valid, "
                f"{result.failed_evaluations} failed, {result.not_run} not run.",
                flush=True,
            )
        summary = summarize(root, name)
        (archive / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (archive / "execution.json").write_text(
            json.dumps(
                {
                    "finished_at": datetime.now(UTC).isoformat(),
                    "stop_reason": http.stop_reason,
                    "global_physical_requests": 150 + http.started,
                },
                indent=2,
            )
            + "\n"
        )
        print(
            json.dumps(
                {
                    key: value
                    for key, value in summary.items()
                    if key
                    not in {
                        "per_case",
                        "combined_per_case",
                        "disagreements",
                        "unstarted_evaluations",
                    }
                },
                indent=2,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
