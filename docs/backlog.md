# SlopLab Backlog

Ideas that are explicitly OUT of V1 scope. An item may be promoted only by mapping it
to a future release's acceptance criteria.

- Real-world sanitized corpus: ingest publicly disclosed reports with explicit
  licenses, permission tracking, PII/target scrubbing pipeline.
- Live GitHub issue ingestion mode (read-only) with provenance capture.
- Additional evaluator baselines: heuristic NLP scorer, small local model adapter.
- Prospective repeat study with registered provider decoding seeds. The offline
  multi-run/base-seed [variance CLI](variance-analysis.md) is delivered; existing
  run base seeds alone do not establish provider decoding seed control.
- HTML report format with embedded charts.
- Plugin discovery of third-party evaluators via entry points.
- Localization of fixture prose beyond English.
- Corpus contribution workflow with automated safety review gate.
- Live LLM follow-up: all 60 canonical cases were dispatched, but
  `canonical-sqlx-002` returned HTTP 400 on all six attempts, leaving 59 cases
  with at least three valid responses. `canonical-saml-019` showed a decision
  flip across repeated runs. See
  [the coverage report](llm-pilot-canonical-coverage-2026-09-28.md). Resolve
  the provider failure before claiming complete canonical coverage; mutation
  cases beyond the realized-edit annotation panel remain future work.
  The separate nine-card private panel is recorded in the October follow-up.
  [The coverage recovery](coverage-recovery-2026-10-03.md) completes all 27 card
  votes and 417/423 edit votes. A separate NVIDIA sqlx-002 study has three valid
  responses; Dots coverage remains 59/60 and its six edit votes remain blocked
  by HTTP 400.
- Reopened methodological issues #45, #46, #47, #50 and #52: deterministic
  controls and operator/pair audits are recorded in
  [the follow-up](methodology-followup-2026-09-28.md). Owner judgments and a
  three-family panel for nine private
  inputs are now recorded in the [October follow-up](model-panel-followup-2026-10-03.md),
  alongside blinded realized-edit annotations. The user's friend returned the
  second-human packet (nine cards, 18 balanced edit pairs); structure and source
  integrity pass, while one p10 rationale revision is pending. See the
  [independent review](independent-human-review-2026-10-03.md). Additional human
  raters, adjudication of disagreements and newly authored private inputs remain
  future validation work.
