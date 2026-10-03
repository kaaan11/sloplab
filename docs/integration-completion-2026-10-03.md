# Integration tracker completion — 3 October 2026

Issue #54 tracked the twelve correction PRs opened against `0382566`, their
merge order, review evidence and the consistency of committed results. All
listed PRs are merged; the review and revision records remain in the
[tracker comments](https://github.com/kaaan11/sloplab/issues/54).

| Wave | Merged PRs | Recorded evidence |
|---|---|---|
| A | #38, #32, #41, #29, #30, #39, #43, #34, #42 | Independent acceptance/revision records; combined local CI checks |
| B | #37 | #23/#49 formula, full result regeneration, locked output tests |
| C | #33, #40 | Changed evaluator records regenerated; operator output comparison; independent revision verification |
| D and follow-up | #62–#69, #58 | Repeat-unit preservation, safe output replacement, provenance, relative paths, evaluator/result CI lock, cross-version summation, cluster intervals and owner-reviewed card contract |

The GitHub merged-PR history confirms the above merges on 27–28 September.
The separate deferred methodology follow-up is recorded in PR #78 and the
[October model panel report](model-panel-followup-2026-10-03.md).

## Legacy branches

The three branches mentioned by #54 are preserved; they are not additional
pending merge candidates:

- `fix/issues-17-18-audit`: its path containment and URL/CVE safety changes
  are superseded by merged #29/#30. Current callers use
  `src/sloplab/path_boundary.py`; regression suites cover absolute paths,
  parent traversal, symlink escapes, URL authority and CVE parsing.
- `fix/issue-22-study-run-hygiene` and `fix/issue-22-study-run-state`: both
  implement outcome cleanup, run start/end timestamps and error counts.
  These are present through merged #41; #63 subsequently moves output
  replacement after successful generation, improving on the early deletion
  in these branches. The study rerun/provenance and issue #59 regression
  tests cover the integrated implementation.

This is a disposition of their intended changes, not a claim that the branch
trees are byte-identical to main. No branch deletion is part of this completion.

## Current verification

The October follow-up ran locked dependency sync, Ruff lint/format, strict mypy,
the full pytest suite, validation of all 60 canonical fixtures, and the CI BYOE
plus repeated offline HTML smoke. Committed evaluator/result lock tests are
included in the full suite. No historical fixture or derived target was changed
by the October annotation sidecars. The canonical LLM pilot's one persistent
provider failure is an explicit measurement limitation and was outside #54's
integration scope.
