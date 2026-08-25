# SlopLab Progress

Build queue status. Updated after every completed queue item.

## V1 acceptance criteria

- [x] 48 controlled canonical fixtures (12 valid / 10 invalid / 10 review / 8 presentation pairs as 16 files).
- [x] 12 mutation operators, each with behavior + determinism + safety tests.
- [x] Oracle + rules-baseline evaluators; optional LLM adapter delivered in Q13.
- [x] One-command reproducible benchmark (`sloplab benchmark`).
- [x] Mutation-level, report-class-level, and evaluator-level metrics.
- [x] JSONL, CSV, and Markdown outputs.
- [x] Safety policy enforced by validation; dataset card committed.
- [x] Full v1-core results committed under `benchmarks/results/v1-core-example/`.
- [x] Clean-install reproduction verified.

## Queue status

| Item | Status | Notes |
|---|---|---|
| Q00 charter | complete | README skeleton, threat model, safety policy, decision log, backlog |
| Q01 scaffold | complete | package, CLI, ruff/mypy/pytest config, CI workflow (see evidence map) |
| Q02 schemas | complete | |
| Q03 corpus loading | complete | |
| Q04 12 canonical reports | complete | |
| Q05 six mutation operators | complete | |
| Q06 planner + materialization | complete | |
| Q07 evaluator protocol + oracle | complete | |
| Q08 rules baseline | complete | |
| Q09 scoring + reporting | complete | |
| Q10 integration tests | complete | |
| Q11 corpus 40 + 12 operators | complete | |
| Q12 regression/property/examples/docs | complete | |
| Q13 optional LLM adapter | complete | |
| Q14 release audit | complete | |

---

## Q00 - Project charter (2026-08-25)

- **Status:** complete
- **Changed:** `README.md`, `docs/threat-model.md`, `docs/safety.md`,
  `docs/decision-log.md`, `docs/backlog.md`, `docs/progress.md`, `LICENSE`, `.gitignore`.
- **Verification:** scope, non-goals, benchmark contract pointer, safety rules are
  explicit in committed docs; decisions D-0001..D-0010 recorded.
- **Known limitations:** README quick-start section is a placeholder until CLI exists;
  methodology/dataset-card/evaluator-contract docs arrive with their implementing
  queue items (Q09/Q12).
- **Next:** Q01 - package scaffold, CLI skeleton, tooling config, CI.

---

## Q02-Q06 progress checkpoint (2026-08-25)

- **Status:** complete
- **Changed:** schemas (models/*), corpus parser/loader/validation, safety policy,
  12 canonical fixtures (5 valid / 4 invalid / 3 review), mutation engine with 7
  operators (6 required + confidence_overstatement), planner, materializer, CLI
  `validate`/`mutate`/`materialize`, smoke suite config.
- **Verification:** 65 tests green; ruff + mypy strict clean; `sloplab validate corpus/`
  passes; smoke materialization yields 29 derived cases deterministically (byte-equal
  across runs).
- **Known limitations:** presentation pairs not yet in corpus (Q11); evaluators and
  scoring not yet implemented (Q07-Q09); `add_irrelevant_detail` deferred to Q11.
- **Next:** Q07 - evaluator protocol + oracle evaluator.

---

## Q07-Q12 progress checkpoint (2026-08-25)

- **Status:** complete
- **Changed:** evaluator protocol/oracle/rules-baseline, scoring harness and metrics,
  JSONL/CSV/Markdown writers, CLI evaluate/benchmark/compare/report, 36 additional
  canonical fixtures (corpus now 48 files incl. presentation pairs), 5 remaining
  mutation operators (12 total), v1-core suite (~250 evaluations), docs package
  (methodology, dataset-card, evaluator-contract, reproducibility, adding-mutations,
  SECURITY, CONTRIBUTING), property + regression tests, worked example.
- **Verification:** 108 tests green offline; ruff + mypy strict clean; full v1-core
  benchmark runs end to end; oracle scores perfectly on all metrics (scoring plumbing
  validated); rules-baseline results manually inspected.
- **Known limitations (documented):** baseline misses ~23% of degrading mutations;
  residual FAR 0.126 concentrated on polished presentation pairs (the measured
  phenomenon); uncertainty-detector phrasing overlap with review class noted in
  methodology and code.
- **Next:** Q13 - optional strict-JSON LLM adapter behind a config flag.

---

## Q13-Q14 release checkpoint (2026-08-25)

- **Status:** complete
- **Changed:** optional strict-JSON LLM adapter (mock-tested, disabled by default),
  corpus-root resolution fixes with regression tests, release notes, final audit,
  SECURITY/CONTRIBUTING, worked example, README quick start with real numbers.
- **Verification:** 127 tests green; ruff+mypy strict clean; clean-venv install +
  foreign-CWD benchmark reproduce committed rules-baseline records byte-for-byte;
  oracle perfect on all metrics; audit found and fixed 2 path-resolution defects.
- **Known limitations:** see docs/final-audit.md (baseline gaps by design, English-
  only corpus, live-LLM path unexercised per policy).
- **Next:** human review (release decision).

---

## Evidence map: Q00-Q14 (added post-release, 2026-08-25)

Single-table mapping of every queue item to its progress record and commit/output
evidence. All items are complete; no queue item is missing.

| Item | progress.md | Primary commits | Output evidence |
|---|---|---|---|
| Q00 charter | Q00 section + D-0001..D-0011 | `19aae78` | README skeleton; docs/threat-model.md, safety.md, decision-log.md, backlog.md |
| Q01 scaffold | (row above; was mislabeled pending, fixed) | `45c0b4e` | pyproject.toml; CLI group with 7 subcommands; CI workflow; first 3 CLI tests |
| Q02 schemas | Q02-Q06 checkpoint | `3b5bee4` | models/* (manifests, evaluation contract); tests/unit/test_schemas.py |
| Q03 corpus loading | Q02-Q06 checkpoint | `d142c8d`, `f85d03a` | parser with line locations; loader/validation; safety policy; 12 parser+corpus+safety tests |
| Q04 canonical reports (first 12) | Q02-Q06 checkpoint | `18c52d9` | corpus/canonical/{authz..perm}-00x (5 valid/4 invalid/3 review), all validating |
| Q05 mutation operators (first 6) | Q02-Q06 checkpoint | `2f2a004` | engine + registry + seed derivation; test_mutations.py determinism/safety suites |
| Q06 planner + materialization | Q02-Q06 checkpoint | `4870db9` | smoke suite -> 29 derived cases byte-stable; CLI materialize/mutate live |
| Q07 evaluator protocol + oracle | Q07-Q12 checkpoint | `8b57a80` | normalized contract; oracle perfect on all v1-core metrics |
| Q08 rules baseline | Q07-Q12 checkpoint | `8b57a80` | documented-limitations baseline; label-independence test |
| Q09 scoring + reporting | Q07-Q12 checkpoint | `3ae5aac`, `58a527b`, `56e26b1` | 9 metrics; JSONL/CSV/Markdown writers; metric unit tests |
| Q10 integration tests | Q07-Q12 checkpoint | `20dbc13`, `6db5fdb` | end-to-end pipeline incl. byte-identical re-run assertion |
| Q11 corpus 40 + 12 operators | Q07-Q12 checkpoint | `9e9b5f9`, `f98107e` | 48 fixtures (16 pair files); v1-core.yaml -> 202 derived + 48 canonical = 250 cases |
| Q12 docs + property/regression | Q07-Q12 checkpoint | `3492591`, `8cff0fd` | methodology/dataset-card/evaluator-contract/reproducibility/adding-mutations; SECURITY/CONTRIBUTING; examples/walkthrough.md; property+regression suites |
| Q13 optional LLM adapter | Q13-Q14 checkpoint | `adab007`, `4f685a9` | strict-JSON adapter; disabled by default; 17 mock-based failure-mode tests; excluded from registry/CI |
| Q14 release audit | Q13-Q14 checkpoint | `a5acb04`, `1a772fe`, `c3dd5ae`, `f3509df`, `0bfb7d2` | clean-venv foreign-CWD reproduction byte-identical; final-audit.md; release notes; 2 audit defects fixed |

Post-audit additions outside the original queue (human-directed, not gaps):
release engineering for v0.1.0/v0.1.1 (`dab8c09`, `7500d4e`) - repo publication,
annotated tags, GitHub Releases, branch protection, manual-only LLM workflow.

**Missing queue items: none.** Deferred ideas live in docs/backlog.md by design.

---

## V0.2 build log (V20-V29, 2026-08-25)

- **Status:** complete through V29; human gates pending (V22 corpus review,
  V26 study review - deliverables ready; V30 secret/pilot approval).
- **Changed:** decision D-0012 (V0.2 charter); independent audit with finding F-1
  fixed + regression tests; +12 balanced canonical fixtures (52 total) and balance
  report; evidence-graph-baseline evaluator; experiments/ infrastructure
  (configs, prompt registry, provenance manifests, byte-identical runner);
  comparative analysis (paired win/loss, per-operator/class, error taxonomy,
  bootstrap CI); budgeted LLM pilot runner + mock tests; evaluator-study guide,
  pilot runbook, reproducibility update; v0.2.0-rc1 release notes.
- **Verification:** 156 tests green offline on clean environment; ruff+mypy strict
  clean; deterministic study reproduces byte-identically from foreign CWD and clean
  install; audit finding corrected with committed regenerated example results.
- **Known limitations:** evidence-graph MDR=0.0 by design (structure-driven trust);
  baseline generality fixes documented as corpus-adjacent calibration; live LLM
  pilot intentionally not executed.
- **Next:** human review of V22/V26 deliverables; V30 secret decision.
