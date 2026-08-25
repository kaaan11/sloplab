# Release Notes - v0.1.1

Patch release. **This release fixes the CI/lint-gate failure present in v0.1.0 and
changes no runtime behavior** - the only code deltas are removals of unused
variables, loop-variable binding in a presentation operator's substitution callback,
and an explicit Ruff per-file policy documenting intentional registration imports.

## What changed

- Fixed lint violations (F841 unused variables, B007/B023 loop-binding issues) that
  made the final v0.1.0 commit fail its own quality gates; the failures never
  affected benchmark outputs, fixtures, or evaluator decisions.
- Added an explicit `[tool.ruff.lint.per-file-ignores]` policy for the two registry
  modules whose side-effect imports intentionally follow definitions (avoids
  circular imports).
- Process fix: quality-gate verification now checks command exit codes rather than
  truncated output tails.

## Verification

Green CI on exactly this commit (`0bfb7d2`), all three matrix jobs:

- CI run: https://github.com/kaaan11/sloplab/actions/runs/32883509834
- 127 tests passing offline; `ruff check` / `ruff format --check` / `mypy --strict`
  clean.

## Tag relationship to v0.1.0

- `v0.1.1` points at `0bfb7d2`; the `v0.1.0` tag remains untouched at `f3509df`.
- If you pinned `v0.1.0`, upgrading is optional from a runtime perspective but
  recommended so that installation aligns with a green CI state.
