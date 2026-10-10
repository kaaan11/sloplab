"""Prepare offline; dispatch only an explicitly budgeted, previously prepared archive.

Usage: python experiments/scripts/nemotron_mutation_repeats.py --prepare /tmp/study
Then: --dispatch /tmp/study --authorize-requests 891
Each bundle uses local repeat 0; protocol batch repeat_index defines the global repeat.
Archives are single-use. Interrupted executions are retained and cannot resume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from verify_nemotron_followups_20261004 import load_cases

from sloplab.evaluators.llm.adapter import HttpLLMClient, LlmEvaluator
from sloplab.evaluators.llm.failures import BudgetExhausted, DeadlineExceeded
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.input_identity import build_input_identity
from sloplab.experiments.pilot import build_pilot_client_chain, run_llm_pilot
from sloplab.experiments.runner import current_commit_sha

MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
CAP = 891
PRIOR = "experiments/results/llm-pilot/2026-10-04/nemotron-mutations-02/protocol.json"
RUNNER = "experiments/scripts/nemotron_mutation_repeats.py"
VERIFIER = "experiments/scripts/verify_nemotron_mutation_repeats.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, data):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(data, indent=2, allow_nan=False) + "\n")


def make_protocol(root):
    canonical, mutated = load_cases(root)
    cases = canonical + mutated
    prior = json.loads((root / PRIOR).read_text())
    identity = build_input_identity(cases)
    if identity != prior["input_identity"]:
        raise ValueError("Inputs differ from the historical frozen suite")
    batches = []
    for repeat in range(3):
        for offset in range(0, len(cases), 10):
            count = min(10, len(cases) - offset)
            config = LLMPilotConfig.model_validate(prior["batches"][0]["config"])
            config.name = "nemotron-mutation-repeats"
            config.case_offset, config.max_cases, config.repeats = offset, count, 1
            config.budget.max_requests = count
            config.budget.deadline_s = count * 60 + 100
            batches.append(
                {
                    "directory": f"r{repeat}-b{offset // 10 + 1:02d}",
                    "repeat_index": repeat,
                    "case_ids": [c.case_id for c in cases[offset : offset + count]],
                    "config": config.model_dump(),
                }
            )
    paths = sorted(root.glob("src/sloplab/**/*.py")) + [
        root / RUNNER,
        root / VERIFIER,
        root / "experiments/scripts/verify_nemotron_followups_20261004.py",
        root / "uv.lock",
        root / "pyproject.toml",
        root / prior["prompt_file"],
        root / PRIOR,
    ]
    return {
        "schema_version": "nemotron-mutation-repeats-v1",
        "prepared_at": datetime.now(UTC).isoformat(),
        "source_commit": current_commit_sha(root),
        "source_sha256": {str(p.relative_to(root)): digest(p) for p in paths},
        "model": MODEL,
        "endpoint": ENDPOINT,
        "max_requests": CAP,
        "repeats": 3,
        "selected_case_ids": [c.case_id for c in cases],
        "input_identity": identity,
        "batches": batches,
        "repeat_identity": "bundle local repeat 0 maps to protocol batch repeat_index",
        "analysis": {
            "primary": "mutation decisions differing across three valid fresh observations",
            "missingness": "report incomplete cases separately; never count failure as decision",
            "pairing": "fresh canonical parent with child in the same global repeat",
            "secondary": "authored-target agreement per repeat; canonical stability separately",
            "uncertainty": "no independent-sample confidence intervals",
        },
        "limitations": [
            "Public synthetic authored targets, not independent real-world validity",
            "No provider decoding seed or pinned provider/model version",
            "Three fixed-order suite passes; chronology and shared parents confound observations",
            "Historical observations and private adjudications do not relabel or fill this suite",
        ],
    }


def validate_routes(catalog, endpoints):
    if catalog.get("id") != MODEL or not endpoints:
        raise ValueError("Model unavailable")
    for entry in [catalog, *endpoints]:
        pricing = entry.get("pricing", {})
        if not {"prompt", "completion"} <= pricing.keys():
            raise ValueError("Missing price")
        if any(not Decimal(str(v)).is_finite() or Decimal(str(v)) != 0 for v in pricing.values()):
            raise ValueError("Nonzero or invalid route pricing")
        if not {"response_format", "structured_outputs"} <= set(
            entry.get("supported_parameters", [])
        ):
            raise ValueError("Route lacks structured response support")


def free_routes():
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        catalog = next(m for m in json.load(response)["data"] if m["id"] == MODEL)
    with urllib.request.urlopen(
        "https://openrouter.ai/api/v1/models/" + MODEL + "/endpoints", timeout=30
    ) as response:
        endpoints = json.load(response)["data"]["endpoints"]
    validate_routes(catalog, endpoints)
    return {"checked_at": datetime.now(UTC).isoformat(), "catalog": catalog, "endpoints": endpoints}


class StudyTransport:
    """One cumulative physical cap, halt state and pacing clock across all bundles."""

    def __init__(self, inner, cap=CAP, interval=3.1):
        self.inner, self.cap, self.interval = inner, cap, interval
        self.started = 0
        self.last_start = None
        self.deadline = None
        self.stop_reason = None

    def set_deadline(self, deadline):
        self.deadline = deadline
        self.inner.set_deadline(deadline)

    def complete(self, prompt):
        if self.stop_reason or self.started >= self.cap:
            raise BudgetExhausted("Cumulative study cap or stop policy")
        wait = (
            0
            if self.last_start is None
            else max(0, self.interval - (time.monotonic() - self.last_start))
        )
        if self.deadline is not None and time.monotonic() + wait >= self.deadline:
            raise DeadlineExceeded("Cross-batch pacing exceeds deadline")
        if wait:
            time.sleep(wait)
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise DeadlineExceeded("Deadline before dispatch")
        self.started += 1
        self.last_start = time.monotonic()
        try:
            return self.inner.complete(prompt)
        except (BudgetExhausted, DeadlineExceeded):
            self.started -= 1
            raise
        except Exception as exc:
            if getattr(exc, "code", None) in {401, 402, 403, 404, 429}:
                self.stop_reason = f"http.{exc.code}"
            raise


def execute(root, archive, protocol, transport, route_check=free_routes):
    """Single-use execution; the started marker also rejects interrupted reruns."""
    from verify_nemotron_mutation_repeats import replay, validate_protocol

    if (archive / "execution-started.json").exists():
        raise FileExistsError("Archive already started; refusing rerun/resume")
    if {p.name for p in archive.iterdir()} != {"protocol.json"}:
        raise ValueError("Prepared archive must contain only protocol.json")
    if json.loads((archive / "protocol.json").read_text()) != protocol:
        raise ValueError("In-memory protocol differs from prepared archive")
    if transport.cap != CAP or transport.started or transport.interval < 3.1:
        raise ValueError("Expected unused transport with the registered cap and pacing")
    cases = validate_protocol(root, protocol)
    write_new(
        archive / "execution-started.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "protocol_sha256": digest(archive / "protocol.json"),
        },
    )
    try:
        for batch in protocol["batches"]:
            if transport.stop_reason:
                break
            # Use the frozen in-memory cases; recheck code/prompt hashes each batch.
            validate_protocol(root, protocol, cases=cases)
            try:
                route = route_check()
                validate_routes(route["catalog"], route["endpoints"])
            except Exception as exc:
                transport.stop_reason = f"route-preflight-{type(exc).__name__}"
                break
            write_new(archive / (batch["directory"] + "-route.json"), route)
            config = LLMPilotConfig.model_validate(batch["config"])
            client = build_pilot_client_chain(
                transport, min_interval_ms=3100, max_requests=config.budget.max_requests
            )
            evaluator = LlmEvaluator(client=client, enabled=True, max_retries=0)
            run_llm_pilot(
                config, evaluator, cases, root, archive / batch["directory"], model_id=MODEL
            )
            print(f"{batch['directory']}: {transport.started}/{CAP} requests", flush=True)
    except BaseException:
        transport.stop_reason = transport.stop_reason or "execution-interrupted"
        raise
    finally:
        write_new(
            archive / "execution.json",
            {
                "finished_at": datetime.now(UTC).isoformat(),
                "physical_requests": transport.started,
                "stop_reason": transport.stop_reason,
            },
        )
    summary = replay(root, archive)
    write_new(archive / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--prepare", type=Path)
    action.add_argument("--dispatch", type=Path)
    parser.add_argument("--authorize-requests", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if args.dispatch:
        if args.authorize_requests != CAP:
            parser.error("Dispatch requires --authorize-requests 891")
        archive = args.dispatch.resolve()
        # Check before constructing a client or making catalog calls.
        if (archive / "execution-started.json").exists():
            parser.error("Archive already started; refusing rerun/resume")
        protocol = json.loads((archive / "protocol.json").read_text())
        from verify_nemotron_mutation_repeats import validate_protocol

        validate_protocol(root, protocol)
        if not os.environ.get("OPENROUTER_API_KEY"):
            parser.error("OPENROUTER_API_KEY unavailable")
        http = HttpLLMClient(
            model=MODEL,
            endpoint=ENDPOINT,
            api_key_env="OPENROUTER_API_KEY",
            timeout_s=60,
            output_mode="json_schema",
            provider_require_parameters=True,
            temperature=0,
        )
        result = execute(root, archive, protocol, StudyTransport(http))
        print(json.dumps(result, indent=2))
    else:
        protocol = make_protocol(root)
        from verify_nemotron_mutation_repeats import validate_protocol

        validate_protocol(root, protocol)
        if args.prepare:
            args.prepare.mkdir(parents=True, exist_ok=False)
            write_new(args.prepare / "protocol.json", protocol)
        print(
            json.dumps(
                {
                    "mode": "offline",
                    "cases": len(protocol["selected_case_ids"]),
                    "repeats": 3,
                    "batches": len(protocol["batches"]),
                    "max_requests": CAP,
                    "prepared_archive": str(args.prepare) if args.prepare else None,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
