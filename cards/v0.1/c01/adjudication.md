# Adjudication record: c01

- Card id: `c01`
- Owner judgment commit: `d4b7e65` (`git log --format=%h -1 -- cards/v0.1/c01/owner-judgment.yaml`)
- Sealed key sha256: `aefd590418d9635f1edb2b38391460d51e544d3a449dd650b73efded721c12f7`
- The committed `card.yaml` equals the sealed copy except `review.next_action.verification_claim_ids`, `review.next_action.verification_question`, `provenance.input_sha256` and `provenance.owner_review_status`, the two provenance fields filled after unsealing plus the adjudicated key fix (verification_claim_ids/question).

## Card-level comparison

| Field | Owner | Key | AGREE/DIFFER |
| --- | --- | --- | --- |
| action | `verify` | `verify` | AGREE |
| action_claim_ids | `[C1, C2]` | `[C1]` (`review.next_action.verification_claim_ids`) | DIFFER |
| confidence | `high` | `high` | AGREE |

## Per-claim comparison

| claim_id | Owner status | Key status | AGREE/DIFFER |
| --- | --- | --- | --- |
| C1 | `supported` | `supported` | AGREE |
| C2 | `supported` | `supported` | AGREE |

## DIFFER details

- Field `action_claim_ids`: owner rationale (verbatim): "The required build, account, ordered steps and observed result are provided, and the supplied records support behavior that conflicts with the documented reset-link policy." Key explanation (verbatim, review.next_action.verification_question): "On build 3.2.0, does a reset link issued before a password change still allow a new password to be set after the change completes?" The key scopes verification to C1 only.
- Resolution: owner judgment adopted (Kaan, 2026-09-28); key updated to verification_claim_ids [C1, C2]
- The `review.next_action.verification_question` was extended to also cover what verifying C2 requires (comparison against the documented reset-link policy).

## Summary

2 of 3 items agree (action, confidence); action_claim_ids differ. Claims: 2/2 agree.
