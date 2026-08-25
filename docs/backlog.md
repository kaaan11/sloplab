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
- Live LLM pilot (deferred from V0.2): add `LLM_API_KEY` secret to the `llm-bench`
  GitHub Environment and dispatch the manual workflow; protocol, budgets, prompt,
  and stability metrics are ready in experiments/configs/llm-pilot-v0.2.yaml and
  docs/llm-pilot-runbook.md.
