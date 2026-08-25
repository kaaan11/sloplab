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
| Fixture leakage into training data of LLM evaluators | Corpus is fully synthetic with reserved namespaces; leakage therefore degrades gracefully rather than exposing sensitive data |
| Overfitting benchmarks via label tuning | Expected decisions live in manifests, reviewed alongside reports; known baseline failures are documented, never tuned away |
| Silent non-determinism | Seeded mutations; no wall-clock/locale/dict-order dependence; recorded run metadata (version, commit, config hash, seed) |
| Metric gaming via single summary score | Primary reporting is per-metric; Robustness Score is explicitly auxiliary |

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
