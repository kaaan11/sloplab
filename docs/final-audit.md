# Final Release Audit - v0.1.0

Audit performed 2026-08-25 against the V1 acceptance criteria and the operating
rules in the project charter.

## Verification performed

| Check | Result |
|---|---|
| Full test suite | 127 passed, offline, no API keys |
| Lint (`ruff check .`) + format | clean |
| Type check (`mypy src tests`, strict) | clean |
| Clean-environment install (fresh venv, `uv pip install .`) | console script works |
| Benchmark from foreign working directory (absolute suite path) | completes; byte-identical rules-baseline case records vs committed example |
| `sloplab validate corpus/` | 48 canonical fixtures, 0 errors, 0 warnings |
| Safety validation of all generated adversarial content | enforced in materializer + property tests |
| Oracle end-to-end sanity | accuracy/detection/FAR/calibration all perfect on v1-core |
| Determinism | same seed -> byte-identical mutations; full re-run identical except timestamped header |

## Issues found and fixed during audit

1. **Silent empty suite from foreign CWD** - relative `corpus_root` resolved against
   the process working directory produced a header-only index instead of failing.
   Fixed: robust anchor resolution (cwd -> suite ancestors) plus loud errors on
   empty discovery; covered by `tests/regression/test_suite_paths.py`.
2. **Uncovered-class planner error was opaque** - a KeyError leaked when a suite
   policy did not cover every report class. Fixed with an actionable message
   listing uncovered classes.

## Acceptance criteria status

All V1 criteria met (see docs/progress.md checklist). The optional LLM adapter is
implemented, disabled by default, mock-tested for malformed JSON / timeout /
schema-mismatch paths, and excluded from CI and default registries.

## Known limitations (accepted for V1)

1. **Baseline gaps are real and documented.** The rules baseline misses ~23% of
   degrading mutations and retains FAR 0.126, concentrated on polished
   presentation-pair members. These numbers are the measurement target, not bugs;
   they are recorded in methodology.md.
2. **Corpus phrasing overlap.** The uncertainty detector's patterns stylistically
   overlap this corpus's review class (noted inline in `baseline.py`). Future
   corpora should include differently-phrased uncertain reports.
3. **English-only corpus**; 48 fixtures is the committed floor, diversity is finite.
4. **LLM adapter is unexercised live.** Transport exists but no vendor calls were
   made during development or audit, by policy. Live benchmarking requires the
   documented separate workflow (model id, decoding params, >= 3 repetitions).
5. **Single-machine determinism claim.** Byte-identity verified across directories,
   clean venvs, and repeated runs on one platform (CPython 3.14, Linux); cross-
   platform byte-identity of PyYAML output is expected but not asserted here.

## Release blocker count

0.
