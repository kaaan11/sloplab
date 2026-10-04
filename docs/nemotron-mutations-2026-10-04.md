# Nemotron single-observation mutation study — 4 October 2026

This study evaluates all **237 existing V1 derived cases** alongside **60 fresh
canonical parent controls**, one observation per case. It does not generate new
mutations or change corpus targets. The existing materialized 297-case suite is
bound by report/target identities before dispatch.

## Registered continuation

The [first mutation protocol](../experiments/results/llm-pilot/2026-10-04/nemotron-mutations-01/protocol.json)
was frozen with the remaining-repeat study. Its gate stopped it before any
model calls because of a transport failure in that repeat study; it has zero
requests and its unstarted ledger remains archived.

After the user explicitly authorized up to three supplemental free requests,
the separate [repeat replacement block](nemotron-full-repeats-2026-10-04.md)
completed. The matrix had 3/60 flipped cases, below the registered operational
threshold of at most six. The
[new mutation protocol](../experiments/results/llm-pilot/2026-10-04/nemotron-mutations-02/protocol.json)
was frozen before supplemental/model dispatch, with unchanged selected inputs
and a maximum of **297 new mutation/control requests**. Together with the
150 original repeat requests and three supplemental requests, this continuation
has an overall ceiling of **450**. Earlier studies are not included in that ceiling.

## Transport and controls

- Requested model: `nvidia/nemotron-3-super-120b-a12b:free`, OpenRouter chat completions.
- Existing `triage-v1` prompt, strict JSON Schema, required provider parameter support,
  temperature 0, no provider decoding seed.
- Thirty disjoint bundles: 29 ten-case batches and a final seven-case batch.
- One observation per selected case; no automatic retries.
- Timeout 60 seconds per request; minimum start interval 3.1 seconds across batches;
  each batch deadline is its request count × 60 seconds + 100 seconds.
- Access/rate-limit failure or changed route pricing stops subsequent physical calls.
  Catalog and listed endpoint prices are checked as zero before every batch.
- Fresh canonical controls and their children share one cohort/repeat index.
  Historical single-observation or repeat-study parents are not substituted into
  paired mutation metrics.

Response-level billing/usage is not retained, so no exact billing total is
asserted. API keys and raw model responses are not archived.
`transport.error` is an outcome classification, not proof of a particular
network/provider fault; the precise underlying exception is not retained.

## Recorded observations

All 297 cases were dispatched once: **296 valid responses and one failure**,
with no unstarted evaluations. The
[verified summary](../experiments/results/llm-pilot/2026-10-04/nemotron-mutations-02/summary.json)
preserves 30 completed integrity-marked bundles and the original failure.

| Subset | Valid responses | Authored-target matches |
|---|---:|---:|
| Fresh canonical controls | 60/60 | 59/60 (98.33%) |
| Derived cases | 236/237 | 136/236 (57.63% of valid responses) |
| Combined valid responses | 296/297 | 195/296 (65.88%) |

`mut-loginject-031-confidence-overstatement-05` failed with `transport.error`.
The failure is not a target mismatch and is not silently counted as a model
decision. The underlying exception is not available from the normalized ledger.
The request ceiling of 450 (150 original repeats + 3 supplemental repeats + 297
mutation/control calls) was reached. A separate up-to-three-request completion
was explicitly authorized by the user. A
[separate supplement protocol](../experiments/results/llm-pilot/2026-10-04/nemotron-mutation-supplement-01/protocol.json)
selected the one missing variant before dispatch. One new call returned a valid
decision matching the authored target. Total continuation usage is **451 calls**,
below the authorized 453 ceiling; the unused allowance was not spent.

The original full-suite metric bundle is withheld because success coverage is
incomplete. The subset counts above are descriptive of valid responses only;
their denominators and the missing case remain explicit.

## Completed matched dataset

The [supplement summary](../experiments/results/llm-pilot/2026-10-04/nemotron-mutation-supplement-01/summary.json)
defines a 297-record matched dataset: the original 296 successes plus the one
new supplemental child observation. All original 60 parent controls are retained;
the original failure remains a failure in its own ledger. This is not retroactive
complete success in the original 297-call study. The later observation introduces
an additional chronological limitation.

| Measurement | Completed dataset result |
|---|---:|
| Canonical target agreement | 59/60 (98.33%) |
| Mutation target agreement | 137/237 (57.81%) |
| Overall authored-target agreement | 196/297 (65.99%) |
| Decision-changing target agreement | 2/96 (2.08%) |
| False reassurance (accept with non-accept target) | 87/245 (35.51%) |
| Over-rejection (reject with accept target) | 1/52 (1.92%) |
| Decision-preserving drift | 8/141 paired variants (5.67%) |
| Presentation susceptibility | 2/39 eligible paired variants (5.13%) |

Decision-changing eligibility uses the production definition: a mutated case's
target differs from its parent-class default. The low target agreement on these
96 variants contrasts with high canonical agreement; the current prompt/model
cannot be characterized as robust merely from canonical results. These remain
authored synthetic targets, with no independent validation of all mutation effects.
No dimensional target errors are reported, and no mutation repeat stability is claimed.

Observed target agreement is much lower for mutations than canonical controls.
In this collection, the returned decisions did not match any authored target for
`fabricate_reference` (0/14), `impossible_precondition` (0/12),
`invent_api_identifier` (0/13), or `misattribute_cve` (0/13).
This is an in-domain discrepancy with authored targets, not proof of general
real-world failure or independent validation of every mutation's target.

The fresh racecond-018 parent control returned review rather than its authored
accept target, unlike the replacement repeat block's three accepts. This
cross-study variation is preserved, not folded into the preregistered repeat matrix.

## Interpretation and offline replay

Authored-target agreement is descriptive of this public synthetic collection,
not independently validated real-world accuracy. Cases share canonical parents
and are not 297 independent samples. A single observation cannot establish
mutation repeat stability. The free model alias and provider decoding are not
pinned; chronological model/provider changes cannot be separated from variability.

The existing pilot does not populate dimensional targets in normalized records.
Dimension-error metrics are therefore undefined, although target provenance is
bound by the protocol. Decision-changing target agreement and decision-preserving
drift are different measurements; stable wrong decisions can have low drift.

```bash
uv run python experiments/scripts/verify_nemotron_completion_20261004.py nemotron-mutations-02
uv run python experiments/scripts/nemotron_mutation_supplement_20261004.py
```

The replay accesses no network. It checks frozen input/source/prompt/model/runner
identities, bundle inventories/hashes, disjoint case selection, unique outcome
keys, parent/operator links and request accounting. On complete success coverage,
it recomputes the existing production metrics using fresh paired controls and
compares the saved summary. No stability or full-suite metrics are substituted
for incomplete coverage.
The separate supplement replay verifies the preserved incomplete original study,
the selected missing-case identity, unique matched coverage and request accounting,
then recomputes the completed dataset's production metrics. Its default mode
is offline; an explicit `--dispatch` is required for a new archive, and existing
archives cannot be overwritten or rerun.
