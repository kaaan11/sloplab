# LLM Pilot Runbook (v0.2)

The live LLM pilot is the **only** step in SlopLab that costs money and touches a
network. Everything else in this repository runs offline.

## Prerequisites (human, one-time)

1. GitHub repository -> Settings -> Environments -> create environment **`llm-bench`**
   (exact name; the workflow gates on it).
2. Add an **environment secret**: `LLM_API_KEY` = your API key.
3. Add **environment variables**:
   - `LLM_MODEL` = model identifier your endpoint accepts
   - `LLM_ENDPOINT` = full chat-completions URL (OpenAI-compatible schema)

Without these, dispatching the workflow fails fast with a red configuration check.

## Running the pilot

1. Actions -> **llm-benchmark** -> Run workflow.
2. Set `max_cases` (default 3 for smoke; pilot protocol uses up to 60).
3. Dispatch. The job runs only on manual dispatch - never on push/PR/schedule.

## Budget enforcement (scripts/llm_bench.py)

The metered step is wired to `experiments/configs/llm-pilot-v0.2.yaml` and every
limit below is enforced in code:

- **Pre-flight plan check:** before any network activity the runner computes
  `max_cases x repeats x (1 + max_retries_per_case)` - the worst-case request
  count including retries - and rejects the run (exit code 2) when it exceeds
  `budget.max_requests`. An oversized dispatch spends zero requests.
- **Hard request cap:** every attempt passes a counting client that stops at
  `budget.max_requests` (180) even when failures trigger retries.
- **Per-request timeout:** 60 s (`budget.request_timeout_s`).
- **Retries:** at most `budget.max_retries_per_case` (2) additional attempts per
  evaluation after transport or parse failures.
- **Pacing:** at least `budget.min_interval_ms` (500 ms) elapses between request
  dispatches; HTTP 429 responses honor their `Retry-After` header before the
  evaluator's retry loop fires again.

### Free-tier safety (e.g. 50 requests/day)

The default smoke plan is `3 cases x 1 repeat x <=3 attempts = <=9 requests` -
far below any daily free-tier limit. To stay under 50 requests in a day,
dispatch plans whose *worst case* sums to at most 45
(`sum(max_cases x repeats x 3)` across the day). The runner prints the computed
worst-case number before starting, so oversized plans are visible immediately.

## What you get back

- `llm-bench-results.jsonl`: normalized evaluation records with repeat indices
  and failure markers. Raw model responses are intentionally NOT stored.
- `llm-bench-results.bundle/manifest.json`: provenance - budget as configured,
  request/error/timeout counters, selected/repeat counts, prompt hash, commit
  SHA. Both files ship in the `llm-bench-results` artifact; nothing sensitive is
  logged.
- Manifest counters also include repeat-stability metrics when two or more
  repeats completed (unanimity rate, decision flips, mean confidence spread).

## Interpreting pilot output

- Report observations scoped to this benchmark only: e.g. "model X flipped decisions
  on N of 60 cases across repeats" - never general claims about triage quality.
- Failed evaluations are excluded from accuracy-style statements but their count is
  always reported alongside.
- If stability is poor (high flip rate), do not proceed to the full study; widen
  temperature/decoding documentation and re-pilot instead.
