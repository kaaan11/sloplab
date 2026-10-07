# SlopLab Progress

Build queue status. Updated after every completed queue item.

## October maintenance and experiment closeout — 7 October 2026

- The fresh [mutation-repeat study](nemotron-mutation-repeats-2026-10-07.md)
  used its 891-call ceiling: 890 valid responses, one preserved transport failure,
  no unstarted evaluations and no supplemental calls. All 90 bundles completed.
- Complete triples: 60 canonical (56 unanimous, four changed) and 236/237
  mutations (217 unanimous, 19 changed). Mutation target agreement is 426/710
  valid observations. Full-suite metrics remain withheld for incomplete repeat 0.
- A registered-source/public-input snapshot and separate offline replay preserve
  reproducibility after maintenance commits or in shallow clones. Original
  protocol, source hashes, outcome ledgers and summary were not rewritten.
- The [assisted user adjudication](user-adjudication-2026-10-07.md) decides two
  card claim disagreements and accepts uncertain action change for two pairs.
  Public exports contain aggregate outcomes only; original responses and targets
  remain intact.
- Report Builder lifecycle waits were traced to sandbox `EPERM` on asyncio's
  cross-thread wakeup socket. The four affected/related shutdown tests passed
  outside that restriction (3.59 seconds). No UI code workaround was introduced.
- Maintenance validation: all 1,287 offline tests passed outside the socket
  restriction; Ruff lint/format and strict mypy (169 files) passed. Corpus
  validation checked 60 fixtures with no errors or warnings. BYOE and repeated
  HTML reports passed with byte-identical output; recorded-study replay passed.
  See the [validation record](../experiments/results/llm-pilot/2026-10-07/maintenance-validation.json).
- Dots coverage recovery, live Jev integration and other optional product and
  validation expansions remain explicitly deferred in [backlog](backlog.md).

## Nemotron remaining repeats and mutation evaluation — 4 October 2026

- The remaining 50 canonical cases received three observations each: 150 calls,
  149 valid responses, one `transport.error` on racecond-018. The original
  aggregate correctly withholds stability for incomplete coverage.
- The user authorized up to three additional free calls. A separate three-observation
  replacement block for racecond-018 passed; original two successes and failure
  are preserved. The [defined 60-case matrix](nemotron-full-repeats-2026-10-04.md)
  uses 180 valid observations: 57 unanimous cases, three flips, 177 target matches.
- The original mutation plan made zero calls because its repeat gate failed.
  A separately registered continuation then dispatched all 60 fresh canonical
  controls and 237 existing mutations: 297 calls, 296 valid responses, one
  `transport.error`. Before the mutation supplement: **450 calls, 448 valid, two failures**.
- The [mutation report](nemotron-mutations-2026-10-04.md) records 59/60 canonical
  target matches and 136/236 matches among valid variants. The missing variant is
  `mut-loginject-031-confidence-overstatement-05`. No full-suite paired metrics
  are reported for incomplete success coverage.
- The user authorized at most three further free calls, ceiling 453. A separately
  registered one-call supplement succeeded. Total continuation: **451 calls,
  449 valid responses, two preserved failures**. The matched mutation dataset
  has 297 valid records: 59/60 control matches, 137/237 variant matches,
  196/297 overall matches and 2/96 decision-changing target matches. Production
  paired metrics were independently recomputed without rewriting the original study.
- Both original/continuation protocols, intact bundles, frozen sources, summaries
  and offline replays are saved. Historical Dots results and targets are unchanged.
  Local full tests, lint/format, strict mypy and result/document regressions passed.
- The completion runner retains its registered bytes; a source-specific E501
  exception preserves one 101-character literal without changing scientific evidence.

## Nemotron repeat pilot — 4 October 2026

- A separately registered first-ten-canonical pilot ran three new observations
  per case: **30 requests, 30 valid responses, zero failures/not-run outcomes**.
- All ten cases had unanimous decisions (zero flips); 30/30 decisions matched
  authored targets. The mean within-case confidence range was 0.07 on the 0–1
  scale. No provider decoding seed was configured.
- The [report](nemotron-repeat-2026-10-04.md), pre-dispatch protocol, integrity-marked
  bundle, frozen runner, derived summary and offline replay preserve the evidence.
- This establishes repeat observations for ten selected public cases only.
  The other 50 canonical cases, the GraphQL disagreement and mutation studies
  remain separate future work. Historical studies/targets were not changed.

## Nemotron canonical continuation — 4 October 2026

- The user selected Nemotron and excluded live Jev testing from the current
  continuation. GitHub's `llm-bench` model variable is now
  `nvidia/nemotron-3-super-120b-a12b:free`, using the OpenRouter chat endpoint.
- A three-case smoke passed, followed by a separately registered 60-case study:
  **60 requests, 60 valid responses, zero failures, 59/60 authored-target matches**.
  Each case has one observation; no repeat stability is claimed. The only
  disagreement is `canonical-graphql-028` (target review, model reject).
- Six integrity-marked bundles, the pre-dispatch protocol, aggregate summary,
  path-redacted runner source with separate provenance hashes and offline replay
  are archived with the
  [study report](nemotron-canonical-2026-10-04.md). Inputs, prompt, source commit,
  request accounting and all 60 unique case identities were verified.
- Historical Dots and model-panel results retain their original coverage.
  Nemotron repeats/mutation studies and further independent human validation
  remain future work. The optional Jev adapter is implemented and mock-tested;
  its live workflow integration is deferred under the current model choice.
- README quick-start commands, adapter descriptions and current result/status
  claims were reconciled with the code and recorded evidence.

## v0.3.0 release preparation — 4 October 2026

- Package/source/lockfile and current documentation now identify v0.3.0.
  [Release notes](release-notes-v0.3.0.md) cover the delivered integrations,
  contribution/reporting tools, integrated corrections and research limitations.
- Historical bundles keep their original versions and hashes. The source-span
  regression explicitly checks the historical/current generator stamps and
  compares every other manifest/report byte without changing archived results.
- Local Ruff lint/format, strict mypy and **1264 tests** passed. All 60 canonical
  fixtures validate with zero errors or warnings. A fresh wheel environment ran
  both rules and lexical evaluators over all 297 cases outside the checkout and
  generated offline HTML.
- Release archives are built from a clean Git checkout so local worktrees and
  untracked notes cannot enter the source distribution. The publish gate is
  successful Python 3.11/3.12/3.13 CI on the release PR and merged main commit.
- Release PR #85 merged and v0.3.0 was published after both CI runs passed;
  wheel, source archive and SHA-256 checksums accompany the release.
- Dots HTTP 400 failures, remaining human disagreements and future independent
  studies remain explicit backlog items. Release preparation makes no live
  model calls.

## October 2026 follow-up checkpoint

- **Coverage:** nine private cards now have 27/27 valid model votes. The public
  realized-edit panel has 420/423 votes after two controlled recovery supplements;
  three Dots votes still fail with HTTP 400.
- **Canonical diagnosis:** Dots sqlx-002 still fails. A separately registered
  NVIDIA study has 3/3 valid observations; original Dots coverage stays 59/60.
- **Delivered:** bounded recovery ledgers and validation, single-call diagnostic,
  offline repeat/seed variance CLI and deterministic September replay artifact;
  installed evaluator plugin discovery/selection and a clean-wheel-tested example.
  The offline `text-quality-baseline` is also delivered, with explicit manual-review
  semantics, 297 replayed public-suite records and a clean-wheel benchmark.
- **Human dependency:** second-human packet with Turkish instructions is ready
  for the user's friend (nine cards, 18 pairs). Filled judgments are received
  and structurally validated: card action/confidence agreement 9/9, claim status
  agreement 16/18. The p10 rationale revision is received and verified with
  unchanged decisions and aggregate counts; see the
  [independent review](independent-human-review-2026-10-03.md).
- **Evidence:** [coverage recovery](coverage-recovery-2026-10-03.md) and
  [variance guide](variance-analysis.md). Historical results below retain their
  original scope; optional expansions remain in [backlog](backlog.md).
  [Plugin/second recovery delivery](plugin-and-coverage-followup-2026-10-03.md)
  records the latest implementation and coverage checkpoint.
  [Text quality delivery](text-quality-delivery-2026-10-03.md) records the new
  lexical control, source-bound artifacts and 1264 passing tests.

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
  fixed + regression tests; +12 balanced synthetic fixtures (corpus at 60 fixture files / 52 logical reports) and balance
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
- **Post-audit addendum (V26 results audit):** root-caused evidence-graph MDR=0.0 /
  FAR=0.44 - one contract-conformance defect fixed (undermined observations now break
  the support edge) + eleven-family blindness confirmed as by-design; evaluator
  repositioned as negative control in README/study docs. Post-fix study: graph
  acc 0.582 / MDR 0.125 / FAR 0.394. Evidence: docs/v26-results-audit.md,
  tests/unit/test_evidence_graph_families.py (`ca731f0`).

- **v0.2.2 remediation (branch `remediation/v0.2.2`):** independent v0.2.1 audit
  findings R01-R07 implemented - no-op derived cases eliminated (population
  340 -> 297; 43 clones removed; clone scan now 0/237), impact-inflation
  word-boundary fix (removes "fcritical"/"alcritical" artifact corruption),
  safety enforcement tested at materializer + mutate CLI boundaries, opaque
  evaluator case handles (identity-free evaluator input), version/docs
  regeneration to 0.2.2 with extended doc-consistency guard, fence-aware
  presentation operators, provenance heading fix. Artifacts regenerated;
  study reruns byte-identical; 183 tests + ruff + mypy strict green.
  Evidence: docs/remediation-audit-v0.2.2.md,
  docs/release-notes-v0.2.2.md, tests/regression/test_remediation_v022.py.
