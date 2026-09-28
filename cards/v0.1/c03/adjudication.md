# Adjudication record: c03

- Card id: `c03`
- Owner judgment commit: `6b9cc2e` (`git log --format=%h -1 -- cards/v0.1/c03/owner-judgment.yaml`)
- Sealed key sha256: `b84318bc27705109a4b63d6f36ef0ce72584a6ae2d1a5cb8f7096648d2e98835`
- The committed `card.yaml` equals the sealed copy except `provenance.input_sha256` and `provenance.owner_review_status`, the two provenance fields filled after unsealing.

## Card-level comparison

| Field | Owner | Key | AGREE/DIFFER |
| --- | --- | --- | --- |
| action | `verify` | `verify` | AGREE |
| action_claim_ids | `[C1]` | `[C1]` (`review.next_action.verification_claim_ids`) | AGREE |
| confidence | `high` | `high` | AGREE |

## Per-claim comparison

| claim_id | Owner status | Key status | AGREE/DIFFER |
| --- | --- | --- | --- |
| C1 | `supported` | `supported` | AGREE |
| C2 | `missing` | `missing` | AGREE |

## DIFFER details

None.

## Summary

3 of 3 items agree (action, action_claim_ids, confidence). Claims: 2/2 agree.
