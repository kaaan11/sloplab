# Audit: is SlopLab's decision matching too strict?

Investigation only; no code was changed. Method and scope in
`docs/plan-decision-matching-investigation.md`.

**Verdict: no. The matching is exact, deliberately, and it should stay exact.**
The benchmark already gives defensible near-misses the credit they deserve - in
the error taxonomy and in the primary risk metric - rather than in the match.
Moving that credit into the match would destroy the benchmark's ability to tell
evaluators apart. Measurements below.

## 1. How the comparison is performed, and where

Exact enum equality, in **two** places:

- `src/sloplab/models/run.py:95` - `CaseRecord.from_result` computes and stores
  `correct=(expected_decision is not None and result.decision == expected_decision)`.
- `src/sloplab/scoring/metrics.py:53-54` - `decision_correct(record)` recomputes
  the same predicate.

`Decision` is a `StrEnum` with three members (`src/sloplab/models/enums.py:23-28`),
so `==` is exact string equality. There is no distance, ordering, or partial
credit anywhere.

The two implementations have different consumers:
`scoring/comparison.py` reads the **stored** field (lines 52-53, 136, 174, 180),
while `scoring/metrics.py` **recomputes** it (lines 92, 165, 225, 246, 248). They
agree today because both are exact equality. They are nonetheless two sources of
truth for one definition, and any change to matching that touched only one would
silently split accuracy from paired win/loss and the bootstrap CI.

**The oracle compares nothing.** `evaluators/oracle.py:27-33` reads
`context.labels["expected_decision"]` and echoes it as its own decision; it is an
evaluator used to validate scoring plumbing, not a judge. Labels reach it from
`scoring/harness.py:139-145`, which builds `EvaluationContext.labels` from the
case manifest. The oracle scoring 1.000 (297/297) is a plumbing check, not a
statement about matching.

## 2. Is `needs_manual_review` a third state?

Yes - genuinely third almost everywhere, flattened in exactly one metric.

- **Ground truth**: `CANONICAL_EXPECTED_DECISION` maps `review ->
  needs_manual_review` (`models/enums.py:73-77`), a first-class label. It is the
  largest class in v1-core: 158 of 297 expected decisions, against 87 `reject`
  and 52 `accept`.
- **Decision accuracy**: third state. `metrics.py:53` compares all three members
  identically.
- **False reassurance** (`metrics.py:61-67`): the *eligible set* is
  "expected != accept", which pools `reject` and `needs_manual_review` - but the
  *outcome* counted is only `decision == accept`. So answering
  `needs_manual_review` never counts as false reassurance. This is the design
  already treating deferral as not-dangerous.
- **Over-rejection** (`metrics.py:70-76`): eligible set is expected `accept`,
  outcome counted is only `reject`. Deferring a valid report is not counted as
  over-rejection either.
- **Error taxonomy** (`comparison.py:106-114`): all six ordered pairs are named
  separately - `deferred_invalid`, `premature_deferral`, `premature_accept`, and
  `over_strict_reject` are distinct from `false_reassurance` and
  `over_rejection`.

The only place the third state is flattened is **decision accuracy**, where
answering `needs_manual_review` to a `reject` case costs exactly as much as
answering `accept`. That is the whole of the complaint, and section 5 shows why
it is the right trade.

## 3. How the five dimensions are scored

Neither exactly nor with a tolerance band: by **mean absolute error**
(`metrics.py:183-193`). For each case carrying `expected_dimensions`, per
dimension, `abs(actual - expected)` is averaged. There is no threshold, so there
is nothing to loosen: a score of 0.62 against an expected 0.66 already costs 0.04
rather than being "wrong". Dimensional scoring is continuous and was never strict.

The question worth asking instead is whether MAE is the right aggregation - it
weights every dimension and every case equally and reports no spread. That is a
reporting-granularity question, not a strictness one, and is out of scope here.

## 4. A real case where a defensible call scores as wrong

Yes, and it is not hypothetical.

**`canonical-pair2a-dirlist`** (`corpus/canonical/pair2a-dirlist/`) - a
well-formed, fully reproducible report that a public `/assets/` directory shows a
file index. Ground truth is `report_class: invalid`, expected decision `reject`,
with the manifest rationale: *"Indexing of an entirely public directory crosses no
boundary; every listed object is individually downloadable by design. Reject."*

`rules-baseline` answers `needs_manual_review` at confidence 0.45, and is scored
wrong.

The call is defensible. Every structural signal the evaluator can read says the
report is sound - its own ground-truth dimensions are `reproducibility: 0.86`,
`evidence_completeness: 0.66`. What makes the report invalid is a *semantic*
judgment about security boundaries that a lexical evaluator cannot make. Deferring
to a human is the honest answer for a system that cannot decide, and it errs in
the safe direction.

It is not isolated: on the committed v1-core run, `rules-baseline` produces 8
`deferred_invalid` and 3 `premature_deferral` cases out of 56 total errors
(the rest: 22 `over_strict_reject`, 22 `false_reassurance`, 1 `premature_accept`).

So the answer to question 4 is **yes** - roughly 11 of 297 cases, about 3.7%.

## 5. Should tolerance be added? No. Here is the cost.

The benchmark already compensates: the taxonomy names deferral separately, and
the primary risk metric excludes it by construction (section 2). The credit
exists; it simply is not spent on the accuracy number.

To test what spending it there would cost, the committed v1-core suite was
re-scored under three matching rules:

- **exact** - current behavior.
- **+defer** - full credit when the evaluator answered `needs_manual_review`
  where `accept` or `reject` was expected (credit only in the safe direction).
- **+any-adjacent** - additionally full credit for any confusion involving
  `needs_manual_review` in either direction.

| matching rule | rules-baseline | evidence-graph-baseline | gap |
|---|---|---|---|
| exact | 241/297 = **0.811** | 161/297 = **0.542** | **+0.269** |
| +defer | 252/297 = 0.849 | 181/297 = 0.609 | +0.239 |
| +any-adjacent | 275/297 = 0.926 | 275/297 = 0.926 | **+0.000** |

`evidence-graph-baseline` is the repository's **negative control**: per the README
it is "intentionally blind to content-quality mutations - it exists to prove the
benchmark detects such blindness". Under any-adjacent matching the competitive
baseline and the deliberately blind control produce **the identical score, 275/297**.
The benchmark stops measuring anything.

The narrower "+defer" rule is not safe either. Scoring degenerate evaluators that
return one constant answer to every case:

| constant answer | exact | +defer | +any-adjacent |
|---|---|---|---|
| always `needs_manual_review` | 0.532 | **1.000** | **1.000** |
| always `accept` | 0.175 | 0.175 | 0.707 |
| always `reject` | 0.293 | 0.293 | 0.825 |

An evaluator that answers "ask a human" to all 297 cases - reading nothing,
deciding nothing - scores a **perfect 1.000** under safety-preserving defer
credit. A matching rule that a constant answer can max out is not a matching rule.
This follows directly from the corpus composition: `needs_manual_review` is 53%
of expected decisions, so crediting it as a near-match for the other two makes it
universally correct.

### If something must change, the smallest defensible change

Not to the match. Report the number that already exists:
`error_taxonomy` (`comparison.py:131-143`) computes `deferred_invalid` and
`premature_deferral` on every run, and the study path already writes them to
`analysis.json`. Surfacing "of N errors, M were safe-direction deferrals" beside
decision accuracy in the Markdown report gives a reader the whole picture at zero
cost to discriminating power, because the accuracy number itself does not move.

That is a reporting change, not a scoring change, and it is optional. The
substantive answer to the investigation is that the matching is already
appropriate.

## Note on the framing that prompted this

The reference framing - a shallower-but-correct classification still counting as a
detection when root cause and remedy match - is about matching **findings** in a
detection harness. SlopLab never scores findings: `EvaluationResult.findings`
flows into `CaseRecord.findings` (`models/run.py:99`) and no metric in
`scoring/` reads it. There is no exact-ID matching here to be punished by. The
decision label is a three-way categorical judgment, and for a three-way judgment
on a corpus where one class is the majority, exactness is what makes the
measurement mean anything.

## Reproducing the tables

```bash
uv run sloplab benchmark benchmarks/suites/v1-core.yaml \
    --evaluator oracle --evaluator rules-baseline \
    --evaluator evidence-graph-baseline --out /tmp/tol
```

then re-score `run.jsonl` under the three rules. The exact-match column
reproduces the 0.811 quoted in README.md, confirming the re-scoring agrees with
the shipped metric path.
