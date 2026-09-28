# SlopLab Backlog

Ideas that are explicitly OUT of V1 scope. An item may be promoted only by mapping it
to a future release's acceptance criteria.

- Real-world sanitized corpus: ingest publicly disclosed reports with explicit
  licenses, permission tracking, PII/target scrubbing pipeline.
- Live GitHub issue ingestion mode (read-only) with provenance capture.
- Additional evaluator baselines: heuristic NLP scorer, small local model adapter.
- Multi-seed variance analysis CLI with confidence intervals for stochastic evaluators.
- HTML report format with embedded charts.
- Plugin discovery of third-party evaluators via entry points.
- Localization of fixture prose beyond English.
- Corpus contribution workflow with automated safety review gate.
- Broader live LLM study: a three-case pilot ran on 2026-09-28 (see
  docs/llm-pilot-2026-09-28.md). The strict-JSON adapter rejected 3 of 18 model
  responses, so complete repeat-stability coverage was not reached. Before a
  larger run, settle schema-constrained output, runtime limits, and recording the
  resolved model identifier in the bundle manifest.
