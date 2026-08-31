# Plan: Cross-Run Decision History

Status: approved for implementation (revision 2)
Supersedes: the initial draft that wired history only into `run_llm_pilot` and
placed the module under `src/sloplab/scoring/`.

## Problem

`repeat_stability` (`src/sloplab/scoring/comparison.py:210`) measures agreement
*within* one run's repeats. Nothing measures agreement *across* runs, so drift
caused by a model swap or a corpus change is invisible. The runbook's flip-rate
warning is likewise intra-run only.

## What changed from the first draft, and why

| # | Draft said | Revision says | Reason |
|---|---|---|---|
| 1 | Module lives in `src/sloplab/scoring/history.py` | `src/sloplab/experiments/history.py` | `docs/reproducibility.md` guarantees no wall-clock input participates "in mutation, evaluation, or **scoring**". A wall-clock `ts` under `scoring/` violates the letter of that. This is run provenance, not scoring. It also makes the evaluator import boundary natural: `evaluators/` already imports nothing from `experiments/`. |
| 2 | Wire only into `run_llm_pilot` | Wire into `run_llm_pilot` **and** `sloplab benchmark --history` | Per D-0013 the live pilot has never run (no API key) and `llm-benchmark.yml` runs on an ephemeral runner that uploads only `llm-bench-results.jsonl` + `.bundle/`. A history file written there vanishes at job end, so `stable_cases()` would always be empty. The deterministic benchmark path is what actually runs today, and corpus-change drift is exactly what it can catch. |
| 3 | One history entry per record | One entry per `(case_id, run)`, decision aggregated over repeats | Pilot protocol is 3 repeats. Writing one entry per record makes `stable_cases(threshold=3)` satisfiable *inside a single run* — i.e. a second, worse copy of `repeat_stability`. |
| 4 | `stable_cases(threshold)` only | `stable_cases(threshold, *, model=None, corpus_version=None)` | Comparing entries produced by different models or corpus versions and calling the result "stable" is misleading. The filter is load-bearing, not cosmetic: `sloplab benchmark` can run several evaluators over one history file, and without a `model` filter their entries interleave into nonsense. |
| 5 | Ban only `evaluators/` → `scoring.history` | Ban `evaluators/` → all of `sloplab.scoring` and `sloplab.experiments` | `evaluators/` currently imports only `models`, `corpus.conventions`, `mutations.textops`. A one-module ban is narrower than the real invariant and would silently permit `scoring.comparison`. |
| 6 | "Each test FAILs before implementation" | The boundary test is demonstrated by temporarily injecting the forbidden import | A test asserting `evaluators/` does not import a module that does not yet exist passes trivially. The draft's blanket fail-first rule is unsatisfiable here; every other test still fails first. |
| 7 | Adapt an Apache-2.0 reference, cite it | Written from scratch, no citation | Nothing worth attributing is being copied: a dict keyed by id, temp-file + `os.replace`, and a "last N agree" check. Repo is MIT; avoiding an Apache-2.0 derivative keeps `docs/dataset-card.md`'s licence bookkeeping clean. |
| 8 | "Append-only" + atomic write | Read-modify-write whole file + atomic replace, stated as such | The two are in tension: a real line append needs no temp file. The temp+replace dance is required *because* the whole file is rewritten. Naming this prevents a confused half-and-half implementation. |
| 9 | silent on write failures | write path never raises either | The pilot is the only path that spends money. An exception after 180 paid requests would be the worst possible failure, so history recording happens strictly after `records.jsonl` and `manifest.json` are on disk, and swallows its own errors. |
| 10 | silent on concurrency | documented limitation | `os.replace` prevents corruption, not lost updates. Two concurrent runs: last writer wins. Acceptable here; must not be implied otherwise by the word "atomic". |

## Deliverable — `src/sloplab/experiments/history.py`

### On-disk format

Single JSON file, UTF-8, trailing newline:

```json
{
  "schema_version": 1,
  "cases": {
    "canonical-crypto-011": [
      {"ts": "2026-08-31T18:22:41Z", "decision": "accept",
       "model": "rules-baseline@0.2.2", "corpus_version": "0.2.2",
       "run_id": "run-ab12cd34ef56"}
    ]
  }
}
```

The envelope (`schema_version` + `cases`) is a deliberate deviation from the
draft's bare `{case_id: [...]}`: it makes corruption detection precise and leaves
room for a future migration.

`model` is "whatever produced the decision": the live model id for the pilot,
`"<evaluator-name>@<version>"` for deterministic evaluators.

### API

- `HistoryEntry` — frozen dataclass: `ts, decision, model, corpus_version, run_id`.
- `DecisionHistory.load(path)` — missing file → empty history, no warning.
  Unreadable / malformed / wrong-shaped file → empty history + `warnings.warn`.
  Never raises.
- `.append(case_id, entry)` / `.entries(case_id)` / `.case_ids()`
- `.save(path)` — atomic: temp file in the same directory, `flush` + `fsync`,
  then `os.replace`. Temp file removed on failure.
- `.stable_cases(threshold=3, *, model=None, corpus_version=None) -> set[str]` —
  cases whose last `threshold` entries (after filtering) all share one decision.
  Fewer than `threshold` entries → not stable.
- `entries_from_records(records, *, model, corpus_version, run_id, ts)` —
  collapses a run's `CaseRecord`s into one entry per `case_id`. Records with
  `evaluation_metadata["failed"]` are dropped (consistent with the runbook's
  "failed evaluations are excluded"); a case with no surviving record is omitted.
  Decision is the majority over repeats, ties broken by sorted decision value.
- `record_run(path, entries) -> bool` — load, append, save. Returns `False` and
  warns instead of raising on any failure.

### Ordering

Entries within a case are kept sorted by
`(ts, run_id, model, corpus_version, decision)`. Timestamp ties therefore order
deterministically, and the sort is applied on load and after every append.

### Identity

Keyed by the **true** `case_id` from `CaseRecord.case_id`, never the opaque
handle from `scoring/harness.py:opaque_case_handle`.

## Wiring

1. `run_llm_pilot(..., history_path: Path | None = None)` — records after
   `records.jsonl` and `manifest.json` are written. `None` (the default) is a
   no-op, so existing behaviour and tests are untouched. `model` comes from
   `os.environ.get(config.model_env, "unknown")` (the workflow supplies this as
   a repo *variable*, not a secret). A `run_id` is derived from
   `sha256(name | commit_sha | prompt_hash | finished_at)[:12]` and also added to
   the manifest.
2. `scripts/llm_bench.py --history PATH` — optional passthrough.
3. `sloplab benchmark --history PATH` — one entry set per evaluator, recorded
   after `run.jsonl` is written.

Nothing is recorded from `evaluators/` or from any evaluation code path.

## Hard constraints

1. History is keyed by the true `case_id`, never the opaque handle.
2. `src/sloplab/evaluators/` must not import `sloplab.scoring` or
   `sloplab.experiments`. Enforced by an AST-scanning regression test.
3. Evaluator-visible input is unchanged. `docs/evaluator-contract.md` is binding
   and is not edited.
4. No commits, no pushes.
5. `uv run pytest -q`, `ruff check`, `ruff format --check`, `mypy src tests` green.

## Known limitations (to be documented, not fixed here)

- The `llm-benchmark` workflow runs on an ephemeral runner. History accumulates
  across pilot dispatches only if the operator carries the file forward from the
  previous run's artifact; the runbook documents this. No third-party GitHub
  Action is introduced to automate it.
- Concurrent writers: last writer wins.
- No retention policy. Growth is linear in runs × cases.

## Definition of done

Each test below fails before implementation and passes after, except the import
boundary test, which is demonstrated by temporarily injecting the forbidden
import.

- two consecutive runs produce a history file containing both entries
- `stable_cases()` returns the expected set for a hand-built history, and the
  `model` filter separates two evaluators sharing one file
- a corrupt history file warns and starts fresh instead of crashing
- an unwritable history path warns and does not fail the run
- entries sharing a timestamp order deterministically
- repeats collapse to one entry per case; failed evaluations are excluded
- `evaluators/` imports neither `sloplab.scoring` nor `sloplab.experiments`
- the pilot's `records.jsonl` is byte-identical with and without history enabled
- full suite green
