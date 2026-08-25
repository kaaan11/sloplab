# Release Notes - v0.2.1

Documentation-only patch release over v0.2.0. **Corpus/documentation count
corrections only; runtime behavior is unchanged** - no source, evaluator,
mutation-operator, corpus, or label modifications of any kind.

## What changed

- Corrected stale corpus-count references across README, corpus balance report,
  v0.2.0 release notes, evaluator study report, and the progress log: the corpus is
  **60 fixture files / 52 logical reports**, and the v1-core study population is
  **340 cases** (60 canonical + 280 derived).
- Added a documentation-consistency guard test
  (`tests/regression/test_doc_consistency.py`) that fails if README fixture/logical
  counts drift from the actual corpus again.

## Why

The V26/V29-era documents were written when the corpus was 48/52 files and cited
"~250 cases"; the numbers silently drifted as the corpus grew. A maintenance audit
(M01-M06) caught the mismatch between cited counts and validator output.

## Verification

162 tests green offline; ruff check/format and mypy strict clean; deterministic
study reproduces byte-identically for this commit.
