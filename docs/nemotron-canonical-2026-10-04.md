# Nemotron canonical study — 4 October 2026

The user selected `nvidia/nemotron-3-super-120b-a12b:free` for the live
continuation. A three-case operational smoke passed before this separate study.
GitHub's `llm-bench` environment now selects Nemotron through OpenRouter's
chat-completions endpoint. No Jev call was made.

## Registered scope

The [pre-dispatch protocol](../experiments/results/llm-pilot/2026-10-04/nemotron-canonical-01/protocol.json)
binds the 60 public canonical inputs, selected order, source commit
`736625c14cbaa0fa2b1f2ae2117bd09662ab7b83`, prompt and frozen runner hashes.
All cases use the existing `triage-v1` prompt, strict JSON Schema output,
`provider.require_parameters=true` and temperature 0. Authored targets are
not sent to the model. The base seed describes benchmark provenance, not a
provider decoding seed.

There are six disjoint ten-case batches, one observation per case, a total
cap of 60 physical requests and zero automatic retries. Each request has a
60-second timeout; request starts are at least 3.1 seconds apart. Each batch
has a 650-second deadline. Catalog and endpoint prices were verified as zero
before dispatch. The existing transport does not retain usage/cost fields, so
no response-level billing total is asserted.

## Recorded results

| Observation | Result |
|---|---:|
| Planned canonical cases | 60 |
| Physical requests | 60 |
| Valid responses | 60 |
| Failed or unstarted evaluations | 0 |
| Agreement with authored targets | 59/60 = 98.33% |
| Returned decisions | 18 accept; 15 review; 27 reject |

The sole disagreement is `canonical-graphql-028`: the authored target is
`needs_manual_review`; the model returned `reject`. That target was preserved.
`canonical-sqlx-002`, which failed in the historical Dots study, returned a
valid `accept` result here.

The [summary](../experiments/results/llm-pilot/2026-10-04/nemotron-canonical-01/summary.json)
and six integrity-marked bundles preserve all normalized records/outcomes.
These are selected public synthetic cases with authored targets, not an
independently validated measure of real-world triage accuracy. One observation
per case cannot measure repeat stability. Mutation cases were not evaluated.
Historical Dots coverage and other model panels are separate observations.
The existing pilot does not populate `expected_dimensions` in result records;
dimensional targets remain bound by the protocol's input identity, but this
study does not report dimension-error metrics.

## Offline verification

```bash
uv run python experiments/results/llm-pilot/2026-10-04/nemotron-canonical-01/replay.py
```

The replay makes no network calls. It verifies six bundle inventories/hashes,
selection disjointness, model/commit/prompt identities, frozen corpus identities,
all 60 case outcomes, public generator-source hash and summary arithmetic. It retains
the summary's recorded completion timestamp and recomputes the result fields.
The live runner is archived as `runner-source.txt` with only the local checkout
path redacted. `runner-provenance.json` records separate original/public hashes;
the original was checked locally against the protocol before redaction. Offline
replay checks the public source and hash linkage, not the unavailable original
bytes, and does not execute the live runner. Neither API keys nor raw
model responses are included in the public archive.
