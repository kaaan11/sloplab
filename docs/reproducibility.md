# Reproducibility Guide

SlopLab's deterministic pipeline produces identical decisions across runs and
machines given identical inputs: the `decision`, `correct`, and finding-code
fields are identical on all supported Python versions (3.11/3.12/3.13; pinned
by `tests/regression/test_committed_results_match_evaluators.py`, added by
#61). Record files are byte-identical for a fixed Python version; the
committed study-v02 records additionally regenerate byte-identically on
3.11/3.12/3.13 (verified by full regen + `cmp`; issue #53: builtin `sum()`
changed float summation in 3.12 and flipped `overall=` at the 0.795 boundary
— fixed by averaging dimensions with `math.fsum`).

## What makes it reproducible

- **Seeding:** every mutation seed is derived as
  `sha256(base_seed | parent_id | operator_name | variant_index)[:8 bytes]`.
  No wall-clock, filesystem-order, locale, or hash-randomization input participates
  anywhere in mutation, evaluation, or scoring.
- **Fixed iteration order:** fixture discovery sorts by id; suite index lines are
  sorted; metric aggregation iterates sorted keys.
- **Run provenance:** every `run.jsonl` begins with a metadata record containing
  sloplab version, Python version, git commit (when available), suite config hash,
  base seed, evaluator names/versions, and start timestamp.

## Reproducing the committed example

```bash
uv sync --group dev
uv run sloplab benchmark benchmarks/suites/v1-core.yaml \
    --evaluator oracle \
    --evaluator rules-baseline \
    --out /tmp/v1-core-repro
diff <(tail -n +2 /tmp/v1-core-repro/run.jsonl) \
     <(tail -n +2 benchmarks/results/v1-core-example/run.jsonl) && echo IDENTICAL
```

(The first line of `run.jsonl` embeds a timestamp and is excluded.)

## Materialization determinism

Running `sloplab materialize` twice yields byte-identical trees (covered by an
integration test). Changing any of `base_seed`, the corpus manifests, or operator
implementations changes outputs - that is intended and visible via the suite hash.
The `suite-index.jsonl` header records the corpus root relative to the suite
directory (#60), so the same suite produces byte-identical bytes on any machine;
evaluation re-locates the corpus from the index's own ancestor chain first and
falls back to the current directory as a last resort (legacy relative-to-cwd
bundles keep evaluating). Bundles written before #60 carry an absolute
`corpus_root` in the header and keep evaluating unchanged. All provenance
locations in committed bundles are portable: `execution-recipe.json`
`locations` and the `run.jsonl` header's `suite_config` record paths
cwd-relative (or bundle-relative, e.g. `suite-index.jsonl`) and never contain
machine-specific absolute paths.

## Environment

- Python >= 3.11 (validated on CPython 3.14).
- Dependencies are locked by `uv.lock`; CI installs with `uv sync --group dev`.
- No network access occurs anywhere in the deterministic pipeline.

## LLM evaluators

The optional LLM adapter is excluded from all of the above. If you enable it,
record model id, decoding parameters, retry policy, and date; results are reported
separately from deterministic baselines and require multiple repetitions per
methodology.md.

## Experiment studies (v0.2)

Deterministic evaluator studies add one more reproducibility layer:

```bash
uv run sloplab study experiments/configs/deterministic-study-v0.2.yaml \
    --out experiments/results/deterministic/study-v02
```

For a fixed commit + corpus + seed + Python version, `records.jsonl` inside
the study output is byte-identical across runs; the committed study-v02
records additionally regenerate byte-identically on CPython 3.11, 3.12, and
3.13 (issue #53). `manifest.json` additionally records the commit SHA,
suite hash, evaluator config hashes, and wall-clock times (excluded from identity
comparison by design). Bootstrap confidence intervals are seeded from the study's
base seed and therefore reproduce exactly.
