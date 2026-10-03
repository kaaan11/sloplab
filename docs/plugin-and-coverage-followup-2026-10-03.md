# Plugin delivery and second coverage supplement — 3 October 2026

This wave implements the installed-evaluator backlog item against the
[next-release criteria](next-release-plan.md), and registers one additional
bounded Dots recovery attempt. The current tagged release remains v0.2.2.

## Installed evaluator plugins

- `sloplab evaluators` lists built-ins and installed `sloplab.evaluators` package
  metadata as JSON without importing plugin targets.
- `benchmark` and `evaluate` accept repeatable `--evaluator-plugin NAME` alongside
  built-ins and direct Python modules. Defaults do not inspect plugin metadata.
- Duplicate registrations, built-in/module collisions, advertised-name
  mismatches and invalid factories/contracts are rejected. Selected imports use
  the existing registry/cache restoration and label-free BYOE adapter.
- [An installable constant-review example](../examples/evaluator_plugin/) and
  [package/usage guide](evaluator-plugins.md) are supplied. The example is a
  packaging control, not a trained baseline.

Both project and example wheels were built offline and installed into a new
virtual environment. The installed CLI ran from outside the checkout; the
import path was checked to belong to that environment. Discovery and a mixed
rules/plugin full benchmark succeeded. Two offline HTML renderings were byte
identical. The temporary environment was removed after the check.

## Second realized-edit coverage supplement

The previous snapshot had 417/423 votes. A new pre-dispatch protocol,
`recovery-20261003-02`, retained frozen model IDs, report pairs, request settings,
batch mapping and all prior failure rows. It covered two missing Dots batches
with a maximum of six new requests:

| Batch | New physical requests | Result |
|---|---:|---|
| `batch-031` | 3 | All HTTP 400; three pair votes remain missing |
| `batch-040` | 1 | Success; three pair votes recovered |

Only **four requests** were used. Original 159 + first supplement 8 + second
supplement 4 = **171 physical requests**. There are now **420/423 valid votes**,
**138/141 complete pairs** and dissent on at least one axis in **120/138** complete
pairs. The
[new public bundle](../experiments/results/model-panel/coverage-recovery-2026-10-03-02/realized-edits/)
retains protocol/ledger hashes and normalized public-case annotations.

| Descriptive full-panel majority | Pairs |
|---|---:|
| Quality only | 56 |
| Neither | 78 |
| Uncertain | 4 |
| Incomplete | 3 |

Dots has 138 valid votes; Liquid and NVIDIA retain 141 each. Previously published
snapshots are preserved. The second-human packet's selection and comparisons
remain bound to their earlier 417-vote annotation snapshot; the new bundle does
not silently change that analysis or its denominator.

The public bundle can be replayed without private files or live calls:

```bash
uv run python scripts/summarize_realized_edit_panel.py \
    --bundle experiments/results/model-panel/coverage-recovery-2026-10-03-02/realized-edits \
    --out /tmp/second-recovery
```

## Canonical diagnostic

One separately registered `canonical-sqlx-002` diagnostic used the original
public report/prompt and strict pilot schema on the original free Dots model.
It returned HTTP 400 again. Raw diagnostic/error data remain private. This
diagnostic is not substituted into the original pilot's outcomes. Dots canonical
coverage stays **59/60**; the separate NVIDIA three-observation recovery remains
separate.

This wave used **five live model requests** in total: four batch requests and
one canonical diagnostic. A batch success shows a valid observation in the same
follow-up; the failed requests' root cause is still unknown. The errors alone do
not establish daily-quota exhaustion.

## Backlog reconciliation

Offline HTML with inline SVG charts and the synthetic contribution transaction
plus CI's rule-based content-safety gate already exist. Their stale backlog
entries are updated without claiming new implementations or independent semantic
validation. Additional baselines/local adapters, fixture localization, newly
authored private inputs and prospective live studies remain future work.
Real-world/GitHub source ingestion needs a defined source and provenance/permission
scope; no live target work was performed in this wave.

## Verification

Locked dependency sync, Ruff lint/format, strict mypy and **1244 tests** passed.
The new plugin selection/collision/cache/privacy tests use local installed-package
metadata and synthetic fixtures; no live model calls occur in tests. Clean-wheel
installation and foreign-CWD usage are verified above. All 60 canonical fixtures
are validated, and the new public annotation bundle replays byte for byte.
The lock file and prior public/private snapshots are preserved.

A regression first reproduced the ambiguity between an installed module named
`package.py` and a direct `.py` file. Installed entry points now force importable
module resolution; the original direct-module/file grammar is retained. The
regression and existing import-cache tests pass with the correction.

A local provider-support packet is prepared at
`heldout-private/provider-support/dots-http400-2026-10-03-02/`. It includes the
public canonical request body and redacted diagnostic metadata, with no API key,
Authorization header, private cards or human identity. It has not been sent to
the provider.
