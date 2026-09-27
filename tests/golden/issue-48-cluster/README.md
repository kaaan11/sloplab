# Issue #48: frozen cluster-bootstrap reference fixtures

`records-0382566.jsonl` is the exact study bundle records from audit commit
`0382566` (PR #37 head), produced with
`git show 0382566:experiments/results/deterministic/study-v02/records.jsonl`.
It is the pre-PR-#33 rules state referenced by the issue #48 binding
implementation contract; the committed `study-v02` bundle now carries the PR #33
corrected decisions and is intentionally NOT byte-identical to this file.

`canonical-pair-ids.json` is the canonical `case_id -> pair_id` map for the 16
presentation-pair members (8 pairs), read from `corpus/canonical/*/manifest.yaml`
at that same commit; verified equal to the committed corpus manifests at HEAD
(the pair structure is unchanged by PR #33).
