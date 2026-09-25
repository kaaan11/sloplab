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

## Add a canonical fixture

```bash
uv run sloplab add-report path/to/synthetic-report.md
```

The wizard detects the H1 title, collects the existing manifest fields, stages and
validates the report plus the full corpus, and asks for explicit confirmation
before publishing. The source is copied byte-for-byte, never moved or rewritten;
existing fixtures are never overwritten. Cancel or failed validation does not add
a fixture. A post-write validation failure rolls back the newly added directory.

See [the add-report guide](docs/add-report.md) for custom corpora, transaction
boundaries, and the UI-independent API shared by the CLI and TUI. After adding
committed fixtures, update the README/dataset-card counts and applicable reference
results/documentation; the wizard does not rewrite those automatically.

### Optional Report Builder TUI

```bash
uv sync --extra ui
uv run sloplab add-report path/to/synthetic-report.md --ui
```

The keyboard-first builder uses the same core transaction. See
[Report Builder](docs/report-builder.md) for installation, shortcuts, actual
validation status and committed-with-cleanup-warning handling. The normal CLI
requires no UI dependency; development installs include the UI toolkit for tests.

## Ways to contribute

1. **New canonical fixtures** - synthetic `valid`, `invalid`, or `review` reports.
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
