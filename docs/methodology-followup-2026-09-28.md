# Methodological follow-up — 28 September 2026

This record tracks reopened issues #45, #46, #47, #50 and #52. It separates
completed deterministic checks from work that requires the owner's pre-vote
judgments or a new model panel. All numbers below come from committed
`v1-core-example` records unless the population is named otherwise.

## #45: fixed actions and actual parent–child transitions

Run `uv run python scripts/blind_policy_compare.py`. Each control returns one
fixed action and confidence `0.5` for every row; it does not inherit confidence
from the rules evaluator. The earlier 0.740 always-review auxiliary score did
inherit varying rules confidences, so that was not a fully constant control.

| Metric | Rules | Always accept | Always reject | Always review |
|---|---:|---:|---:|---:|
| Decision-changing target accuracy | 0.8021 | 0 | 0.2396 | 0.7604 |
| Overall authored-target agreement | 0.8485 | 0.1751 | 0.2929 | 0.5320 |
| False reassurance | 0.0939 | 1 | 0 | 0 |
| Legacy auxiliary score | 0.8385 | 0.2125 | 0.5901 | 0.7910 |
| Both parent and child correct, of 96 paired target-changing children | 0.7604 | 0 | 0 | 0 |
| Observed decision change, of 96 pairs | 0.8333 | 0 | 0 | 0 |
| Child correct when parent correct | 0.8022 | 0 | undefined | undefined |
| Child deferrals, of 96 | 0.6979 | 0 | 0 | 1 |

The new paired audit binds parent and child by evaluator and repeat, counts
missing parents, and refuses duplicate records. All 96 eligible children have
a parent in this run. A fixed review policy nearly matches the rules evaluator
on the old target-accuracy and auxiliary-score fields while changing **no**
parent–child decisions. The legacy auxiliary score remains in machine-readable
historical bundles but is omitted from current human-facing comparisons.
Neither that score nor target accuracy is a detection or capability claim.

## #50: authored pairs and the composite operator

Run `uv run python scripts/presentation_pair_audit.py`. The 8 authored
plain/polished pairs are outside the operator-generated presentation metric.
The rules baseline changes decisions in **7/8**, has both members correct in
**1/8**, and moves from accept to non-accept in **4/8**. Its transition matrix
is 4 `accept → reject`, 3 `needs_manual_review → reject`, and 1
`reject → reject`. There is no acceptance gain. The oracle has 8/8 both
correct and no transitions. These authored pairs also differ in boundary
wording, so their transitions cannot be attributed to style alone.

The historical `professionalize_language` operator combines register edits
with an asserted authorized-testing preamble. Its bytes are retained for
reproduction of published v1 results. New `professionalize_style` and
`add_authorization_preamble` operators isolate the interventions; the latter
is a provenance category and is excluded from the style metric. Run
`uv run python scripts/presentation_intervention_audit.py` for the four-arm
rules-baseline comparison over the 44 **standalone** canonical reports (the
authored pairs are excluded): original, style only, cue only and historical
composite each receive 18 accepts, with zero decision changes from original.
This zero is specific to the deterministic rules baseline and these reports;
it does not establish that an LLM or a different corpus is insensitive.

## #46–#47: separate axes and author targets

The [case-card contract](../cards/README.md) separates per-claim evidence
support, next human action and ordinal action confidence. `verify` is a
verification queue recommendation, not proof of a vulnerability. The legacy
numeric quality targets remain authored targets; they are not a measure of
independently verified report quality.

Run `uv run python scripts/decision_preserving_audit.py`. In the committed
suite, 141 derived cases preserve the authored decision; 93 come from
operators with negative authored dimension deltas. In 26 cases the
`remove_affected_version` operator deletes a section listed as required by
its parent manifest while the target decision remains unchanged. This is a
provenance inconsistency to disclose, not evidence that all 26 actions should
change. A listed `required_evidence` item is not a universal hard gate: the
program policy and the core claim decide what blocks human verification.
The old variants have **not** been independently relabeled.

A blinded three-family realized-edit panel is prepared in
`scripts/realized_edit_panel.py`: all 141 parent/child report pairs are shown
without the operator, report class, or authored targets; A/B order is fixed by
a hash of the variant ID. Its first 423-request attempt on 2026-09-28 yielded
**zero valid votes**: all 141 Google requests returned HTTP 404 for unavailable
structured-output routing, while all 282 Mistral/Qwen requests returned HTTP
403 because the local OpenRouter key had exceeded its total limit. The raw
failure ledger stays under ignored `heldout-private/`. These failures supply
no semantic labels. The runner now stops after the first permanent provider
error, and the replacement Google model is checked against the live catalog.
Once the key limit is resolved, the audit will retain per-model votes and
uncertainty; model agreement will remain exploratory evidence, not independent
human ground truth.

Three public cards (c01–c03) already have owner judgments and adjudication.
Nine fresh synthetic inputs (c04–c12) have been prepared outside Git under
`heldout-private/v0.1/owner-packet/`. Their answer key is sealed separately.
The owner must judge the neutral input views before any model votes. The
aggregate will preserve both owner/model disagreements and uncertainty;
these nine are not being added to the legacy 60-fixture benchmark.

## #52: exposure and held-out status

The [exposure register](exposure-register.md) records when corpus, derived
variants, public cards and pilot outputs first appeared in Git. Public
material cannot be an unseen test. The nine new private inputs are a
**candidate** held-out set only: no model has seen them through this project,
but there is no claim that a provider has not seen similar material. Owner
judgment, an allowed three-family model panel, discrepancy retention and
controlled aggregate publication remain required before a held-out result
can be reported. No private input or sealed answer key is committed.
