# Contributing to SlopLab

Thanks for your interest! SlopLab measures how robust vulnerability-report triage
evaluators are against degraded report content.

## Quick start (under 10 minutes)

```bash
git clone <repo-url> && cd sloplab
uv sync --group dev                      # install with dev tooling
uv run pytest                            # full test suite, offline
uv run sloplab validate corpus/          # validate the committed corpus
uv run sloplab benchmark benchmarks/suites/v1-core.yaml \
    --evaluator rules-baseline --out /tmp/my-benchmark
uv run sloplab report /tmp/my-benchmark/run.jsonl
```

No API keys, no network access. See docs/reproducibility.md for byte-level
reproduction guarantees.

## Ways to contribute

1. **New canonical fixtures** - synthetic reports in any of the four classes.
   Requirements: manifest + report pair passing `sloplab validate`, ground truth
   rationale, dataset-card entry update. Safety rules in docs/safety.md apply.
2. **New mutation operators** - see docs/adding-mutations.md for the full guide.
3. **New evaluators** - see docs/evaluator-contract.md.
4. **Metrics/reporting improvements** - definitions live in docs/methodology.md;
   changes to metric semantics must update that document and tests together.

## Ground rules

- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`); small, revertible.
- Every feature lands with tests; `ruff check`, `ruff format --check`, `mypy`
  (strict), and `pytest` must pass.
- Deterministic pipeline only in CI: no network calls, no LLM usage.
- Safety policy (docs/safety.md) is binding; contributions enabling deceptive
  report writing against real targets are rejected.

## Project layout

```
src/sloplab/        package code (models, corpus, mutations, evaluators, scoring,
                    reporting, safety, cli)
corpus/canonical/   committed fixture source of truth
benchmarks/         suite configs and example results
tests/              unit / integration / regression / property tests
docs/               methodology, safety, threat model, contracts
```

## Decision log

Material engineering decisions are recorded in docs/decision-log.md. If you change
one of those decisions, extend the log rather than rewriting history.
