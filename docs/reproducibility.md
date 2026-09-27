# Reproducibility Guide

SlopLab's deterministic pipeline produces byte-identical outputs across runs and
machines given identical inputs.

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

For a fixed commit + corpus + seed, `records.jsonl` inside the study output is
byte-identical across runs; `manifest.json` additionally records the commit SHA,
suite hash, evaluator config hashes, and wall-clock times (excluded from identity
comparison by design). Bootstrap confidence intervals are seeded from the study's
base seed and therefore reproduce exactly. The PRIMARY accuracy interval is the
logical-report cluster bootstrap (issue #48): cluster keys resolve
`parent_id` (derived) / `case_id` (canonical) through the canonical manifests'
`pair_id` when present, cluster order is first appearance in `records.jsonl`,
and `random.Random(seed)` draws `len(clusters)` clusters per resample with
`rng.choice` — so the interval depends on the record order as well as the seed,
and both are frozen by the committed artifacts. The paired difference uses the
same draws for both evaluators. The cluster block also carries
`pair_merge` = `applied` | `skipped`: `skipped` means pair ids could not be
resolved (fallback to per-fixture clusters) and the `sloplab study` command
warns on stderr.
