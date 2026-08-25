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

Budget enforcement (from `experiments/configs/llm-pilot-v0.2.yaml`):
- hard cap: 180 requests total,
- 60 s per-request timeout,
- at most 2 retries per case,
- results written to the `llm-bench-results` artifact; nothing sensitive is logged.

## What you get back

- `llm-bench-results.jsonl`: normalized evaluation records with repeat indices and
  failure markers. Raw model responses are intentionally NOT stored.
- Manifest counters: requests / errors / timeouts, plus repeat-stability metrics
  (unanimity rate, decision flips, mean confidence spread).

## Interpreting pilot output

- Report observations scoped to this benchmark only: e.g. "model X flipped decisions
  on N of 60 cases across repeats" - never general claims about triage quality.
- Failed evaluations are excluded from accuracy-style statements but their count is
  always reported alongside.
- If stability is poor (high flip rate), do not proceed to the full study; widen
  temperature/decoding documentation and re-pilot instead.
