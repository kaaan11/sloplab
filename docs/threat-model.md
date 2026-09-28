# SlopLab Threat Model

## What SlopLab is for

SlopLab measures how robust vulnerability-report triage evaluators are against
degraded, manipulated, or low-quality report content: missing evidence, inflated
impact, fabricated identifiers, contradictory claims, and persuasive-but-empty
presentation.

## Assets being protected

1. **Benchmark integrity** - results must reflect evaluator behavior, not fixture
   leakage or label contamination.
2. **Corpus safety** - fixtures must never contain working exploits, real target
   information, private data, or unlicensed material.
3. **Reproducibility** - published numbers must be regenerable from committed inputs.

## Threats to benchmark integrity (and mitigations)

| Threat | Mitigation |
|---|---|
| Evaluator peeks at ground-truth labels | Labels reach evaluators only via documented context fields; rules baseline is tested with metadata stripped; oracle is test-only and clearly marked |
| Evaluator infers expected mutation from case ids/paths | Evaluators receive only opaque deterministic handles (`case-<sha256[:16]>`) as case id and report identity; true identifiers live solely in benchmark records/provenance (v0.2.2, R04); leak tests assert operator names are absent from evaluator-visible input |
| Fixture leakage into training data of LLM evaluators | **Privacy:** the corpus is synthetic with reserved namespaces (`example.*` hosts, `CVE-2099-*`), reducing exposure of real targets and private data (docs/dataset-card.md). **Measurement validity:** the corpus, labels and prior results are public; an LLM may have seen them. The [exposure register](exposure-register.md) records first publication, and fresh private case cards follow an owner-before-model protocol. The public corpus remains a development set, not an unseen accuracy test. No claim is made that any particular model is contaminated. |
| Overfitting benchmarks via label tuning | Expected decisions live in manifests, reviewed alongside reports; known baseline failures are documented, never tuned away |
| Silent non-determinism | Seeded mutations; no wall-clock/locale/dict-order dependence; recorded run metadata (version, commit, config hash, seed) |
| Metric gaming via single summary score | Current human-facing reports use per-metric results; the legacy weighted score remains only in machine-readable bundles and cannot rank evaluators (#45) |
| Evaluator matches mutation-template wording instead of report content (surface signature) | **Open risk, not mitigated.** Several operators insert fixed phrases, and the rules baseline contains regexes sharing literal text with them. Pre-registered ablation: disabling literally-matching patterns lowered decision-changing target accuracy (formerly "mutation detection") 0.802 → 0.625, not separable from random-pattern controls (rank p ≈ 0.095, verdict inconclusive). Post-hoc, with a hand-audited set of 22 template-sharing patterns, it fell 0.802 → 0.250 while disabling the other patterns left it unchanged. Report this metric as target agreement against a blind policy, not semantic competence; separating signature from meaning needs counterparts with different surface forms |

## What SlopLab is NOT (non-goals)

- Not a scanner, fuzzer, or exploitation tool. It never touches network targets.
- Not a generator of working exploits. Mutations operate on prose, not payloads.
- Not a source of credible-looking attack material. All fabricated identifiers use
  reserved namespaces (`CVE-2099-*`, RFC 2606 domains, synthetic product names).
- Not an optimizer for evading triage systems. Operators model *quality degradation*,
  not bypass techniques, and are documented individually.

## Abuse-resistance posture

SlopLab's operators make reports *worse* (less complete, less consistent, noisier)
or *more polished without more substance*. They do not provide:
- credential/identity impersonation guidance,
- real-product attribution of false claims,
- automation for submitting deceptive reports to real programs.

Contributions adding any of these are rejected by policy (see safety.md).
