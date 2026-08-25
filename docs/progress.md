# SlopLab Progress

Build queue status. Updated after every completed queue item.

## V1 acceptance criteria

- [ ] At least 40 controlled canonical fixtures (valid / invalid / review / presentation-paired).
- [ ] At least 12 mutation operators, each with expected-effect tests.
- [ ] At least 2 evaluator baselines (rules-baseline + oracle; optional LLM adapter excluded from CI).
- [ ] One-command reproducible benchmark.
- [ ] Mutation-level, report-level, and evaluator-level metrics.
- [ ] JSONL, CSV, and Markdown outputs.
- [ ] Safety policy and dataset provenance records.
- [ ] Benchmark example results committed under `benchmarks/results/`.
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
| Q07 evaluator protocol + oracle | pending | |
| Q08 rules baseline | pending | |
| Q09 scoring + reporting | pending | |
| Q10 integration tests | pending | |
| Q11 corpus 40 + 12 operators | pending | |
| Q12 regression/property/examples/docs | pending | |
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
