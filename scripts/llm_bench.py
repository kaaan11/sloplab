"""Live LLM benchmark runner (manual, metered, never run by CI's default flows).

Usage (requires the SLOPLAB_LLM_API_KEY environment variable):

    python scripts/llm_bench.py [--max-cases 3] [--out llm-bench-results.jsonl]

Evaluates the first N canonical cases of the committed v1-core example through the
strict-JSON adapter and writes full records to the output file. Stdout prints only
counts and decisions - never API keys, raw model responses, or rationale text.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sloplab.evaluators.llm.adapter import AdapterError, HttpLLMClient, LlmEvaluator  # noqa: E402
from sloplab.scoring.harness import build_cases, run_suite  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-cases", type=int, default=3)
    parser.add_argument(
        "--suite-index",
        type=Path,
        default=REPO_ROOT / "benchmarks/results/v1-core-example/suite-index.jsonl",
    )
    parser.add_argument("--out", type=Path, default=Path("llm-bench-results.jsonl"))
    args = parser.parse_args()

    model = os.environ.get("SLOPLAB_LLM_MODEL")
    endpoint = os.environ.get("SLOPLAB_LLM_ENDPOINT")
    if not model or not endpoint:
        print("error: set SLOPLAB_LLM_MODEL and SLOPLAB_LLM_ENDPOINT", file=sys.stderr)
        return 2

    try:
        client = HttpLLMClient(
            model=model,
            api_key_env="SLOPLAB_LLM_API_KEY",
            endpoint=endpoint,
        )
        evaluator = LlmEvaluator(client=client, enabled=True)
    except AdapterError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    cases = build_cases(args.suite_index, REPO_ROOT / "corpus", REPO_ROOT / "corpus")
    canonical = [c for c in cases if c.kind == "canonical"][: max(1, args.max_cases)]

    records = run_suite(evaluator, canonical)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.model_dump_json() + "\n")

    failed = sum(1 for r in records if r.evaluation_metadata.get("failed"))
    print(f"evaluated {len(records)} canonical cases -> {args.out}")
    for record in records:
        state = "FAILED-EVAL" if record.evaluation_metadata.get("failed") else record.decision.value
        print(f"  {record.case_id}: {state}")
    print(f"failed evaluations: {failed}/{len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
