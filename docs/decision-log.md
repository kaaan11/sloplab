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
