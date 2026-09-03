# Release Notes - v0.3.0

The first SlopLab release to change the safety policy. Read
[docs/safety.md](safety.md) before using it.

Three additions, all opt-in: a narrow carve-out admitting prompt-injection
mutation operators, a `defense` prompt-boundary arm for the LLM evaluator, and
cross-run decision history. **No default-path behavior changed** - the committed
v1-core reference results reproduce byte for byte, and the untouched control
prompt is pinned by a literal golden.

## The safety policy changed

`docs/safety.md` rule 6 rejected "triage bypass techniques" and the threat model
disclaimed evasion optimization. Prompt injection is exactly that: it does not
degrade report quality, it targets the evaluator. Measuring whether an LLM triage
evaluator can be hijacked by report content - and whether a delimiting defense
stops it - cannot be done without such cases in the corpus.

Exception 7 is now recorded in safety.md, threat-model.md and D-0015. It is
written by mechanism rather than by implementation, and admits two classes on
separate terms: **7a instruction override** (content directing the reader to
disregard its own task) and **7b fabricated authority** (content asserting a
verdict as though it came from outside the report). A payload that is neither is
not covered, and a new mechanism needs a new clause before any operator
implements it.

Both classes require the text to be a generic, widely published shape, never
tuned against an observed system, naming no real triage system, product, vendor
or program, and always with a defense measured against it. 7b adds that the
asserted authority must be unattributed and must not imitate any real system's
output format. Every operator names its admitting clause in code, and a test
asserts that clause exists in the policy - so an operator cannot outlive the rule
that permits it.

The first version of this exception described instruction override alone and
admitted a fabricated-authority operator under it anyway. That is recorded in
D-0015 rather than quietly corrected: a policy that fails its first test is
information about the policy.

Everything else in rules 5 and 6 stands. The exception does not license bypass
techniques aimed at systems outside this benchmark.

## Prompt-boundary arm (`defense: none | delimited`)

`defense=none` is the control and the default: the prompt SlopLab has always
measured, byte-identical, pinned by a hand-written golden and its sha256.
`defense=delimited` fences the report as untrusted content, neutralizing
boundary-looking markers first - a fence a report can close from the inside is
not a defense.

Detection runs on a normalized view of the text (format characters dropped, NFKD
with nonspacing marks removed, Cyrillic/Greek confusables and Unicode dash
lookalikes folded), and the verifier uses the same pattern as the neutralizer.

Selectable per dispatch: `--defense` and `--case-kind` on `scripts/llm_bench.py`
and on the `llm-benchmark` workflow.

## Injection operators

`instruction_override`, `forged_boundary`, `fabricated_triage_note` - opt-in
through `benchmarks/suites/injection-v1.yaml`, deliberately absent from v1-core
so no published number moves. D-0012's twelve quality operators stay frozen; the
registry test now asserts the family split rather than a bare count.

Injected cases keep their parent's expected decision and penalise no dimension:
injection attacks the evaluator, not the report. That makes `rules-baseline` a
negative control, asserted corpus-wide.

## Cross-run decision history (opt-in, `--history`)

`repeat_stability` only sees flips within one run's repeats. History records one
decision per case per run - a stochastic evaluator's repeats collapsing to their
majority - so `stable_cases(3)` means three runs agreed. Entries record model and
corpus version and `stable_cases` filters on both. Lives under `experiments/`
because every entry is timestamped and reproducibility.md guarantees no wall-clock
input reaches mutation, evaluation or scoring.

## Reporting

`injection_success_by_arm` reports the **lift** over the un-injected parents, not
the raw rate: an evaluator that would have answered the demanded decision anyway
scores as obeying, which for a deterministic evaluator reads as susceptibility it
cannot have. The benchmark Markdown report now prints the error taxonomy beside
decision accuracy, so a safe-direction deferral is distinguishable from a
dangerous error.

## Not in this release

- **No measurement.** The live pilot has never been dispatched, so
  `defense=delimited` has not seen a single real model response. Everything
  verified here is against an in-process fake transport.
- The pilot's case selection still takes the first N cases in id order, so a
  dispatch can spend its budget on cases where injection success is undefined;
  the runner warns when that happens rather than reordering the metered protocol.
- Arm B's fence neutralization rewrites any all-dash line, so it would also
  rewrite Markdown setext headings. No committed fixture uses them and a test
  pins that, but the confound is latent rather than absent.
- Carrying a history file across pilot dispatches is a manual operator step; the
  ephemeral CI runner does not accumulate it on its own.

## Review history

Six review rounds plus a security review (no vulnerabilities). Every round found
real defects: two were introduced by the previous round's fixes, two only became
visible once the feature was wired up enough to run, and one was a defense being
measured against a test set drawn from the defense's own assumptions. See
[docs/review-brief-injection-arm.md](review-brief-injection-arm.md) for what a
further reviewer should look at, including the per-case nonce delimiter that
would dissolve the forged-boundary class entirely and is deliberately deferred.
