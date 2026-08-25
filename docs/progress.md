# SlopLab Progress

Build queue status. Updated after every completed queue item.

## V1 acceptance criteria

- [x] 48 controlled canonical fixtures (12 valid / 10 invalid / 10 review / 8 presentation pairs as 16 files).
- [x] 12 mutation operators, each with behavior + determinism + safety tests.
- [x] Oracle + rules-baseline evaluators; optional LLM adapter tracked in Q13.
- [x] One-command reproducible benchmark (`sloplab benchmark`).
- [x] Mutation-level, report-class-level, and evaluator-level metrics.
- [x] JSONL, CSV, and Markdown outputs.
- [x] Safety policy enforced by validation; dataset card committed.
- [x] Full v1-core results committed under `benchmarks/results/v1-core-example/`.
- [ ] Clean-install reproduction verified.

## Queue status

| Item | Status | Notes |
|---|---|---|
| Q00 charter | complete | README skeleton, threat model, safety policy, decision log, backlog |
| Q01 scaffold | pending | |
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
| Q13 optional LLM adapter | pending | |
| Q14 release audit | pending | |

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
