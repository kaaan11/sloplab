# Installed evaluator plugins

Install a trusted Python evaluator package and select its registered name without
passing a file path on every run. The standard package entry-point group is
`sloplab.evaluators`.

```bash
# Repository example: constant manual-review action, for packaging practice.
uv pip install ./examples/evaluator_plugin
uv run sloplab evaluators
uv run sloplab benchmark benchmarks/suites/v1-core.yaml \
    --evaluator rules-baseline --evaluator-plugin example-review-plugin \
    --out /tmp/plugin-benchmark
uv run sloplab report /tmp/plugin-benchmark/run.jsonl \
    --format html --out /tmp/plugin-benchmark/report.html
```

The example uses a fixed action, confidence and dimensions. It demonstrates
installation and the existing contract; it is not a validated triage baseline.
It is installed separately and does not become a built-in evaluator.

## Discovery and selection

`sloplab evaluators` emits deterministic JSON containing built-in names/versions
and installed plugin metadata: advertised name, import target, distribution,
distribution version and name-conflict flag. It reads entry-point metadata
without importing the plugin target. A metadata listing does not certify that
the factory or evaluator works. JSON escapes control characters in package
metadata.

`benchmark` and `evaluate` accept repeatable `--evaluator-plugin NAME` alongside
`--evaluator` and `--evaluator-module`. Only selected targets are imported.
Built-in-only and direct-module-only runs do not inspect plugin metadata.
Plugin-only runs are supported, including reevaluation of an existing suite:

```bash
uv run sloplab evaluate /tmp/plugin-benchmark \
    --evaluator-plugin example-review-plugin --out /tmp/plugin-evaluate
```

Unknown names, duplicate selections, multiple distributions advertising the
same name, built-in name collisions and collisions with selected modules are
errors before materialization/evaluation. An unrelated broken target does not
need to be imported to list or select a different plugin.

## Package contract

In your package's `pyproject.toml`:

```toml
[project.entry-points."sloplab.evaluators"]
my-evaluator = "my_package.evaluator:make"
```

The target must be an importable `MODULE:ATTR`. A zero-argument factory, class or
existing evaluator object is supported. Dotted object references, such as
`my_package.evaluator:factories.make`, are supported for installed plugins.
The returned evaluator's `name` must exactly match its entry-point name.
`version` is the evaluator version; it can differ from its distribution version.
Run metadata and records retain evaluator name/version as before. Distribution
identity is visible in discovery, not added as a new run provenance field.

The target uses the existing
[BYOE contract and trust model](bring-your-own-evaluator.md). It runs trusted
local Python with the current user's privileges. Installation or selection is
not a sandbox. No marketplace, automatic installation, download, extra dependency
resolution or remote executor is provided. Package authors must supply their
dependencies; optional entry-point extras do not trigger installations.

Plugin targets load through the existing BYOE import/factory adapter to preserve
registry and failed-import cache handling. They cannot request ground-truth
labels; result identities and typed operational failures use the existing
checks. Do not register your object globally from an import or factory.
Rejected fresh imports, factories and advertised-name mismatches restore the
registry and discard only imports owned by that rejected loading attempt.
Arbitrary Python side effects remain outside that limited restoration.

The experiment `study` configuration continues to select its registered
evaluators. This feature applies to the `benchmark`/`evaluate` CLI path.

## Specification references

Python's [importlib.metadata documentation](https://docs.python.org/3/library/importlib.metadata.html)
defines selectable entry-point metadata and its target properties. The
[PyPA entry-point specification](https://packaging.python.org/en/latest/specifications/entry-points/)
defines group/name/object references and leaves duplicate-name handling to the
consumer. SlopLab rejects ambiguous duplicate registrations.
