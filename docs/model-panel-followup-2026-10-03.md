# Model panel follow-up — 3 October 2026

This follow-up supplies the annotation pilot for #46–#47 and the private-input
measurement record for #52. Historical canonical and mutation targets are retained
as authored labels. The [rubric](case-card-rubric-v0.1.md) separates human
verification, claim support, report quality and next human action.

## OpenRouter failure correction

The September paid-model failures did not establish exhaustion of the owner's
free daily quota. Live inspection found a zero USD spending cap, zero paid usage
and a successful free Qwen request. A key's spending limit is denominated in USD
([OpenRouter key documentation](https://openrouter.ai/docs/api/api-reference/api-keys/create-keys)).
Both October panels use catalog-verified zero-price `:free` models. Later HTTP
429 responses are operational failures, retained in request counts; upstream
rate limiting is not a semantic annotation or evidence of an exhausted daily quota.

## Nine private cards: owner first, then models

The owner completed all nine neutral c04–c12 inputs before the first dispatch.
The owner sheet was frozen at **2026-10-03T15:16:46Z**, SHA-256
`ccb0271bf20d5e93960a7473da34d4c18f7c31dffbca4ff564fcda790fcc9a26`.
The private original protocol hash is
`b8dd1c12a53911c9c94391708786c0c1dfec0be8d1b893181f3d4acf17a74fe2`.
Model prompts contain neutral inputs and the support/action rubric, without
owner judgments or the sealed author key. See the
[exposure register](exposure-register.md) for source ancestry and reuse limits.

| Free model | Valid votes / planned | Owner action agreement | Claim-status agreement | Confidence agreement |
|---|---:|---:|---:|---:|
| Qwen Qwen3.8 27B | 7/9 | 7/7 | 13/14 | 7/7 |
| Dots 3 Note Preview | 9/9 | 9/9 | 15/18 | 8/9 |
| Liquid LFM 2.5 2.6B | 9/9 | 4/9 | 15/18 | 8/9 |

The original run generated **25/27 valid votes in 36 physical requests**. A
separately registered six-request coverage supplement retried the two missing
Qwen slots using unchanged inputs, owner reference and model settings. All six
returned HTTP 429. Overall: **42 requests, 25 successes, 16 HTTP failures and one
invalid/transport failure**. Seven cards have all three votes; four of these have
at least one action disagreement with the owner and three have a claim-status
disagreement. Failed slots are excluded from agreement denominators and remain
explicitly absent from coverage. The supplement does not erase original failures.

Qwen and Dots use temperature 0, reasoning disabled, max_tokens 2048; Liquid
requires reasoning enabled and uses max_tokens 4096. These are different model
sizes and request settings; the counts are not a controlled ranking. There is
one valid configured invocation per slot, without a repeat-variance estimate.
Exact IDs, transitions, coverage and protocol/ledger hashes are in the
[public aggregate](../experiments/results/model-panel/private-cards-2026-10-03/summary.json).
No individual private-card labels, inputs or raw votes are published.

After voting, the sealed author key was compared with the frozen owner sheet.
There is **one claim-status disagreement** and no action/confidence differences.
Both originals and the comparison remain private and unchanged. The previously
submitted owner judgment governs the reference under the existing card policy;
this does not assert a new post-panel owner review. These nine cards plus the
three public owner-adjudicated examples supply 12 contract examples, but only
nine are new private panel inputs. They are separate from the 60-fixture benchmark.

## Public realized-edit panel

The population is all **141** realized v1 edits whose authored decision preserves
the parent target. Selection uses the historical manifests; those labels are
hidden from the models. Each request contains three actual report A/B pairs,
opaque pair handles, and the quality/action rubric. A/B order and batch order
are fixed by hashes of public mutation IDs. Some batches may share a parent;
the 141 pairs are not independent reports.

The separately registered panel uses Dots, Liquid and NVIDIA Nemotron 3 Super
120B A12B. Qwen was excluded from this panel before its first dispatch because
its shared upstream pool was repeatedly unavailable in the private-card run.
This panel is not a matched model comparison with the card panel. NVIDIA is the
model developer ([model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8));
no OpenAI, Meta or Anthropic model is used for either panel.

The protocol was registered at **2026-10-03T15:52:22Z**, before the first pair
request. There are 47 batches × 3 families = 141 planned requests and 423
planned individual annotations. Each failed batch can be attempted at most
three times, with a hard 240 physical-request cap. Request starts are spaced
at least 3.1 seconds apart across the three active workers. On a permanent
HTTP error, the runner records in-flight results before stopping; resume appends
only eligible missing batches. A resume credential-variable bug was corrected
after the initial dispatch, before the first resume; it did not alter inputs,
prompts, model settings or the original protocol.

Dots uses reasoning disabled/max_tokens 4096; Liquid and NVIDIA use reasoning
enabled/max_tokens 8192; all use temperature 0 and structured output. Any
missing/duplicate pair ID invalidates the batch. Model-family separation is a
provenance control, not proof of statistical independence or human truth.

The completed bounded run produced **414/423 valid individual
annotations in 159 physical requests** (138 successful batches,
10 HTTP failures and 11 invalid/transport failures).
All 141 planned batch/family slots were attempted. Three slots exhausted their
three-attempt allowance: two Dots batches returned HTTP 400, and one Liquid
batch ended with upstream HTTP 429. They leave **9 pairs incomplete**; the other
132 have all three family votes. These missing labels are not converted into
semantic categories.

| Descriptive majority category | Pairs |
|---|---:|
| Quality only | 55 |
| Action only | 0 |
| Both | 0 |
| Neither | 73 |
| Uncertain | 4 |
| Incomplete | 9 |

**114 of the 132 complete pairs have dissent on at least one axis**.
This high disagreement limits the majority categories' interpretation. The
`axis_vote_counts` aggregate covers only complete three-family pairs; the
normalized annotations retain every valid vote on incomplete pairs too.

| Operator | Quality only | Action only | Both | Neither | Uncertain | Incomplete |
|---|---:|---:|---:|---:|---:|---:|
| add_irrelevant_detail | 8 | 0 | 0 | 27 | 0 | 1 |
| confidence_overstatement | 1 | 0 | 0 | 3 | 0 | 1 |
| professionalize_language | 14 | 0 | 0 | 29 | 2 | 3 |
| remove_affected_version | 13 | 0 | 0 | 10 | 0 | 3 |
| remove_reproduction_step | 13 | 0 | 0 | 2 | 0 | 1 |
| scope_expansion | 6 | 0 | 0 | 2 | 2 | 0 |

The panel supplies evidence for separating quality changes from next-action
changes; it does not validate the legacy numeric targets. In particular,
version removal can be judged a quality change while still permitting a
verification attempt. Outcomes for the historical composite professionalization
operator cannot isolate register from its authorization preamble.

The [annotation bundle](../experiments/results/model-panel/realized-edit-2026-10-03/)
contains all 423 planned slots (including failures), per-model reasons, aggregate
counts and the frozen protocol. Raw provider errors remain private; their counts
and the raw-ledger hash are public. Recomputing with `--bundle` reproduced the
saved aggregate exactly without opening a private ledger.


Annotations use `yes/no/uncertain` independently for quality and action. A
public descriptive category requires at least two matching definite votes on
each axis: both, quality only, action only or neither. An unresolved axis stays
uncertain; a missing family vote makes the pair incomplete. All normalized
votes and reasons are retained, including dissent. No majority result changes
legacy target labels. A listed `required_evidence` item is not an automatic
verification gate: the explicit program policy and core claim determine
whether an omitted version or reproduction step changes the next action.

## Reproduction and limits

```bash
uv run python scripts/summarize_heldout_panel.py
uv run python scripts/summarize_realized_edit_panel.py \
  --out experiments/results/model-panel/realized-edit-2026-10-03
uv run python scripts/summarize_realized_edit_panel.py \
  --bundle experiments/results/model-panel/realized-edit-2026-10-03
```

The first command requires the controlled local owner/input/ledger files. The
public realized-edit export contains normalized annotations, an aggregate and
the frozen protocol plus raw-ledger hash. The `--bundle` command recomputes its
aggregate from public annotations without private ledger or card access.
Running either live panel again requires its preserved local
protocol and ledger with `--run --resume`; default invocation is preflight.
A completed slot is never re-requested. These retrospective runners are tied
to the registered populations, not a fresh-data generation API.

This is an exploratory annotation pilot: one human owner, synthetic inputs,
model-assisted sidecar labels and known operational missingness. It supplies
no general vulnerability accuracy, report-quality validity, prevalence or
time-saving estimate. A future validation study needs additional independent
human raters and newly authored inputs. The prior canonical LLM study's
`sqlx-002` HTTP 400 remains a separate unresolved coverage limitation.


## Delivery checks

Local Python 3.13.15: locked dependency sync, Ruff lint and format, strict mypy,
**1203 tests passed**, 60 canonical fixtures validated with zero errors/warnings,
and the CI BYOE plus byte-identical repeated offline HTML smoke. Public bundle
replay matched the saved aggregate. The private owner sheet and sealed author
key hashes remained unchanged. Integration tracker disposition is recorded in
[integration completion](integration-completion-2026-10-03.md).
