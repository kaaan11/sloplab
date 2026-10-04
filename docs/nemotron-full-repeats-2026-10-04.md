# Nemotron canonical repeat follow-up — 4 October 2026

This completes the remaining-case repeat evaluation after the
[first-ten pilot](nemotron-repeat-2026-10-04.md), while retaining the operational
failure and the separately authorized replacement block.

## Registered scopes and recovery

The [original protocol](../experiments/results/llm-pilot/2026-10-04/nemotron-repeat-remaining-01/protocol.json)
selected the remaining 50 canonical reports, three observations each, before
dispatch. Five disjoint ten-case bundles contain **150 physical requests,
149 valid responses and one transport failure**. There were no automatic retries.
`canonical-racecond-018`, repeat index 2, failed with `transport.error`.
This is the ledger's failure classification; the underlying exception message
or raw response was not retained, so the precise cause is not established.
The original records, including two valid observations for that case, are unchanged.
The original aggregate correctly withholds stability because coverage is incomplete.

The mutation gate therefore stopped the
[original mutation plan](../experiments/results/llm-pilot/2026-10-04/nemotron-mutations-01/protocol.json)
before any model calls. The user explicitly authorized up to three supplemental
free calls and completion of the mutation evaluation, increasing the combined
new-request ceiling from 447 to 450.

The separately registered
[replacement protocol](../experiments/results/llm-pilot/2026-10-04/nemotron-repeat-recovery-01/protocol.json)
selected **three new observations of racecond-018** before supplemental dispatch.
All three returned valid `accept` decisions matching the authored target. This
is a new block, not an overwrite or retroactive retry in the original study.

## Coverage-normalized 60-case matrix

The matrix uses the first-ten pilot's 30 observations, the remaining study's
147 observations on 49 fully covered cases, and the three new replacement
observations for racecond-018: **60 cases × 3 observations = 180 valid records**.
The two earlier valid racecond-018 observations remain archived outside this
matrix; the failed observation remains a failure. Replacement was selected
because of missing coverage, not because of returned decisions.

The three repeat studies therefore contain **183 physical requests, 182 valid
responses and one failure** in total, including the earlier first-ten pilot.
These totals must not be confused with the normalized 180-record matrix.

The [verified replacement summary](../experiments/results/llm-pilot/2026-10-04/nemotron-repeat-recovery-01/summary.json)
contains the matrix's per-case decision/confidence sequences:

| Observation | Result |
|---|---:|
| Cases with three identical decisions | 57/60 (95%) |
| Cases whose decisions changed | 3/60 (5%) |
| Agreement with authored targets | 177/180 (98.33%) |
| Mean per-case confidence range | 0.0672 on the 0–1 scale |

| Changed case | Three decisions, in observation order |
|---|---|
| `canonical-loginject-031` | review → accept → review |
| `canonical-openred-015` | accept → reject → accept |
| `canonical-pair6b-logout` | accept → reject → reject |

GraphQL returned review in all three new repeat observations, whereas the earlier
single-observation study returned reject. SAML returned accept in all three
Nemotron observations; historical Dots flips remain separate evidence.
Targets were not changed.

## Limits and verification

The model is `nvidia/nemotron-3-super-120b-a12b:free`, with the existing `triage-v1`
prompt, strict JSON Schema, required provider parameter support and temperature 0.
No provider decoding seed is set; the benchmark base seed is not a decoding seed.
Each request has a 60-second timeout and request starts are at least 3.1 seconds
apart across batches. Catalog/endpoint prices were checked as zero before dispatch
and again at each batch. Response-level billing is not retained.

These are public synthetic cases with authored targets, not independently
validated real-world accuracy. Chronological batches, an unpinned model alias,
uncontrolled provider decoding, and the operational replacement block limit
generalization. Confidence range is not a calibration metric. The registered
mutation gate (complete replacement block and at most six flipped cases among 60)
is an operational threshold, not a statistical certification.

```bash
uv run python experiments/scripts/verify_nemotron_followups_20261004.py nemotron-repeat-remaining-01
uv run python experiments/scripts/verify_nemotron_completion_20261004.py nemotron-repeat-recovery-01
```

These offline replays verify bundle hashes, frozen input/target identities,
source/prompt/model/runner identities, budgets and unique outcome keys. They
recompute the original incomplete status and the explicitly defined replacement
matrix separately, without executing live runners. API keys and raw responses
are not archived.
