# Offline repeat and seed analysis

`sloplab variance` analyzes verified `llm-pilot` bundles without model calls,
API keys or new observations. It accepts multiple runs and records each run's
base seed. Different model, prompt, renderer, schema, output mode, required
parameters or temperature settings produce separate conditions.

```bash
uv run sloplab variance path/to/run-a path/to/run-b \
    --corpus corpus --bootstrap-samples 2000 --confidence 0.95 --seed 0 \
    --out /tmp/variance.json
```

The command reports decision counts, observed decision flips, confidence mean,
population standard deviation and range for each case. Failed and unrun
observations remain visible. A case contributes to the aggregate flip rate and
interval only when **all supplied planned observations succeeded** and at least
two valid observations exist. A flip in a partially failed case still appears
in its individual entry.

The percentile bootstrap resamples logical report clusters: presentation pair
IDs from `--corpus`, then canonical parent IDs, then case IDs. Omitting `--corpus`
retains parent grouping but cannot merge canonical presentation pairs; the JSON
states this limitation. Fewer than two eligible clusters yields a null interval.
Copies of the same integrity bundle, changed rendered inputs for the same case,
duplicate repeat slots inside a bundle, mismatched outcomes and damaged hashes
are rejected. Separate runs remain separate observations even if repeat indexes
overlap. This command never fills missing observations with an earlier result.

`--seed` controls bootstrap resampling. A pilot's `base_seed` describes run
provenance and does **not** establish that the provider used a controlled decoding
seed. Multi-run input support is delivered; a prospective study with several
registered provider decoding seeds remains separate experimental work.

## Replay the September canonical study

The committed [report](../experiments/results/variance/canonical-2026-09-28.json)
uses exactly the nine verified bundles listed in the
[canonical coverage study](llm-pilot-canonical-coverage-2026-09-28.md):

```bash
uv run sloplab variance \
    experiments/results/llm-pilot/2026-09-28/36437723703 \
    experiments/results/llm-pilot/2026-09-28/36444462899 \
    experiments/results/llm-pilot/2026-09-28/36457213299 \
    experiments/results/llm-pilot/2026-09-28/36458707078 \
    experiments/results/llm-pilot/2026-09-28/36460357015 \
    experiments/results/llm-pilot/2026-09-28/36461933375 \
    experiments/results/llm-pilot/2026-09-28/36463456436 \
    experiments/results/llm-pilot/2026-09-28/36464461292 \
    experiments/results/llm-pilot/2026-09-28/36464822213 \
    --corpus corpus --bootstrap-samples 2000 --confidence 0.95 --seed 0 \
    --out /tmp/canonical-variance.json
cmp /tmp/canonical-variance.json experiments/results/variance/canonical-2026-09-28.json
```

There are 179 successes and seven failures across 60 cases. The 58 cases with
complete observations form 50 logical report clusters; their observed flip rate
and empirical interval are 0 and [0, 0]. This degenerate interval is conditional
on the supplied complete cases. It cannot bound an unseen population's flip rate
or establish general stability. `saml-019` has a visible flip (four accept, one
manual review) and one failure, so it is excluded from that aggregate.
`sqlx-002` has six failures and no valid decision. These exclusions explain why
the aggregate differs from the earlier descriptive 58/59 unanimity count.

The separate October NVIDIA recovery bundle uses another model and must remain
a separate condition. It does not complete the original Dots study.
