# Adjudication record: c02

- Card id: `c02`
- Owner judgment commit: `7bb0360` (`git log --format=%h -1 -- cards/v0.1/c02/owner-judgment.yaml`)
- Sealed key sha256: `6f169ef110552c4472351b62e2213bb3a90407c4e45e7bb0f940b8356eac19cd`
- The committed `card.yaml` equals the sealed copy except `provenance.input_sha256` and `provenance.owner_review_status`, the two provenance fields filled after unsealing, and the adjudication resolution line below.

## Card-level comparison

| Field | Owner | Key | AGREE/DIFFER |
| --- | --- | --- | --- |
| action | `likely_out_of_scope` | `likely_out_of_scope` | AGREE |
| action_claim_ids | `[]` | `[]` (`review.next_action.verification_claim_ids`) | AGREE |
| confidence | `high` | `high` | AGREE |

## Per-claim comparison

| claim_id | Owner status | Key status | AGREE/DIFFER |
| --- | --- | --- | --- |
| C1 | `supported` | `supported` | AGREE |
| C2 | `supported` | `supported` | AGREE |
| C3 | `missing` | `missing` | AGREE |

## DIFFER details

None.

- Resolution: full agreement; no change (adjudicated 2026-09-28)

## Summary

3 of 3 items agree (action, action_claim_ids, confidence). Claims: 3/3 agree.
