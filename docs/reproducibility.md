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
base seed and therefore reproduce exactly.

## Cross-run decision history (opt-in)

`sloplab benchmark --history PATH` and the pilot's `--history PATH` append one
decision per case per run to a JSON history file
(`src/sloplab/experiments/history.py`). Its purpose is the opposite of
byte-reproducibility: it exists to make drift *between* runs visible, where
`repeat_stability` only sees flips *within* one run's repeats.

It is therefore an explicit exception to the guarantee above, and is fenced off
so it cannot leak into anything that is guaranteed:

- Every entry carries a wall-clock `ts`, so history files are not byte-comparable
  across runs. Nothing in the deterministic pipeline reads them.
- The module lives under `experiments/` (run provenance), never under `scoring/`.
  No metric, mutation, or evaluation consumes it.
- Nothing under `src/sloplab/evaluators/` may import it - an evaluator that could
  read its own prior decision would be gaming the benchmark. A regression test
  (`tests/regression/test_history_isolation.py`) enforces the boundary.
- Enabling history changes no other output: with the flag omitted, results are
  identical byte for byte.

Entries are keyed by the true `case_id`, not by the opaque handle evaluators see.
One run contributes one entry per case, with a stochastic evaluator's repeats
reduced to their majority decision, so `stable_cases(threshold=3)` genuinely
means "three runs agreed" and not "three repeats of one run agreed".

Because a single file may hold entries from several evaluators or corpus
revisions, read stability through the filters:

```python
history.stable_cases(threshold=3, model="rules-baseline@0.2.2")
```

Known limits: the whole file is rewritten on each update and swapped in with
`os.replace`, so a reader never sees a partial file - but two concurrent runs
will lose one set of entries (last writer wins). There is no retention policy;
the file grows linearly in runs x cases.
