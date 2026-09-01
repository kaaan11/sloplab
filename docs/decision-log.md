# SlopLab Decision Log

Each entry records a material engineering decision, its context, and consequences.

## D-0001 - Project charter and scope lock

- **Date:** 2026-08-25
- **Decision:** SlopLab V1 is exclusively an offline adversarial benchmark/evaluation
  harness for vulnerability-report triage evaluators. It is not a live triage product,
  scanner, exploit framework, web application, RAG system, or multi-agent framework.
- **Non-goals (binding for V1):**
  - No scanning, attacking, exploiting, or interacting with real targets.
  - No working exploit payloads; no bug-bounty submissions.
  - No absolute truth verdicts on reports; only evaluator-consistency measurement.
  - No network access, API keys, or LLM required for tests/benchmarks.
  - No evasion/triage-bypass optimization.
- **Consequences:** Every feature must map to a V1 acceptance criterion or go to
  `docs/backlog.md`.

## D-0002 - Expected decisions are explicit, not inferred

- **Decision:** Every derived-case manifest carries an explicit `expected_decision`
  (`accept` | `reject` | `needs_manual_review`) plus descriptive `expected_effect`
  fields. Scoring consumes only `expected_decision`.
- **Rationale:** A mutation does not always invalidate a report (e.g., impact inflation
  degrades claim quality while the underlying bug remains real). Encoding this as data
  keeps scoring deterministic and auditable instead of burying policy in code.

## D-0003 - Synthetic identifier policy (hard safety rule)

- **Decision:** Mutation operators may only emit identifiers from reserved namespaces:
  - CVE IDs use the fictional far-future year: `CVE-2099-NNNN`, never a real year.
  - Hostnames/URLs use RFC 2606 reserved domains (`example.com`, `example.org`,
    `example.net`, `example.edu`) and subdomains of them.
  - Product/component names come from a fixed synthetic list defined in
    `src/sloplab/safety/policy.py`.
  - Person names come from a fixed synthetic list; no real researcher/vendor names.
- **Enforcement:** `sloplab.safety.policy` provides the generators; tests assert that
  all generated adversarial content matches these patterns.

## D-0004 - Tooling stack

- **Decision:** Python >= 3.11 (developed on 3.14); uv for environment management;
  pydantic v2 for schema validation (actionable errors are an explicit exit criterion);
  click for CLI; PyYAML for manifests; pytest + ruff + mypy as quality gates.
- **Rejected alternative:** stdlib-only implementation. Rejected because actionable,
  schema-level errors for malformed manifests are required and reimplementing them adds
  complexity without benefit.

## D-0005 - Git workflow

- **Decision:** Local repository, single `main` branch, small conventional commits per
  queue item. Milestone branches would add ceremony without any review infrastructure
  (no remote configured during initial build).

## D-0006 - Oracle reads labels via evaluation context only

- **Decision:** The oracle evaluator derives output from harness-supplied metadata in
  `EvaluationContext`, never from report text. The rules baseline must not access
  label-bearing metadata at evaluation time. Tests assert identical rules-baseline
  behavior when metadata is stripped.

## D-0007 - Manifest format is YAML sidecar files

- **Decision:** Each fixture is a directory containing `report.md` plus `manifest.yaml`
  (canonical) or a generated `mutation-manifest.yaml` (derived).
- **Rationale:** YAML is readable for hand authoring; PyYAML round-trips cleanly.

## D-0008 - Deterministic seeding strategy

- **Decision:** Every mutation is seeded by
  `sha256(base_seed | parent_id | operator_name | variant_index)` truncated to 64 bits.
  No wall-clock, filesystem-order, hash-randomization, or locale dependence anywhere in
  mutation, evaluation, or scoring. Benchmark runs record everything needed to
  reproduce byte-identically (version, git commit when available, config hash, seed).

## D-0009 - Metrics consume only the normalized contract

- **Decision:** Scoring operates exclusively on `EvaluationResult` objects plus case
  manifests. Evaluators are free-form internally; anything they want scored must flow
  through the normalized decision / confidence / dimensions / findings contract.

## D-0010 - LLM adapter is optional, strict, and CI-excluded

- **Decision:** The LLM evaluator is disabled by default, requires explicit
  configuration, returns only schema-validated results, and treats malformed output /
  timeouts / API errors as failed evaluations rather than crashes. No live calls occur
  in tests; all adapter failure modes are covered with mocks.

## D-0011 - M7 release direction (human-approved)

- **Date:** 2026-08-25
- **Decision:**
  1. The `needs_manual_review` class is retained in V0.1.0 ground truth; forcing
     accept/reject labels onto genuinely ambiguous fixtures would be less honest.
  2. The Robustness Score remains an auxiliary summary only. Dimensional metrics are
     primary everywhere: they appear first in generated Markdown reports (the score is
     labeled "Auxiliary" and printed last) and the README's example table contains no
     composite score.
  3. No git tag and no remote push for V0.1.0; publication decisions (visibility,
     tag, CI/secret strategy) are deferred to a subsequent human checkpoint.
- **Consequences:** Release-candidate state stands as committed at HEAD of `main`.

## D-0012 - V0.2 scope lock and evaluation-discrimination mission

- **Date:** 2026-08-25
- **Decision:** V0.2 proves the framework can discriminate robustness differences
  between evaluators. Binding constraints:
  - Corpus grows to AT MOST 60 canonical fixtures (48 existing + <= 12 new), balanced
    across classes; all synthetic, English, CC0-1.0, safety-policy compliant.
  - The 12 existing mutation operators are frozen: no additions, no semantic changes,
    no label adjustments to flatter results. Verified-defect fixes only, each with a
    regression test.
  - One new evaluator (`evidence-graph-baseline`) joins the deterministic set. It must
    be label-independent and explainable; independence is enforced by tests.
  - Comparative analysis becomes first-class: paired win/loss, per-operator and
    per-report-class breakdowns, error taxonomy, bootstrap confidence intervals
    (seeded -> reproducible), and repeat-stability measures for stochastic evaluators.
  - Experiment infrastructure lands under `experiments/` with versioned configs,
    prompt registry, run manifests, and full provenance (commit SHA, hashes, seed,
    repeat index, request/error/timeout counters). Raw LLM responses are never stored;
    only schema-validated normalized results.
  - Live LLM calls remain opt-in behind the `llm-bench` environment; the single manual
    step for the pilot is adding that environment secret. Pilot protocol: 1 model,
    60 selected cases, 3 repeats, hard request/timeout budgets from config.
  - Robustness Score stays auxiliary; dimensional metrics lead all reporting.
- **Non-goals (unchanged):** no web UI, no real-target integration, no exploitation,
  no RAG, no agent orchestration, no real bug-bounty collection.
- **Branch layout:** feat/v0.2-audit-corpus, feat/evidence-graph-baseline,
  feat/evaluator-study-analysis, feat/llm-pilot-preparation, release/v0.2.0-rc1;
  merges happen locally, pushes executed by the maintainer at checkpoints (session
  push-permission constraint, consistent with D-0005).

## D-0013 - V0.2 closes without the live LLM pilot

- **Date:** 2026-08-25
- **Decision:** No API key is available, so V0.2 finalizes on the deterministic
  evaluator study alone. The pilot infrastructure ships complete (adapter, budgets,
  mock tests, runbook) and is explicitly recorded as a future opt-in study in
  docs/backlog.md. v0.2.0 is tagged on the latest green main commit; the rc1/rc2
  pre-releases remain untouched. Final v0.2.0 must not be presented as including any
  live-model observation.

## D-0014 - Cross-run decision history is run provenance, not scoring

- **Date:** 2026-08-31
- **Decision:** Decision history across runs ships as
  `src/sloplab/experiments/history.py`, opt-in behind `--history` on both
  `sloplab benchmark` and the pilot runner. Binding choices:
  - It lives under `experiments/`, not `scoring/`. Every entry is timestamped,
    and `docs/reproducibility.md` guarantees no wall-clock input participates in
    mutation, evaluation, or scoring. History is provenance about runs, not an
    input to them.
  - `evaluators/` may import neither `sloplab.scoring` nor `sloplab.experiments`,
    enforced by an AST-scanning regression test. An evaluator able to read its
    own previous decision would be gaming the benchmark exactly as the evaluator
    contract's rule 4 forbids; the ban is deliberately wider than the one module
    at issue so the loophole cannot reopen.
  - One run contributes one entry per case. A stochastic evaluator's repeats are
    reduced to their majority decision, because writing one entry per repeat
    would let `stable_cases(threshold=3)` be satisfied inside a single run - a
    second, worse copy of `repeat_stability`.
  - Entries record `model` and `corpus_version`, and `stable_cases` filters on
    them. Comparing decisions across a model swap or corpus revision and calling
    the result "stable" would be the kind of detail-hiding single number this
    project avoids elsewhere.
  - Neither a corrupt file on read nor a failure on write may abort a run; both
    degrade to a warning, and recording happens only after a run's own artifacts
    are on disk. The pilot is the only path that spends money.
- **Consequences:** History accumulates locally and in the deterministic
  benchmark path today. The `llm-benchmark` workflow runs on an ephemeral runner,
  so accumulating history across pilot dispatches requires the operator to carry
  the file forward from the previous artifact; no third-party GitHub Action was
  introduced to automate it.

## D-0015 - Prompt-boundary delimiting ships as a second arm, not as a fix

- **Date:** 2026-08-31
- **Decision:** The LLM adapter gains a `defense: none | delimited` axis and an
  instruction-override operator family. Binding choices:
  - **Arm A stays the measurement.** The undelimited prompt is the control and
    the default. It is pinned by a golden test holding a hand-written literal of
    the exact prompt text, not a comparison against the template itself, which
    would move whenever the template moved. Changing the default would change
    what every published SlopLab number means.
  - **Arm B neutralizes before it wraps.** A fence a report can close from the
    inside is not a defense, so boundary-looking markers - including the bare
    `---` fence Arm A already uses - are replaced with an inert token before
    wrapping, and the finished wrap is checked in code to hold exactly one
    marker pair. The replacement token is what defeats reassembly attacks; the
    fixpoint loop is defense in depth for future pattern changes.
  - **Detection runs on a normalized view, not on literal ASCII.** A first
    implementation matched the exact marker string and was defeated by a plain
    newline between the words, a non-breaking space, a zero-width space inside
    the word, and a Cyrillic homoglyph - with the whole test suite green, because
    every test encoded the same assumptions as the code. Matching now happens on
    a view with format characters dropped, per-character NFKC applied and a
    bounded confusables table folded, with matched spans mapped back to the
    original text. The wrap post-condition counts markers on that view too;
    counting literal ASCII let every one of those bypasses satisfy the check
    meant to catch them. Confusables outside Cyrillic and Greek remain a stated
    limit, and the alternative architecture that would dissolve the whole class -
    a per-case nonce delimiter, unforgeable by construction - is left for review
    rather than decided unilaterally.
  - **Undecidable injection cases are excluded, not counted.** Every operator
    demands `accept` and injected cases keep the parent's expected decision, so
    on a valid parent the payload demands exactly what a correct evaluator would
    answer: obeying and being right are one observation. Those cases are reported
    as `undecidable_cases` and kept out of the rate, which would otherwise
    overstate susceptibility on roughly a third of a balanced suite.
  - **Arm B is two treatments, and says so.** It fences *and* modifies content.
    The neutralized markers are recorded in `EvaluationResult.metadata` so the
    confound is visible rather than hidden, alongside the arm itself - without
    which the two arms' records would be indistinguishable, both being
    `llm-json` at the same version.
  - **Injection needs a safety carve-out, granted narrowly.** safety.md rule 6
    rejects triage bypass techniques and the threat model disclaims evasion
    optimization. Prompt injection is exactly that, so the exception is written
    into safety.md and threat-model.md before the operators exist: generic,
    widely-published payloads only, never tuned against or aimed at a real
    system, impersonation still rejected, and only because a defense is being
    measured against them.
  - **The V1 freeze holds.** D-0012's twelve quality-degradation operators are
    unchanged; injection is a separate family under `MutationCategory.INJECTION`
    and the registry test now asserts the split rather than a bare count, so the
    new family cannot become a back door for growing the frozen set.
  - **Injected cases keep the parent's label.** Injection does not degrade report
    quality, so no dimension is penalised and the expected decision is the
    parent's. This makes `rules-baseline` a negative control: it has no
    instructions to hijack, and a test asserts its decision does not move.
  - **Injection success is a new metric, built on the existing machinery.**
    `false_reassurance` cannot stand in for it - a payload demanding *reject* on
    a valid report succeeds while scoring as `over_rejection` - so
    `injection_success_by_arm` measures agreement with the decision each operator
    declares its payload demands, splitting arms through the existing `group_by`.
  - **The verifier must be the pattern it verifies.** An independent review
    found fifteen defects in this change, all real. Five were Arm-B bypasses, and
    the sharpest was a post-condition looser than the neutralizer: benign prose
    ("end untrustedness") raised and the adapter discarded the evaluation, so any
    report could force its own Arm-B result to be dropped. `wrap_untrusted` now
    counts markers with `_MARKER_RE` itself; a check that can disagree with the
    thing it checks is worse than no check. The fixpoint loop, shown by
    instrumentation to never do more than one productive pass and to return dirty
    text silently on exhaustion, is now one pass plus a verifying pass that
    raises.
  - **Narrowing a pattern is not free.** Re-review of the fixes found that the
    blank-line fix had over-corrected into a regression: an unbounded separator
    matched `end` / `begin` followed by a paragraph break and `Untrusted` in
    ordinary prose, so Arm B deleted report text that Arm A kept - the confound
    the arm exists to avoid. Dashes now license a permissive separator; undashed
    words must share a line. Likewise the case-folding fix left Cyrillic `Н` and
    `Г` out while holding their Greek counterparts, so a sweep over every marker
    letter in both scripts replaced the spot checks.
  - **A forward-version history file is refused, not overwritten.** Treating it
    as corruption destroyed intact data from a newer build. Corruption carries no
    information; a newer file is somebody's history.
  - **The metered path verifies its own provenance.** The pilot refuses to run
    when the evaluator's arm differs from the config's, rather than recording a
    manifest that misreports the treatment; run ids mix in a nanosecond reading
    so two dispatches in one second cannot collide; and history tags the producer
    as `model+arm`, since one model under two prompt treatments is two producers.
- **Consequences:** No default-path behavior changes: `defense` defaults to
  `none`, the v1-core suite is untouched, and the committed reference results
  still reproduce. Injection operators are opt-in through a suite's operator
  list. The pilot records its arm in the run manifest, and both the arm and the
  history file are selectable from the metered dispatch (`--defense`,
  `--history`) rather than requiring a commit.
