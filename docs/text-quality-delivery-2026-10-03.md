# Text quality control delivery — 3 October 2026

The heuristic text-scoring portion of the additional-evaluator backlog is
implemented as `text-quality-baseline` version 0.1.0. It is selected explicitly
alongside the original built-ins, BYOE modules or installed plugins. The
[feature guide](text-quality-baseline.md) defines every proxy and its limitations.
A trained local-model adapter remains separate future work.

## Implementation and contract

The evaluator measures section content, distinct ordered steps and first-line
step detail, and reports lexical overlap/repeated-line diagnostics. Heading
tokens and fence language tags do not fill empty sections. Code examples cannot
be counted as ordered reproduction steps; duplicated steps cannot inflate the
step score. Nested section bodies and Unicode normalization are supported.

It receives no labels and never derives signal from case names, paths or fixture
identifiers. It always returns `needs_manual_review` and a fixed uncalibrated
confidence of 0.5. The three semantic dimensions stay at 0.5 and are explicitly
marked unassessed. Existing metric formulas still score those numeric values.
There is no new dependency, model download, API request or network requirement.

## Descriptive public-suite snapshot

The full V1 suite materializes 60 canonical and 237 changed derived cases
(297 total); 43 planned no-op mutations stay excluded. The run used base seed
20260825 and source commit `a44788087f6faac46ceabace1fb0e026be9ae48c` after
implementation was committed. The proxy definitions were documented before the
full-suite run. Fence/indentation corrections came from parser-contract checks,
not fitting thresholds to target outcomes.

The [snapshot](../experiments/results/deterministic/text-quality-control-2026-10-03/)
contains the selected evaluator's 297 `records.jsonl` rows, its metrics,
path-independent report/target identities and provenance with source/artifact
SHA-256 hashes. The source benchmark also ran `rules-baseline`; only the new
control's rows are exported here. This is a descriptive export, not a complete
integrity-marked study bundle or a fresh independently validated corpus.

| Observation | Result |
|---|---:|
| Returned decisions | 297 manual review; 0 accept; 0 reject |
| Full-suite target agreement | 158/297 = 53.20% |
| Canonical-only target agreement | 16/60 = 26.67% |
| Canonical target counts | 18 accept; 16 review; 26 reject |
| False reassurance / over-rejection counts | 0 / 0 |
| Auxiliary robustness score | 0.791 |

The full suite has 158 authored review targets, so full-suite agreement is exactly
their share. This control cannot distinguish a valid claim from an invalid one.
Zero false reassurance or rejection counts result from never accepting or
rejecting. The 0.791 auxiliary score repeats the fixed-action metric weakness
already described in the methodology follow-up; it does not demonstrate useful
claim discrimination, calibrated confidence or improved evaluator accuracy.

## Reproduction

```bash
uv run sloplab benchmark benchmarks/suites/v1-core.yaml \
    --evaluator rules-baseline --evaluator text-quality-baseline \
    --out /tmp/sloplab-text-quality
uv run sloplab report /tmp/sloplab-text-quality/run.jsonl \
    --format html --out /tmp/sloplab-text-quality/report.html
uv run pytest tests/regression/test_text_quality_snapshot.py
```

The regression rematerializes the full suite and reruns the actual evaluator. It
compares all 297 exported rows byte for byte, checks input identities, recomputes
metrics and validates source/artifact hashes. Run headers contain timestamps and
are intentionally kept outside the deterministic exported row bytes.

## Verification

- Ruff lint and format checks, strict mypy and **1264 tests** passed.
- All 60 canonical fixtures validate with zero errors or warnings.
- Benchmark/evaluate/HTML and deterministic-study integration are covered.
- The original deterministic study's decision/correct/finding-code lock passed.
- An offline wheel was installed into a fresh virtual environment. Discovery and
  a full benchmark ran outside the repository; its 297 evaluator rows were byte
  identical to the snapshot. The temporary environment was removed.
- The dependency lock, previous study results and original targets are preserved.

The PR merge gate remains green CI on Python 3.11, 3.12 and 3.13. Existing Dots
coverage remains 420/423 edit votes and 59/60 canonical cases. This offline wave
makes zero live model calls and supplies no new observations for that provider
failure.
