# v0.3.0 acceptance plan

The user's October continuation authorizes implementation of remaining work.
The delivered candidates below are included in v0.3.0 without changing the
historical V1/V0.2 acceptance contract. See the
[release notes](release-notes-v0.3.0.md) for the complete release scope and
remaining scientific dependencies.

## Delivered implementation: installed evaluator plugins

- [x] List built-ins and installed `sloplab.evaluators` metadata without importing
  plugin targets; include distribution version and conflicts in deterministic JSON.
- [x] Explicit, repeatable plugin selection in benchmark/evaluate; combine with
  built-ins or direct-module evaluators; keep default runs free of plugin discovery.
- [x] Reject ambiguous/unknown/duplicate names and preserve existing registry,
  import-cache, label-access, identity and operational-failure gates.
- [x] Provide an installable example and package-author/usage documentation.
- [x] Verify wheel installation and CLI usage from outside the checkout; record
  local verification and delivery in progress.md.

The implementation and release PRs passed CI on Python 3.11/3.12/3.13.
v0.3.0 was published on 4 October 2026.

## Delivered implementation: offline text quality baseline

- [x] Register `text-quality-baseline` with no added dependencies or live calls.
- [x] Measure section content and distinct ordered-step detail using documented
  lexical features; expose similarity/repetition as diagnostics only.
- [x] Keep decisions at manual review, confidence as an uncalibrated control and
  semantic dimensions explicitly unassessed; preserve labels/identity isolation.
- [x] Verify missing evidence, duplicate/empty/Unicode/fenced content and repeated
  benchmark/evaluate/study execution through the normalized contract.
- [x] Record the full public-suite descriptive control results and reproducibility.
- [x] Complete lint, format, strict mypy, full tests and offline clean-wheel
  verification from outside the checkout.

The formulas and fixed decision policy are documented before running the full
suite in [the evaluator guide](text-quality-baseline.md). Corpus outcomes do not
drive threshold selection; this is a lexical quality control, not a model
accuracy improvement claim. A trained local-model adapter remains a separate
backlog item.

The [delivery report](text-quality-delivery-2026-10-03.md) binds the 297-case
descriptive snapshot to code, input and artifact hashes. The implementation PR's
Python 3.11/3.12/3.13 checks passed before v0.3.0 publication.

## Previously delivered functionality

Offline HTML reports already contain inline numeric SVG charts and work without
remote resources. Offline repeat/base-seed variance analysis is also delivered.
Synthetic contribution transactions and CI's rule-based safety validation also
exist; target validity remains a human review task.
These are existing implementations; their presence does not claim a new live
multi-seed experiment or complete independent validation.

## Remaining scientific dependencies

The current live continuation uses Nemotron. Its separate
[60-case study](nemotron-canonical-2026-10-04.md) has 60 valid single-observation
responses and 59 authored-target matches. A separate
[first-ten repeat pilot](nemotron-repeat-2026-10-04.md) has 30/30 valid responses
and no decision flips across three repeats per selected case. Repeat coverage
for the remaining 50 cases was subsequently evaluated in the
[remaining-repeat follow-up](nemotron-full-repeats-2026-10-04.md). One original
transport failure and a separately authorized replacement block are preserved;
the defined 60-case matrix has three decision-changing cases.
The [mutation study](nemotron-mutations-2026-10-04.md) attempted all 237 variants
and 60 fresh controls with 296 valid responses and one transport failure.
The user subsequently authorized a bounded supplement; one additional call
completes the matched dataset at 451 total continuation calls. Original failures
remain intact. Mutation target agreement is 137/237, and decision-changing target
agreement is 2/96; mutation repeat stability remains future work.
Historical Dots coverage stays incomplete because recorded
requests returned HTTP 400; another model's results do not replace those outcomes.
Live Jev testing/integration is deferred under the user's current model choice.
Two card claim-status disagreements and two action-changing human pair annotations
remain recorded without automatic relabeling. New independently authored private
inputs and prospective repeat/mutation studies require their own frozen protocol.

Other product candidates remain in [backlog](backlog.md). Real-world corpus
ingestion needs source licenses/permissions and sanitized source material; the
existing synthetic-only scope does not automatically authorize live target work.
