"""Bounded, opt-in live repeat pilot; run from the repository root with --dispatch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from sloplab.evaluators.llm.adapter import HttpLLMClient, LlmEvaluator
from sloplab.evaluators.llm.failures import BudgetExhausted
from sloplab.experiments.bundle import verify_bundle
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.input_identity import build_input_identity
from sloplab.experiments.pilot import build_pilot_client_chain, run_llm_pilot
from sloplab.experiments.runner import current_commit_sha
from sloplab.scoring.harness import build_cases

MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
ARCHIVE = Path("experiments/results/llm-pilot/2026-10-04/nemotron-repeat-01")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch", action="store_true")
    args = parser.parse_args()
    if not args.dispatch:
        parser.exit(message="No requests made. Explicit --dispatch is required.\n")
    root = Path.cwd()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OpenRouter API key unavailable")
    if ARCHIVE.exists():
        raise RuntimeError("Study archive already exists; refusing to rerun or overwrite")
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        catalog = next(m for m in json.load(response)["data"] if m["id"] == MODEL)
    with urllib.request.urlopen(
        "https://openrouter.ai/api/v1/models/" + MODEL + "/endpoints", timeout=30
    ) as response:
        endpoints = json.load(response)["data"]["endpoints"]
    assert endpoints and "structured_outputs" in catalog["supported_parameters"]
    for entry in [catalog, *endpoints]:
        assert all(
            float(entry["pricing"].get(key, "0")) == 0
            for key in ("prompt", "completion", "request")
        ), "Nonzero route pricing: refusing dispatch"
    cases = [
        case
        for case in build_cases(
            root / "benchmarks/results/v1-core-example/suite-index.jsonl",
            root / "corpus",
            root / "benchmarks/results/v1-core-example",
        )
        if case.kind == "canonical"
    ]
    selected = cases[:10]
    assert len(cases) == 60 and len({case.case_id for case in selected}) == 10
    config = LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "nemotron-repeat-20261004",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 20260825,
            "repeats": 3,
            "max_cases": 10,
            "model_env": "SLOPLAB_LLM_MODEL",
            "endpoint_env": "SLOPLAB_LLM_ENDPOINT",
            "api_key_env": "OPENROUTER_API_KEY",
            "output_mode": "json_schema",
            "provider_require_parameters": True,
            "temperature": 0,
            "prompt_file": "experiments/prompts/triage-v1.md",
            "budget": {
                "max_requests": 30,
                "request_timeout_s": 60,
                "max_retries_per_case": 0,
                "min_interval_ms": 3100,
                "deadline_s": 1900,
            },
        }
    )
    protocol = {
        "registered_at": datetime.now(UTC).isoformat(),
        "source_commit": current_commit_sha(root),
        "model": MODEL,
        "endpoint": ENDPOINT,
        "catalog": catalog,
        "endpoints": endpoints,
        "selected_case_ids": [case.case_id for case in selected],
        "selection_rule": "First ten public canonical cases in the frozen suite order",
        "input_identity": build_input_identity(selected),
        "config": config.model_dump(),
        "runner_file": str(Path(__file__).resolve().relative_to(root)),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "prompt_sha256": hashlib.sha256((root / config.prompt_file).read_bytes()).hexdigest(),
        "stop_policy": "First HTTP 401/402/403/404/429 stops subsequent physical requests",
        "limitations": [
            "Selected ten-case operational pilot, not full-corpus repeat stability",
            "No provider decoding seed is set; base_seed describes benchmark provenance",
            "No mutation cases, Jev calls, target changes or raw responses",
            "Catalog prices checked; transport does not retain response-level billing",
        ],
    }
    ARCHIVE.mkdir(parents=True)
    (ARCHIVE / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    print("Registered 10 cases x 3 repeats; cap 30 requests, no retries.", flush=True)

    class ObservedClient(HttpLLMClient):
        started = 0
        halted = False

        def complete(self, prompt):
            if self.halted:
                raise BudgetExhausted("Registered access/rate-limit stop policy")
            self.started += 1
            print(f"Dispatch {self.started}/30", flush=True)
            try:
                return super().complete(prompt)
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 402, 403, 404, 429}:
                    self.halted = True
                raise

    http = ObservedClient(
        model=MODEL,
        api_key_env=config.api_key_env,
        endpoint=ENDPOINT,
        timeout_s=60,
        output_mode="json_schema",
        provider_require_parameters=True,
        temperature=0,
    )
    client = build_pilot_client_chain(http, min_interval_ms=3100, max_requests=30)
    evaluator = LlmEvaluator(client=client, enabled=True, max_retries=0)
    result = run_llm_pilot(config, evaluator, cases, root, ARCHIVE / "bundle", model_id=MODEL)
    verify_bundle(ARCHIVE / "bundle", kind="llm-pilot")
    manifest = json.loads(result.manifest_path.read_text())
    assert http.started == manifest["counters"]["physical_dispatches"] <= 30
    print(
        json.dumps(
            {key: manifest[key] for key in ("successful", "failed", "not_run", "stability")},
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
