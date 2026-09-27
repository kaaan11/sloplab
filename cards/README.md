# Case cards (stage 1, case-card-v0.1)

Small, reviewed **case cards**: fully synthetic triage scenarios with a neutral
annotator-visible input view and a separately held answer key. Stage 1 ships the
versioned schema, an export/leak-check pipeline, and three example cards
proposed as additional examples for
[OpenSSF wg-vulnerability-disclosures #178](https://github.com/ossf/wg-vulnerability-disclosures/issues/178).
The general benchmark is deliberately NOT growing; stage 2 (12 cards, model
panel) only opens if there is external interest.

## Layout

- `schema/case-card-v0.1.schema.json` — full card schema (identity, input,
  review, provenance; `additionalProperties: false`).
- `schema/owner-judgment-v0.1.schema.json` — the owner's blind judgment file.
- `v0.1/<id>/input.json` — the **generated** annotator-visible view (only
  schema_version, opaque_id, context, report, artifacts, claims + a note).
  Regenerate with `scripts/export_card_inputs.py`; never edit by hand.
- `v0.1/<id>/card.yaml` — the full card (answer key). NOT in stage 1's tree
  yet; see workflow below. Sealed answer keys live outside tracked paths.
- `v0.1/<id>/owner-judgment.yaml` — the owner's blind judgment.
- `v0.1/<id>/adjudication.md` — where judgment-vs-key differences are recorded
  (never deleted).

## Two views, one source

Every card exists in two views generated from one source card.yaml:

1. `input.json` — the annotator/owner-visible view: neutral claim inventory
   (no target status, no failure-mode name, no quality hints), report lines
   (`R01…`), evidence artifacts (`E1…`), context items (`P1…` with kind in
   `setting` / `stipulated_fact` / `program_policy` / `assistant_role`).
2. the full card — adds `review` (failure modes, claim–evidence map, next
   action, counterconditions, confidence) and `provenance`.

A leak test (`tests/unit/test_case_cards.py`) enforces that committed
`input.json` files contain no answer-bearing keys or identifiers.

## K1 action vocabulary

A card does not return accept/reject. It recommends the next **human** step:

| Action | Means | Does not mean |
| --- | --- | --- |
| `verify` | An in-scope specific claim has enough evidence and context for a human to attempt verification. Claim and verification question are named. | Established fact; all impact claims true; reward deserved |
| `request_specific_information` | A named, material input is missing or contradictory. The smallest useful question is asked, and how the answer would change the action is stated. | The reporter is wrong; every section must be filled |
| `likely_out_of_scope` | The stated scope or threat-model facts put the issue outside the program. The human ratifies the routing. | The behavior is false, harmless, or badly reported |

- Confidence is **ordinal only** (`low` / `medium` / `high`) and refers to the
  recommended action. No percentages or probabilities.
- Claim–evidence status: `supported` (within the supplied evidence package),
  `missing`, or `contradictory`. `contradictory` requires supplied evidence or
  explicit authoritative context; "unfamiliar API" is not enough.
- Terminal, definitively disproven in-scope cases are excluded from this
  package; no fourth action is invented.

## Owner-judgment workflow (blind)

1. The owner sees **only** `input.json` (plus this README and the template).
2. The owner fills `cards/v0.1/<id>/owner-judgment.yaml`: per claim a status
   (same enum), one action (same enum), a one-line rationale, optional ordinal
   confidence; plus `judged_date` and `judge`. Roughly 5–8 minutes per card.
3. Only after the owner's judgment is committed is the card.yaml answer key
   shown/added, and any divergence is recorded in `adjudication.md`.
   Nothing is deleted; the owner never fills in for the orchestrator.

`cards/v0.1/owner-judgment.template.yaml` lists the claim ids of a card with
empty status fields — no suggested values, no hinting defaults.

## Limits

- Fully **synthetic**: no real reports, no working exploits, no real domains
  (only `example.*` reserved hosts and `CVE-2099-*`), per `docs/safety.md`.
- **Model-assisted, owner-adjudicated**: cards are drafted with a model but no
  claim stands on model output; the human owner adjudicates.
- No prevalence, accuracy, or time-saving claims of any kind.
- **Panel exclusion rule**: any future stage-2 model panel must exclude the
  authoring family and the corpus-authoring families — OpenAI, Meta, and
  Anthropic for these cards (`panel_excluded_families` in provenance).
