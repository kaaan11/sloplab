# Offline text quality baseline

`text-quality-baseline` is a deterministic, content-only lexical control. It
needs no model, fitted vocabulary, API key, optional dependency or network
connection. It helps compare sensitivity to missing text and reproduction-step
detail independently of the corpus-specific phrases used by `rules-baseline`.
It is not a trained model or a general vulnerability triage system.

```bash
uv run sloplab evaluators
uv run sloplab benchmark benchmarks/suites/v1-core.yaml \
    --evaluator rules-baseline --evaluator text-quality-baseline \
    --out /tmp/sloplab-text-quality
uv run sloplab report /tmp/sloplab-text-quality/run.jsonl \
    --format html --out /tmp/sloplab-text-quality/report.html
```

It also works with `sloplab evaluate --evaluator text-quality-baseline` and as a
registered evaluator in a deterministic `sloplab study` config. Historical
study configs continue to select their original evaluators explicitly.

## Features and scores (evaluator version 0.1.0)

Tokens use Unicode NFKC normalization and case folding. Alphanumeric words,
including numbers, count as tokens; internal apostrophes and hyphens stay within
a word. Ordered-list markers and fence delimiters/language tags are removed.
There is no stemming, learned
vocabulary or language detection. Section names follow the existing English
heading conventions. Heading words themselves do not count as body content;
child section bodies are included.

| Output | Definition |
|---|---|
| `evidence_completeness` | Mean of seven section-content scores. Affected component/versions saturate at one distinct body token; summary, preconditions, reproduction steps, observed result and expected boundary saturate at six. Each section uses `min(distinct tokens / target, 1)`. These are content proxies, not evidence verification. |
| `reproducibility` | `0.5 * min(distinct content steps / 3, 1) + 0.5 * mean step detail`. Detail is `min(distinct content tokens / 8, 1)` for each distinct nonempty step. With no content steps, both terms are zero. |
| Remaining three dimensions | Fixed `0.5`, explicitly listed in `metadata.unassessed_dimensions`. Claim consistency, impact and scope need semantic assessment this control cannot supply. |
| `decision` | Always `needs_manual_review`, including well-filled and empty reports. |
| `confidence` | Fixed `0.5`; `confidence_kind=fixed_uncalibrated_control`. This is a control value, not an estimated correctness probability. |

Steps are ordered-list first lines with at most three leading spaces;
fenced code and indented code lines do not provide steps. Continuation/code
contents can contribute to section content, but do not contribute to step-detail
scores. The content-token filter removes a fixed list of common English function
words. Repeated normalized step token sequences count only once; repeated words
cannot inflate a step's distinct-token detail or a section's content score.
The numeric targets are declared heuristics, not statistically calibrated
thresholds or thresholds optimized on benchmark outcomes. Scores are rounded to
six decimal places.

## Diagnostics

Result metadata exposes section token counts/scores, ordered/distinct steps,
mean detail and repeated prose-line counts. Prose lines with at least four
content tokens participate in repetition counting; fenced code is excluded.
Case, punctuation and list numbers do not distinguish repeated token sequences.

`summary_observed_cosine` is term-frequency cosine similarity after the English
function-word filter, or `null` if either side has no content terms. It is a
diagnostic only. Identical text may repeat an incorrect claim; disjoint words may
describe consistent evidence. The similarity never changes a decision or
semantic dimension.

Findings identify missing, empty or sparse bodies, absent detailed steps,
duplicated steps and repeated lines. `TEXT_SEMANTICS_UNASSESSED` is always present.
No finding claims fabrication, contradiction, a valid exploit or impact. Output
contains counts and fixed messages, rather than echoing source body excerpts.

## Interpretation and limits

On a three-decision benchmark, this control's decision accuracy equals the share
of authored `needs_manual_review` targets. High aggregate scores or invariance
under style changes do not establish useful claim discrimination. Every report
is routed to a person. The metric harness still scores the three neutral
dimensions numerically; `unassessed_dimensions` is descriptive metadata, not a
request to omit them from existing metrics.

Unique-word padding, synonyms and alternative formatting can change the proxies.
A filled section does not mean its evidence is complete. A short correct
procedure may score below a verbose incorrect one. English headings/function
words are a limitation; Unicode token support is not fixture localization.
There is no trained local-model adapter in this implementation.

The evaluator ignores labels, paths, fixture identifiers, operator identities
and case-name contents. It echoes only the provided case handle. There are no
content-specific truth targets or mutation-pattern detectors in this control.
