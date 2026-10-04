# Nemotron ten-case repeat pilot — 4 October 2026

This separate prospective pilot follows the
[single-observation canonical study](nemotron-canonical-2026-10-04.md).
The first ten canonical cases in suite order were selected before dispatch;
no outcome-dependent case substitution was made. Each selected case received
three new observations. The earlier study is not counted as another repeat.

The [registered protocol](../experiments/results/llm-pilot/2026-10-04/nemotron-repeat-01/protocol.json)
binds the exact selected input/target identities, source commit
`b5444cde73e04ec98cafd87754ec64eec50ca39d`, runner and prompt hashes, provider
catalog/prices and budgets. The frozen runner is committed with this report.

## Scope and budgets

- Model: `nvidia/nemotron-3-super-120b-a12b:free` through OpenRouter chat completions.
- Existing `triage-v1` prompt; strict JSON Schema; required provider parameter support;
  temperature 0; no provider decoding seed is set.
- Ten cases, three repeats, maximum 30 physical requests, no automatic retries.
- Timeout 60 seconds/request, minimum start interval 3.1 seconds, deadline 1900 seconds.
- Stop subsequent physical requests after an HTTP 401/402/403/404/429 response.
- Catalog and all listed endpoint prices checked as zero before dispatch.
  Response-level cost/usage is not retained, so no exact billing total is asserted.

## Observations

The [verified summary](../experiments/results/llm-pilot/2026-10-04/nemotron-repeat-01/summary.json)
records **30 physical requests, 30 valid responses, no failed/unstarted evaluations**.
All 30 decisions matched their authored targets. All **10/10 cases were unanimous**
across the three repeats; **zero cases flipped decisions**.

The mean per-case confidence range (maximum minus minimum over three repeats)
was **0.07** on the 0–1 scale. Confidence therefore was not identical even when
decisions were unchanged. This is not a confidence-calibration result.

These are ten selected public synthetic cases, not full-corpus repeat stability
or independently validated real-world accuracy. The canonical GraphQL disagreement
and historical SAML flip case are outside this first-ten selection. This study
does not resolve those cases, replace historical Dots findings, evaluate mutations,
or test Jev. Further repeat coverage and mutation work require separate protocols.

## Offline verification

```bash
uv run python experiments/scripts/replay_nemotron_repeat_20261004.py
```

The replay does not access the network. It verifies bundle inventories/hashes,
registered input/source/prompt/model identities, the unique 10×3 outcome ledger,
request cap and zero-retry configuration. It recomputes target agreement,
per-case decisions/confidences and the stability fields using the production
metric function, then compares the saved summary. Incomplete coverage is never
counted as unanimity. API keys and raw model responses are not archived.

The live runner requires explicit `--dispatch` and refuses to overwrite this
existing archive; normal execution makes no requests. Do not rerun the frozen
pilot to replace observations.
