"""Live LLM benchmark runner (manual, metered, never run by CI's default flows).

Wired to the committed pilot budget config
(``experiments/configs/llm-pilot-v0.2.yaml``):

- worst-case request count (``max_cases x repeats x (1 + retries)``) is validated
  against ``budget.max_requests`` BEFORE any network activity and the run is
  rejected when it would exceed the cap;
- every request passes through a counting client (hard budget stop) and a pacing
  client (minimum interval between requests; HTTP 429 Retry-After is honored);
- normalized records plus a provenance manifest (budget, request/error/timeout
  counters, prompt hash) are written next to the results file.

Usage (requires the SLOPLAB_LLM_API_KEY environment variable):

    python scripts/llm_bench.py [--max-cases 3] [--repeats 1] \
        [--out llm-bench-results.jsonl]

Stdout prints only counts and decisions - never API keys, raw model responses,
or rationale text.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sloplab.evaluators.llm.adapter import AdapterError, HttpLLMClient, LlmEvaluator  # noqa: E402
from sloplab.experiments.config import LLMPilotConfig  # noqa: E402
from sloplab.experiments.pilot import CountingClient, ThrottledClient, run_llm_pilot  # noqa: E402
from sloplab.experiments.runner import load_pilot_config  # noqa: E402
from sloplab.scoring.harness import build_cases  # noqa: E402

DEFAULT_CONFIG = REPO_ROOT / "experiments/configs/llm-pilot-v0.2.yaml"
DEFAULT_MAX_CASES = 3
DEFAULT_REPEATS = 1


def _worst_case_requests(max_cases: int, repeats: int, max_retries: int) -> int:
    return max_cases * repeats * (1 + max_retries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-cases", type=int, default=DEFAULT_MAX_CASES)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--suite-index",
        type=Path,
        default=REPO_ROOT / "benchmarks/results/v1-core-example/suite-index.jsonl",
    )
    parser.add_argument("--out", type=Path, default=Path("llm-bench-results.jsonl"))
    args = parser.parse_args(argv)

    model_env = os.environ.get("SLOPLAB_LLM_MODEL")
    endpoint = os.environ.get("SLOPLAB_LLM_ENDPOINT")
    if not model_env or not endpoint:
        print("error: set SLOPLAB_LLM_MODEL and SLOPLAB_LLM_ENDPOINT", file=sys.stderr)
        return 2
    if args.max_cases < 1 or args.repeats < 1:
        print("error: --max-cases and --repeats must be >= 1", file=sys.stderr)
        return 2

    try:
        config: LLMPilotConfig = load_pilot_config(args.config)
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    config.max_cases = args.max_cases
    config.repeats = args.repeats

    # Pre-flight budget rejection: refuse to start when the dispatch plan could
    # exceed the hard cap even if every evaluation exhausts its retries.
    worst_case = _worst_case_requests(
        config.max_cases or 0, config.repeats, config.budget.max_retries_per_case
    )
    print(
        f"plan: {config.max_cases} cases x {config.repeats} repeat(s), "
        f"worst-case {worst_case} requests incl. retries "
        f"(hard cap {config.budget.max_requests}, min interval "
        f"{config.budget.min_interval_ms} ms)"
    )
    if worst_case > config.budget.max_requests:
        print(
            f"error: requested plan can spend up to {worst_case} requests but the "
            f"budget caps at {config.budget.max_requests}; reduce --max-cases/--repeats",
            file=sys.stderr,
        )
        return 2

    try:
        http = HttpLLMClient(
            model=model_env,
            api_key_env=config.api_key_env,
            endpoint=endpoint,
        )
    except AdapterError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    throttled = ThrottledClient(http, min_interval_ms=config.budget.min_interval_ms)
    counting = CountingClient(throttled, max_requests=config.budget.max_requests)
    evaluator = LlmEvaluator(
        client=counting,
        max_retries=config.budget.max_retries_per_case,
        enabled=True,
    )

    cases = build_cases(
        args.suite_index,
        REPO_ROOT / "corpus",
        args.suite_index.parent,  # committed reference bundle holds the trees
    )
    canonical = [c for c in cases if c.kind == "canonical"]

    bundle_dir = args.out.parent / f"{args.out.stem}.bundle"
    result = run_llm_pilot(config, evaluator, canonical, REPO_ROOT, bundle_dir)
    shutil.copyfile(result.records_path, args.out)

    print(f"evaluated {result.evaluations_attempted} evaluations -> {args.out}")
    for line in args.out.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        state = "FAILED-EVAL" if record["evaluation_metadata"].get("failed") else record["decision"]
        repeat = record["evaluation_metadata"].get("repeat_index", 0)
        print(f"  {record['case_id']} (repeat {repeat}): {state}")
    print(f"failed evaluations: {result.failed_evaluations}/{result.evaluations_attempted}")
    print(
        "requests used: "
        f"{result.counters.get('requests', 0)} "
        f"(errors {result.counters.get('errors', 0)}, timeouts "
        f"{result.counters.get('timeouts', 0)}) | manifest: "
        f"{result.manifest_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
