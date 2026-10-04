# Release Notes - v0.3.0

SlopLab v0.3.0 packages the evaluator integrations, contribution tools,
reporting improvements and integrated corrections delivered since v0.2.2.
Python 3.11, 3.12 and 3.13 remain supported. Default benchmarks and tests run
offline; live model evaluation requires explicit configuration.

## New functionality

- Trusted local Python evaluators can run alongside built-ins through
  [BYOE](bring-your-own-evaluator.md). Installed packages can advertise named
  evaluators through `sloplab.evaluators`; `sloplab evaluators` lists metadata
  without importing plugin targets. See the [plugin guide](evaluator-plugins.md).
- `text-quality-baseline` measures lexical section content and distinct ordered
  step detail without dependencies or model calls. It always returns manual
  review, uses uncalibrated confidence and leaves semantic dimensions unassessed.
  Its [297-case descriptive snapshot](text-quality-delivery-2026-10-03.md) is
  reproducible; its scores do not demonstrate claim discrimination.
- Offline HTML reports include inline SVG charts. JSONL, CSV and Markdown outputs
  remain available. [Repeat/base-seed variance analysis](variance-analysis.md)
  operates on recorded runs; it does not establish provider decoding seed control.
- Synthetic corpus contributions use the validated `add-report` transaction,
  with an optional keyboard-driven [Report Builder](report-builder.md) installed
  through the `ui` extra. CI validates the synthetic content policy.
- Typed JEV evaluation carries versioned criteria and treats option order as an
  explicit stimulus. The strict-JSON LLM adapter and bounded pilot tooling retain
  operational failures and request provenance.

## Integrated corrections

The release includes path containment, URL/CVE policy parsing, corpus identity
validation, Markdown fence handling, LLM severity/JSON handling, conditional
boundary classification and mutation matching corrections. Scoring now uses
canonical accuracy in the robustness component; repeat-unit and cluster analysis,
portable provenance, output replacement and committed-result checks were also
corrected. The [integration record](integration-completion-2026-10-03.md) links
the correction waves and review evidence.

Historical result bundles retain their recorded versions and provenance. The
version bump does not regenerate old observations or change corpus targets.
Recomputed runs may differ from v0.2.2 because of the documented corrections;
consult the [reproducibility guide](reproducibility.md) for comparison guarantees.

## Descriptive research follow-ups and remaining work

The release includes registered model-panel observations and a second human's
review, including the verified p10 rationale correction. Public exports contain
aggregate human results; private forms and identities stay outside the package.
These selected synthetic samples do not establish general triage accuracy or
independent validation of the full corpus.

Dots coverage remains **59/60 canonical cases** and **420/423 realized-edit votes**.
Persistent HTTP 400 responses leave one canonical case and three edit votes
unresolved. A separate NVIDIA observation does not fill Dots coverage. Human
claim-status disagreements and action-changing pair annotations remain recorded
without automatic relabeling. See the
[coverage follow-up](plugin-and-coverage-followup-2026-10-03.md),
[independent human review](independent-human-review-2026-10-03.md) and
[backlog](backlog.md).

## Release validation

The release gate is Ruff lint/format, strict mypy, the full offline pytest suite,
validation of all 60 canonical fixtures, a clean wheel installation with a full
297-case benchmark outside the checkout, and green CI on Python 3.11/3.12/3.13.
Release preparation makes no live model calls. Build artifacts and SHA-256
checksums accompany the GitHub release.
