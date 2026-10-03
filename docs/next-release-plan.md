# Next release acceptance plan

The user's October continuation authorizes implementation of remaining work.
The current tagged release stays v0.2.2; this plan records candidates for the next
release without changing the historical V1/V0.2 acceptance contract.

## Current implementation wave: installed evaluator plugins

- [x] List built-ins and installed `sloplab.evaluators` metadata without importing
  plugin targets; include distribution version and conflicts in deterministic JSON.
- [x] Explicit, repeatable plugin selection in benchmark/evaluate; combine with
  built-ins or direct-module evaluators; keep default runs free of plugin discovery.
- [x] Reject ambiguous/unknown/duplicate names and preserve existing registry,
  import-cache, label-access, identity and operational-failure gates.
- [x] Provide an installable example and package-author/usage documentation.
- [x] Verify wheel installation and CLI usage from outside the checkout; record
  local verification and delivery in progress.md.

The merge gate is successful CI on Python 3.11/3.12/3.13. The implementation PR's
check results record that gate; the release itself remains a separate milestone.

## Previously delivered functionality

Offline HTML reports already contain inline numeric SVG charts and work without
remote resources. Offline repeat/base-seed variance analysis is also delivered.
Synthetic contribution transactions and CI's rule-based safety validation also
exist; target validity remains a human review task.
These are existing implementations; their presence does not claim a new live
multi-seed experiment or complete independent validation.

## Remaining scientific dependencies

Dots coverage is incomplete because recorded requests returned HTTP 400. Bounded
registered retries may add observations; results from another model stay separate.
Two card claim-status disagreements and two action-changing human pair annotations
remain recorded without automatic relabeling. New independently authored private
inputs and prospective repeat/mutation studies require their own frozen protocol.

Other product candidates remain in [backlog](backlog.md). Real-world corpus
ingestion needs source licenses/permissions and sanitized source material; the
existing synthetic-only scope does not automatically authorize live target work.
