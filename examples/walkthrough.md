# Worked Example: canonical -> mutated -> evaluated

This walkthrough uses only files committed in this repository.

## 1. The canonical fixture

`corpus/canonical/authz-001/report.md` is a **valid**-class report (expected triage
decision: `accept`) describing a cross-tenant document read in fictional DemoVault.
Its manifest pins ground truth:

```yaml
id: canonical-authz-001
report_class: valid
ground_truth:
  reproducible: true
  impact_class: medium
  expected_dimensions: {reproducibility: 0.94, evidence_completeness: 0.92, ...}
```

## 2. Mutate it

```bash
uv run sloplab mutate corpus/canonical/authz-001 --operator impact_inflation --seed 20260825
```

The operator rewrites calibrated impact language ("medium confidentiality impact")
into breach rhetoric inside the Impact section and records its choices:

```text
# parameters: {'calibration_replacements': ['medium->critical'], 'appended_sentence': '...'}
```

The bug itself is unchanged - only the claim quality degraded. That is why the
derived case's expected decision is `needs_manual_review`, not `reject`.

## 3. Run the full suite

```bash
uv run sloplab benchmark benchmarks/suites/v1-core.yaml \
    --evaluator rules-baseline --out /tmp/example-run
```

Among the ~250 scored cases are all mutations of `canonical-authz-001`. Inspecting
one record from `/tmp/example-run/run.jsonl`:

```json
{"case_id": "mut-authz-001-impact-inflation-01", "case_kind": "mutated",
 "parent_id": "canonical-authz-001", "operator": "impact_inflation",
 "expected_decision": "needs_manual_review", "decision": "needs_manual_review",
 "correct": true, ...}
```

## 4. Read the summary

```bash
uv run sloplab report /tmp/example-run/run.jsonl | head -20
```

Committed results for the full V1 suite live in
`benchmarks/results/v1-core-example/` (`report.md` for humans, `metrics-*.json`
for tooling, `results.csv` for spreadsheets).
