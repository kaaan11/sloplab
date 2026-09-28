# Terminology and claim changes (issue #57)

Documentation-only renames decided by the methodological audit (issue #44) and
applied in issues #45, #47, #50 and #52. No metric code or JSON field names
change: the JSON keys below are the historical field names and remain canonical
in all reports (issue #57 contract).

Historical release/audit documents (`docs/release-notes-*`, `docs/audit-*`,
`docs/remediation-*`, `docs/v26-results-audit.md`) are not edited; they keep the
old names as historical record. Live documents (README.md, methodology.md,
evaluator-study guides, threat-model.md) use the new names and may point here
with a "formerly ..." note.

## Mapping

| Old name / claim | New name / narrowed claim | JSON field (unchanged) | Source | Reason |
|---|---|---|---|---|
| "Mutation detection rate"; "Was a known degradation noticed?"; the score as detection evidence | **Decision-changing target accuracy**: among derived cases whose expected decision is designed to differ from the parent-class default, the rate of matching that expected decision. Rationale sentence: it does not require the parent to be correct nor reflect a real decision change; a blind always-`needs_manual_review` policy scores 0.760 (rules-baseline 0.802), reproduced to 3 decimals from the script below. | `mutation_detection_rate` | #45 | The old name implied the evaluator "detected" a mutation; actually it scores agreement with an *authored target decision*, and blind policies score high. |
| "Quality-neutral mutations"; "substance-neutral edits" | **Decision-preserving mutations**: expected decision equals the parent-class default. 93 of the 141 such cases in the v0.2 study come from operators whose `dimension_deltas` lower quality dimensions; preserving the decision is not preserving quality. | (derived-case population, no single field) | #47 | The old names conflated decision stability with content-quality stability. |
| "Robustness delta" | **Decision-preserving drift** | robustness/drift component of metric bundles | #45, #47 | Clarifies it measures decision wobble on decision-preserving cases only. |
| "Presentation susceptibility: Does polished language buy acceptance for broken content?" (broad phrasing) | Name kept; scope narrowed to operator-generated presentation mutations. The historical `professionalize_language` combines style and an authorization cue; new `professionalize_style` isolates style, while `add_authorization_preamble` isolates the cue and is excluded from this metric. The 8 authored plain/polished pairs are reported separately. | `presentation_susceptibility` | #50 | The old question over-claimed coverage and confused two interventions. |
| Auxiliary Robustness Score quoted without caveat | Legacy score retained in machine-readable metrics but omitted from current human-facing comparisons. A constant always-`needs_manual_review` policy with confidence `0.5` scores 0.791 (rules-baseline 0.839); it must not be used for ranking. | `robustness_score` | #45 | The score is not blind-policy safe. The older 0.740 control inherited varying rules confidences. |
| Threat model "Fixture leakage into training data" as a privacy-mitigated threat | Split outcomes: (a) privacy - synthetic corpus leaks no real data; (b) measurement validity - the public CC0 corpus may be in an LLM's training data; that is an explicit, unmitigated risk. | (none) | #52 | Privacy and measurement-validity risks were conflated; (b) is not mitigated. |

## Reproduction of the blind-policy numbers

```bash
uv run python scripts/blind_policy_compare.py
```

Command run against the committed
`benchmarks/results/v1-core-example/run.jsonl`:

```
| metric | rules-baseline | always-accept | always-reject | always-needs_manual_review |
|---|---:|---:|---:|---:|
| mutation_detection_rate | 0.8020833333333334 | 0.0 | 0.23958333333333334 | 0.7604166666666666 |
| decision_accuracy | 0.8484848484848485 | 0.1750841750841751 | 0.29292929292929293 | 0.531986531986532 |
| false_reassurance_rate | 0.09387755102040816 | 1.0 | 0.0 | 0.0 |
| robustness_score | 0.8385 | 0.2125 | 0.5901 | 0.791 |
```

All fixed controls use confidence `0.5`. The script also prints paired
parent/child diagnostics with explicit denominators. The earlier 0.7395
auxiliary score came from copying the rules evaluator's per-case confidences
into the always-review control; that control was not fully constant.

(JSON field names keep the historical names per the issue #57 contract.)

## Related issues

- #44 methodological audit (found the naming/claim problems)
- #45 blind-policy baseline and score caveats
- #47 relabeling of the derived-case populations
- #50 pair/operator analysis and susceptibility scope
- #52 leakage/privacy threat separation
- Later measurement redesign is tracked under #45, #46, #47, #50 and #52;
  this document preserves the original #57 terminology decision.
