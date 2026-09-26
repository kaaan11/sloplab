# Evaluator Contract

Every SlopLab evaluator implements one protocol (`src/sloplab/evaluators/base.py`):

```python
class Evaluator(Protocol):
    name: str
    version: str

    def evaluate(
        self,
        report: ReportDocument,
        context: EvaluationContext,
    ) -> EvaluationResult: ...
```

## Input

- `report: ReportDocument` - parsed Markdown with sections and source line ranges
  (`report.find_sections(pattern)`, `report.section_text(pattern)`).
- `context: EvaluationContext` - harness-supplied:
  - `context.case_id` - an **opaque case handle** (`case-<sha256[:16]>`) to echo
    back. Since v0.2.2 the handle is an opaque, deterministic identifier and
    encodes neither the fixture nor its mutation; do not attempt to parse it.
    The true case identifier is restored automatically in recorded results.
  - The report's `fixture_id`/`path` carry the same opaque handle (v0.2.2, R04).
  - `context.labels` - ground truth (expected decision/dimensions). **The oracle is
    the only built-in evaluator that reads labels.** Content-based evaluators must
    ignore `labels`; a unit test asserts identical output with labels stripped.

## Output (normalized)

```python
EvaluationResult(
  evaluator_name=..., evaluator_version=..., case_id=context.case_id,
  decision="accept" | "reject" | "needs_manual_review",
  confidence=0.0..1.0,
  dimensions={five fixed quality dimensions, each 0.0..1.0},
  findings=[Finding(code="UPPER_SNAKE", severity=..., evidence=...)],
  rationale="human-readable summary",
  metadata={},   # free-form; recorded in run logs
)
```

## Rules for implementers

1. Be deterministic for a fixed configuration. Stochastic evaluators own their
   seeding and must document it in `metadata`.
2. Never raise on unusual report content - return a low-confidence result instead.
   The LLM adapter, by contrast, raises a typed `EvaluationFailure` (strict JSON
   contract and failure codes in its module docstring) rather than inventing
   decisions.
3. Never read `context.labels`. Ever.
4. Never infer the expected mutation or report class from `context.case_id`,
   `report.fixture_id`, or `report.path`: these are opaque handles, and parsing
   them for signal is benchmark gaming. Tests assert operator identity is absent
   from evaluator-visible input.
5. Built-in implementations register via `register_evaluator(instance)`. External
   BYOE modules must not register; return their object/factory result directly.

## Adding an evaluator

Create the module under `src/sloplab/evaluators/`, implement the protocol, register
it, add unit tests (including the label-independence test), and import it from
`sloplab/evaluators/__init__.py`. Then:

```bash
sloplab evaluate benchmarks/results/v1-core-example --evaluator your-name --out results/
sloplab compare results/ benchmarks/results/v1-core-example
```

## External evaluators (no source edits)

Use `--evaluator-module FILE.py:ATTR` or `MODULE:ATTR` on `benchmark` / `evaluate`.
`ATTR` is an evaluator object or zero-argument factory; it follows the same input
and output contract above. Combine it with `--evaluator rules-baseline` to compare
both in one run. External `requires_labels=True` is rejected. This executes trusted
local Python with your user's privileges, not a sandbox. See
[Bring your own evaluator](bring-your-own-evaluator.md) for setup, failure provenance
and the offline HTML report.

## Reference implementations

- `oracle` - echoes labels; validates scoring plumbing end to end.
- `rules-baseline` - deterministic heuristics over section structure and language;
  documented limitations in its docstring and docs/methodology.md.
