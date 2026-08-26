# Remediation Audit - v0.2.2

Maps every finding from the independent v0.2.1 audit to the remediation evidence
on branch `remediation/v0.2.2`. Scope guard: no new product features; no label,
operator-semantics (beyond the fixes below), or evaluator-decision changes.

## Verification performed (R07)

| Check | Command / method | Result |
|---|---|---|
| Full test suite | `pytest` | **183 passed** (162 prior + 21 new), offline |
| Lint / format / types | `ruff check .`, `ruff format --check .`, `mypy src tests` (strict) | clean |
| Version consistency | `sloplab --version`; wheel filename; `uv.lock` | `0.2.2` everywhere |
| Clean wheel install | fresh venv, `pip install dist/sloplab-0.2.2-py3-none-any.whl` | works |
| Foreign-CWD operation | CLI run from `/tmp` against copied tree | works |
| Corpus validation | `sloplab validate corpus/` | 60 fixtures, 0 errors, 0 warnings |
| Reference reproduction | `reproducibility.md` command, byte diff of `run.jsonl` (minus header) | IDENTICAL |
| Study determinism | rerun `sloplab study`, byte-diff `records.jsonl` + adversarial trees (237 x 2 files) | IDENTICAL |
| Clone detection (R01) | compare every written `report.md` vs canonical parent | **0 clones in 237 derived** (both artifact sets) |
| Independent metric recomputation | standalone script over committed `records.jsonl`, no sloplab imports | matches all published numbers |

## Finding-by-finding mapping

### P1-1 / R01 - no-op derived cases

- Fix: machine-readable `"note"` signal from `confidence_overstatement`
  (`src/sloplab/mutations/operators/presentation.py`) plus a parent-text equality
  guard in `materialize_suite` (`src/sloplab/mutations/materialize.py`). Also
  fixed an exposed edge: the output root is now created even when every plan is
  skipped.
- Evidence: before - 43/48 confidence-overstatement cases were byte-identical
  clones; after - clone scan over regenerated artifacts reports **0 clones in 237
  derived cases**.
- Tests: `tests/regression/test_remediation_v022.py::TestR01NoOpElimination`.
- Regeneration: `benchmarks/results/v1-core-example/` and
  `experiments/results/deterministic/study-v02/` fully regenerated at v0.2.2.

Changed metrics (study, seed 20260825):

| Metric | v0.2 artifacts | v0.2.2 regenerated |
|---|---|---|
| Population | 340 (60 + 280) | **297 (60 + 237)** |
| rules accuracy | 0.824 | **0.811** |
| rules FAR | 0.088 (24) | **0.094 (23)** |
| rules drift | 1/184 = 0.005 | **1/141 = 0.007** |
| rules presentation susceptibility | -0.031 (n=68) | **-0.019 (n=39)** |
| graph accuracy | 0.582 | **0.542** |
| graph FAR | 0.394 (108) | **0.429 (105)** |
| graph susceptibility | +0.013 (n=68) | **+0.007 (n=39)** |
| MDR both evaluators | 0.802 / 0.125 (denominator 96) | unchanged: **0.802 (77/96) / 0.125 (12/96)** |

MDR denominators are unaffected by construction (clones carried class-default
expectations). Accuracy/FAR shifts come solely from removing non-mutated clones
from those populations.

### P2-1 / R02 - impact-inflation word corruption

- Before: "trusted login fcritical" (`openred-015`), "would alcritical repeated"
  (`racecond-018`); provenance recorded `low->critical` while the real edit was
  `allow`->`alcritical`.
- Fix: `_CALIBRATION_REPLACEMENTS` are compiled `\b`-anchored patterns; provenance
  records the exact matched text.
- Tests: `TestR02InflationBoundaries` ("flow", "allow", "below", "shallow"
  preserved; phrase preference; case handling).
- Regeneration: the two corrupted cases are gone from the new artifacts; a corpus
  sweep shows no `[a-z]critical` mid-word artifacts anywhere.

### P2-5 / R03 - safety enforcement untested/bypassable

- Before: deleting `validate_content_safety` from the materializer broke zero
  tests; `sloplab mutate` never validated output.
- Fix: materializer validation retained and now covered; `mutate` validates and
  fails closed without writing (`src/sloplab/cli/main.py`).
- Tests: `TestR03SafetyBoundaries` - fake unsafe operator (real-year CVE +
  non-reserved host): materializer records violations, writes nothing; CLI mutate
  exits nonzero, writes nothing. Mutation-testing proof: the earlier audit break
  now corresponds to a failing suite member.

### P2-7 / R04 - mutation identity leak via case id/path

- Before: evaluators received e.g. `case_id="mut-dup-007-confidence-overstatement-01"`.
- Fix: `run_case` passes an opaque deterministic handle (`case-<sha256[:16]>`) as
  context case id and report `fixture_id`/`path`; true identity restored on the
  recorded `CaseRecord` (`src/sloplab/scoring/harness.py`).
- Docs: evaluator contract rule 4, methodology protocol step 2, threat-model row.
- Tests: `TestR04OpaqueIdentity` - spy evaluator asserts operator names absent
  from evaluator-visible input for canonical and mutated cases; handle
  determinism/distinctness; record-level identity restoration.
- Note: deterministic study outputs are unchanged by this fix (records carry true
  ids; evaluator rationales/metadata never embedded ids).

### P2-2/P2-3/P2-4/P2-6 / R05 - release, version, documentation consistency

- Package/source/CLI/generator version `0.2.0rc1` -> **0.2.2**
  (`pyproject.toml`, `src/sloplab/__init__.py`, `uv.lock`); manifests stamped by
  regenerated artifacts now record generator version 0.2.2.
- Documentation URL fixed (`kaaan11/sloplab`).
- Dataset card: composition corrected to 60 fixtures (18 valid / 10 standalone
  invalid / 16 review / 8 pairs), version line tied to package version.
- Suite + study config descriptions state exact current counts (60 / 237 / 297)
  and are enforced by the guard.
- Walkthrough figure corrected (297 scored cases).
- Study doc (`evaluator-study-v0.2.md`) figures regenerated from artifacts;
  wrong fraction (8/64) replaced with 12/96 family breakdown; "eleven families"
  corrected to the eight-family degrading population; drift/ECE rows now match
  artifacts (0.007/0.000 and 0.298/0.270).
- V26 audit annotated rather than rewritten ("solely" correction).
- Reference result regenerated at v0.2.2; documented reproduction command updated
  to include both evaluators and verified byte-identical.
- Guard extended: dataset-card composition/version, suite/study config counts,
  walkthrough count, pyproject URL, non-prerelease version
  (`tests/regression/test_doc_consistency.py`, 8 tests total).

### P3 findings / R06 - low-risk cleanup

- Presentation operators fence-aware: contractions, register upgrades, `!` -> `.`
  punctuation, hedge hardening, and preamble insertion all skip fenced code
  (`split_code_fences` helper). Tests: `TestR06FenceAwarenessAndProvenance`
  (fence bytes preserved verbatim; prose still transformed; fence-only hedge text
  yields the R01 no-op note).
- `add_irrelevant_detail` provenance records the actual appended block heading
  ("Additional Context" / "Background Information"); dead `parse_report` call and
  module-bottom alias removed; duplicated comment block removed from the rules
  baseline.

## Residual limits (not defects)

- Rules-baseline detection remains lexical and corpus-adjacent (documented);
  MDR values measure this baseline's design, not general capability.
- Single seed/corpus; small per-family denominators (10-14) persist.
- The v0.2 study artifacts are superseded in-place; historical documents
  (release notes <= v0.2.1, V26/V22 audits) intentionally retain their original
  era-specific numbers, with annotations where they could mislead.
