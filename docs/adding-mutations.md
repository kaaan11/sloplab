# Adding Mutation Operators

Mutation operators are deterministic, text-level transformations that model
specific report-quality degradations. This guide walks through adding one.

## Hard requirements

1. **Safety:** only emit identifiers from approved namespaces
   (`sloplab.safety.policy`): `CVE-2099-*`, RFC 2606 domains, synthetic product/
   person lists. Never reference real products, people, or advisories.
2. **Determinism:** all randomness comes from the provided `rng`
   (`random.Random(seed)`); same seed + input => byte-identical output.
3. **No-op transparency:** if a required section is missing, return the original
   text with `{"note": ...}` parameters; the materializer will skip and record it.
4. **Scope:** degrade quality or manipulate presentation only. No exploit content,
   no evasion technique that would materially assist deceptive-report writing.

## Anatomy

```python
from sloplab.mutations.base import MutationSpec, register
from sloplab.models.enums import CLAIM_EVIDENCE_CONSISTENCY, Decision, MutationCategory, ReportClass


class MyOperator:
    spec = MutationSpec(
        name="my_operator",
        category=MutationCategory.IMPACT,
        description="One paragraph: what it does to the report.",
        dimension_deltas={CLAIM_EVIDENCE_CONSISTENCY: -0.3},
        decision_by_parent_class={ReportClass.VALID: Decision.NEEDS_MANUAL_REVIEW},
        claim_quality="degraded",
    )

    def apply(self, document, rng, parameters=None):
        ...
        return mutated_text, {"recorded": "choices"}


register(MyOperator())
```

- `dimension_deltas` are applied to the parent's expected dimensions (clamped to
  [0, 1]) to produce the derived case's scoring target.
- `decision_by_parent_class` defines the derived case's expected triage decision
  per parent class; classes you omit keep their default expectation.

## Checklist before submitting

- [ ] Unit tests: determinism (same seed byte-equal), behavior assertions,
      safety-policy compliance of outputs across seeds.
- [ ] Registry count test updated (`tests/unit/test_mutations.py`).
- [ ] Suite coverage considered: add the operator to relevant class policies in
      `benchmarks/suites/v1-core.yaml` (or justify exclusion).
- [ ] `docs/methodology.md` unaffected (definitions) - operator metadata lives in
      code, not in metric definitions.
- [ ] Run `uv run pytest && uv run mypy src tests && uv run ruff check .`.

## What gets rejected

Operators optimizing evasion or triage bypass, emitting real-world identifiers, or
producing working exploit content violate docs/safety.md and will not be merged.
