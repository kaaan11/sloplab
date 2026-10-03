# Case-card and realized-edit annotation rubric v0.1

This rubric separates four questions. The old class labels and numeric targets
remain historical author targets. The new card panel is compared with the owner's
blind judgments, written before model votes; model agreement is descriptive.

| Axis | Anchor | Recorded answer |
|---|---|---|
| Vulnerability validity | A real boundary violation requires human verification. Explicit synthetic policy and stipulated facts define the scenario. A supported observation does not establish every impact claim. | Verification remains a human task; no model validity score. |
| Claim support | `supported`: supplied evidence supports this claim. `missing`: material evidence is absent. `contradictory`: supplied evidence or authoritative context contradicts it. Plausibility alone cannot supply evidence. | One status for each claim, with the claim ID preserved. |
| Report quality | Completeness, claim consistency, impact calibration and clarity are judged against the information actually needed. A truthful, clearly limited report can be well written while its behavior is outside program scope. | For realized edits, whether these properties materially changed between the two texts; `yes`, `no`, or `uncertain`. No inherited numeric quality score is used. |
| Next human action | `verify`: the specified in-scope claim has enough information to attempt verification. `request_specific_information`: a named material gap or conflict prevents that attempt. `likely_out_of_scope`: stated policy or threat-model facts exclude the reported behavior. | One card action and ordinal action confidence. For realized edits, whether that next step should change; `yes`, `no`, or `uncertain`. |

## Material change anchors for realized edits

- Completeness changes when an edit removes or adds information needed to follow
  the claim, identify its subject, or understand a verification attempt.
- Consistency changes when an edit introduces or removes a disagreement between
  a claim and supplied evidence or between parts of the report.
- Calibration changes when asserted certainty, impact or scope changes without
  matching support. Correctly saying "no demonstrated impact" is calibrated.
- Clarity changes only when the edit materially changes readability or ambiguity;
  a cosmetic spelling preference alone need not count.
- Action changes only when these facts change what a human should do under the
  stated policy. An omitted version is a blocker when that policy or core claim
  needs it; `required_evidence` in an old manifest is not a universal gate.
- Use `uncertain` when the supplied text does not establish the relevant policy
  or the materiality of the change. Do not guess an implicit program rule.

For each pair, quality and action are annotated separately. `yes/yes` gives
**both**, `yes/no` **quality only**, `no/yes` **action only**, and `no/no`
**neither**. An unresolved axis remains uncertain. Published descriptive majority
categories require at least two matching definite votes on each axis; all votes,
including dissent and uncertainty, are retained. These categories do not replace
historical mutation targets.

## Ordinal action confidence

- **High:** explicit policy, claim and evidence determine the next action without
  a material ambiguity.
- **Medium:** the next action is supported but a relevant interpretation remains
  uncertain; name it in the rationale.
- **Low:** the supplied input barely supports choosing one next action; explain
  what prevents a firmer recommendation.

Confidence refers to the action. It is not a probability that the vulnerability
exists. Model families used for either panel exclude OpenAI, Meta and Anthropic;
the exact free model IDs, request settings and first-dispatch hashes are frozen
in the corresponding run protocol. The three author families are separate
annotation sources, not a proof of statistical independence or correctness.
