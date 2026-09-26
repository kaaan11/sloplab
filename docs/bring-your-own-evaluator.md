# Bring your own evaluator (BYOE)

Measure your evaluator beside a built-in baseline without editing SlopLab source,
then open a single offline HTML report. No new runtime dependencies are required.

## Five-minute walkthrough

From the repository checkout:

```bash
uv sync --locked --group dev

uv run sloplab benchmark benchmarks/suites/v1-core.yaml \
  --evaluator rules-baseline \
  --evaluator-module examples/my_evaluator.py:make \
  --out /tmp/byoe

uv run sloplab report /tmp/byoe/run.jsonl \
  --format html \
  --out /tmp/byoe/report.html
```

Open `/tmp/byoe/report.html` in your browser, even with networking disabled. It
contains inline CSS and numeric SVG, no JavaScript, fonts, images or remote
resources. Light/dark appearance follows the system. Tables scroll horizontally
on small screens and are keyboard-focusable. Documentation links are ordinary
links, not required resources.

The example is a **structure-only teaching heuristic**, not a validated triage
system. Its factory is `make()`. Copy the file and replace the heuristic, keeping
the [existing evaluator contract](evaluator-contract.md). Echo `context.case_id`,
your evaluator's `name`/`version`, and return an `EvaluationResult` with all five
quality dimensions. Its ordinary name is `example-structure`.

Already materialized cases can be reused:

```bash
uv run sloplab evaluate /tmp/byoe \
  --evaluator rules-baseline \
  --evaluator-module ./my_evaluator.py:make \
  --out /tmp/byoe-evaluated
```

## Loading and trust

`--evaluator` and `--evaluator-module` are repeatable and **can be combined**.
Built-ins only, externals only, and mixed selections all work; at least one source
is required. A missing/invalid selection is rejected before materialization.

Supported external specifications:

```text
./my_evaluator.py:make       # zero-argument factory
./my_evaluator.py:evaluator  # existing object
mypkg.triage:evaluator      # importable Python module and attribute
```

The `.py` source is loaded with Python's import machinery under an isolated module
name (including support for dataclass decorators). For package-relative imports,
prefer the importable module form and install your package into the environment.
`name` and `version` must be non-empty unpadded strings; `evaluate(report, context)`
must be synchronous and callable. Invalid result types/identities are contract
errors, not fake decisions. Import/factory/contract errors identify the failing
stage/field without dumping raw exception or model response text.

**Only load trusted local Python. `--evaluator-module` is not a sandbox: code runs
with your current user's privileges.** Import and factory execution can have side
effects. SlopLab does not supply a network client, subprocess protocol or remote
executor, but arbitrary external Python can do those things itself. Filesystem,
network and process isolation are not provided.

External evaluators receive **no ground-truth labels through the harness**.
A truthy `requires_labels` is rejected; a missing attribute defaults to false.
The adapter retains the false capability, rechecks it during evaluation, and
passes an empty labels mapping. Report identity uses the existing opaque handles.
This protects the evaluation API against accidental label access, not a malicious
Python program reading the corpus manifests from disk.

External objects are passed directly to the harness, not registered globally.
Do **not** call `register_evaluator()` at import time or inside a factory. The
loader snapshots the registry mapping, rejects replacement/addition/removal and
restores it even on import/factory failure. It does not undo arbitrary mutations
to Python objects or other process state; it is not a security boundary or a
concurrent plugin manager. Resolve before running evaluations.

Every selected name must be unique. Collisions with any registered built-in,
between external modules, or via duplicate specifications are errors. Built-in
instances are resolved before external imports. Unsafe/long evaluator names are
never used as paths: their metrics filenames use a deterministic SHA-256 suffix.
The original name is retained in JSON metadata and escaped in HTML.

## Outcomes and provenance

A completed normal `benchmark` or `evaluate` run writes:

```text
run.jsonl          # existing RunMetadata + successful CaseRecord observations
outcomes.jsonl     # typed operational failures; empty means observed zero failures
metrics-*.json     # existing metric definitions
report.md          # existing Markdown format
```

External evaluators can raise the existing typed operational failure:

```python
from sloplab.evaluators.llm.failures import EvaluationFailure

raise EvaluationFailure(
    error_kind="timeout",  # use existing ERROR_KINDS, not arbitrary messages
    adapter_attempts=1,
    rendered_prompt_hash="",
    detail="transport.timeout",
)
```

The harness isolates that failed case, continues its siblings and records **no
invented decision**. Unexpected programming/contract errors still fail the run.
The sidecar reuses the study outcome fields (`schema_version: 1`, `status: failed`,
`case_id`, `evaluator_name`, `repeat_index: 0`, `error_kind`). It deliberately omits
raw detail, prompts, tracebacks and unchecked exception data. Unknown error-kind
strings use the existing `unknown` fallback; recognized `ERROR_KINDS` are preserved.
Successful result metadata is still authored by your evaluator: do not put secrets
there either. HTML does not render free-form result metadata/rationales.

Failure rows are sorted by evaluator and case. Every completed run writes the
sidecar, including an empty one, so reusing an output directory does not retain
old failures. Its exact SHA-256 is stored as `suite_config.outcomes_sha256` in the
run metadata. Missing or mismatched bound sidecars are errors. Duplicate rows,
unknown evaluator identities or a case marked both scored and failed are rejected.

For older runs with no sidecar, HTML says **Operational failure ledger not
available for this legacy run**. It never infers failures from missing successes.
Older sidecars without a hash remain readable, explicitly marked unbound. This
small binding is not whole-bundle atomic publication: normal benchmark/evaluate
bundles retain their existing legacy lifecycle. Do not consume interrupted runs.

## Reading the report correctly

These are **authored-target agreement** measurements on a synthetic corpus. They
are **not verified real-world triage accuracy, bug-bounty performance, or proof of
general semantic security competence**. No independent human validation is claimed.
The known rules-baseline surface-signature risk remains visible: fixed regexes
can recognize mutation phrasing instead of understanding the underlying claim.
An oracle, when present, is a label-reading plumbing control, not a competitor.

The report reuses `compute_metrics`, `per_operator_metrics`, and
`scoring.comparison.bootstrap_accuracy_ci`. The interval uses 2,000 resamples,
95% confidence and an explicit seed from run metadata (0 if absent). It is the
existing case-level percentile bootstrap, **not** a cluster-adjusted interval:
canonical reports and their variants are correlated. Check failure coverage and
operator case counts before comparing percentages.

Only successful records with expectations contribute to scored accuracy and its
interval. All-failed evaluators remain visible with zero scored cases and
**Not available** metrics, not fictitious zero accuracy. Operational failures have
a separate section and are not added to scoring denominators. Evaluator versions
come from metadata/records; conflicting versions are rejected, not pooled.

For identical input artifacts the HTML bytes are identical. It uses no wall clock,
unseeded randomness, machine-specific input paths or external resources. Displayed
timestamps come only from run metadata; an absent timestamp stays Not recorded,
not a fresh model default. Text is HTML-escaped, including names,
versions, operators and suite metadata; SVG receives only bounded finite geometry.

Markdown remains the default. Its existing `--analysis` path is unchanged.
`--format html --analysis ...` is intentionally rejected: V1 HTML needs the records
and sibling outcomes, which versioned analysis alone does not fully describe.
No evaluator marketplace, sandbox, remote execution, live evaluation UI, new
metric definitions, corpus changes or TUI changes are part of this feature.

Write HTML outside integrity-marked study/pilot directories: adding a new file inside
such a directory would invalidate its completion hashes. Normal benchmark/evaluate
output directories support the sibling `report.html` path shown above.
