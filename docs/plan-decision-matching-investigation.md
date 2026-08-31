# Plan: Investigation - is SlopLab's decision matching too strict?

Status: approved (revision 2). Investigation only - no code changes, no commits.
Supersedes: the initial draft that addressed the question to the oracle, imported
a findings-matching analogy, and asked whether dimensions use a tolerance band.

## The question, restated

Does SlopLab score an evaluator as wrong when it made a defensible call that
merely differs from the ground-truth label? And if so, should it stop?

## What changed from the first draft, and why

| # | Draft said | Revision says | Reason |
|---|---|---|---|
| 1 | "SlopLab's **oracle** compares an evaluator's decision to the ground-truth label" | The oracle compares nothing; the comparison lives in `models/run.py` and `scoring/metrics.py` | `oracle.py` is an *evaluator* that echoes labels back (oracle.py:27-33). Neither module that performs the comparison appears in the draft's read list, so following it literally would produce a wrong answer to question 1. |
| 2 | Frame the question with vulnhunter's finding-matching ("shallower-but-correct still counts when root cause and remedy match") | Drop the analogy; ask the decision question directly | That framing is about matching free-text findings in a detection harness. SlopLab never scores findings at all - `EvaluationResult.findings` is recorded into `CaseRecord.findings` and no metric reads it. "Exact-ID matching punishes a correct evaluator" is inapplicable by construction. The decision question is real and stands on its own. |
| 3 | "Are the five dimensions scored with a tolerance band, or exactly?" | "Is per-dimension error the right aggregation?" | False dichotomy: dimensions are scored by mean absolute error (metrics.py:183-193), a continuous measure with no threshold to be exact or tolerant about. The posed question has no answer. |
| 4 | (absent) | Add: how many places implement the comparison? | `CaseRecord.correct` is computed and stored at run.py:95; `metrics.decision_correct` recomputes it at metrics.py:53. `comparison.py` reads the stored field, `metrics.py` recomputes. Any tolerance change must touch both or they diverge silently - question 5 cannot be answered correctly without this. |
| 5 | "If tolerance is missing, what is the smallest change that would add it" | First ask whether the benchmark already compensates elsewhere | The premise that tolerance is simply absent is untested. The error taxonomy already names six distinct error types, and the primary risk metric deliberately ignores `needs_manual_review`. The real question is what, if anything, is still missing after that. |
| 6 | Cost in discriminating power described in prose | Cost must be **measured** on the committed corpus | This benchmark's stated purpose is discriminating between evaluators. A claim about discriminating power should be a number, not an opinion - and the number decides the answer. |

## Method

1. Read the actual comparison sites, not only the drafted list:
   `models/run.py`, `scoring/metrics.py`, `scoring/comparison.py`,
   `evaluators/oracle.py`, `scoring/harness.py`, `models/enums.py`,
   `docs/evaluator-contract.md`, `docs/methodology.md`.
2. Answer the five questions with `file:line` citations.
3. For question 4, find a real case in the committed corpus, not a hypothetical.
4. For question 5, re-score the committed v1-core run under three matching rules
   and report the gap between the competitive baseline (`rules-baseline`) and the
   negative control (`evidence-graph-baseline`), which exists precisely to be
   distinguishable. Also score degenerate always-one-answer evaluators under each
   rule: a matching rule that rewards a constant answer is disqualifying.

## Questions to answer

1. Exactly how is `decision` compared to `expected_decision`, and in how many
   places?
2. Is `needs_manual_review` a third state, or collapsed into accept/reject - and
   is the answer the same for every metric?
3. How are the five quality dimensions aggregated, and is that aggregation the
   right one?
4. Is there a real corpus case where a defensible-but-different call scores as
   wrong? Name it.
5. Does the benchmark already compensate for defensible near-misses somewhere
   other than the match itself? If a change is still warranted, what is the
   smallest one - and what does it cost, in measured discriminating power?

## Output

A written report saved to `docs/decision-matching-audit.md`. If the matching is
already appropriate, say so plainly and close the question rather than inventing
a change to justify the investigation.

No code changes. No commits.
