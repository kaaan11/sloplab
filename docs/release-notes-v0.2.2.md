# Release Notes - v0.2.2

Audit-remediation patch over the v0.2.x line. Scope is limited to findings from
the independent v0.2.1 audit; **no new product features, no label changes, no
evaluator-behavior changes to the deterministic baselines.** See
docs/remediation-audit-v0.2.2.md for the finding-by-finding evidence map.

## What changed

### Benchmark integrity

- **R01 - No-op derived cases eliminated.** A mutation plan whose output equals
  its parent text is never written as a derived case; `confidence_overstatement`
  additionally reports a machine-readable no-op signal. The committed study and
  reference artifacts were regenerated: 43 unmutated clones removed, population
  340 -> **297 cases** (60 canonical + 237 derived). Presentation-population
  metrics are no longer diluted by non-mutated copies.
- **R02 - `impact_inflation` word boundaries.** Calibration replacements are now
  regex word-boundary anchored. Words such as "flow" / "allow" / "below" can no
  longer be corrupted ("fcritical"/"alcritical" defects in two v0.2 artifacts are
  gone); provenance records the actual matched text.

### Safety enforcement

- **R03 - Output-boundary validation.** The materializer refuses unsafe derived
  cases (already implemented, now regression-tested with a fake unsafe operator),
  and `sloplab mutate` validates its output before writing and fails closed.

### Identity hygiene

- **R04 - Opaque evaluator input.** Evaluators receive an opaque, deterministic
  case handle (`case-<sha256[:16]>`) as `context.case_id` and as
  the report's `fixture_id`/`path`. Mutation identity is available only in
  recorded provenance. Contract, methodology, and threat model updated; leak
  tests added.

### Consistency and cleanup

- **R05 - Release/version/docs consistency.** Package, source, CLI, generator
  stamp, and lockfile now say `0.2.2`. Documentation URL corrected. Stale counts
  and figures replaced across dataset card, suite/study config descriptions, and
  walkthrough; study doc figures regenerated from artifacts; V26 audit annotated.
  The documentation-consistency guard now covers all of these, not just README.
  The committed reference result was regenerated at v0.2.2 and the documented
  reproduction command reproduces it byte-identically.
- **R06 - Low-risk cleanup.** Presentation operators are code-fence aware (fenced
  content is never rewritten). `add_irrelevant_detail` records the actual appended
  block heading; dead code and a duplicated comment removed.

## Regenerated numbers (deterministic study, seed 20260825)

| Metric | rules-baseline | evidence-graph-baseline |
|---|---|---|
| Decision accuracy | 0.811 | 0.542 |
| Mutation detection rate | 0.802 (77/96) | 0.125 (12/96) |
| False reassurance rate | 0.094 | 0.429 |
| Over-rejection rate | 0.000 | 0.000 |

MDR denominators are unchanged (96 degrading mutations): the removed clones were
quality-neutral by construction. Accuracy/FAR/susceptibility shifted only through
removal of the 43 non-mutated clone cases from those populations.

## Verification

183 offline tests green (162 prior + 21 new remediation/doc-guard tests); ruff
check/format clean; mypy strict clean; deterministic study reruns byte-identical;
clean wheel install + foreign-CWD reproduction verified.
