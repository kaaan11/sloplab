# Nemotron mutation repeats — 7 October 2026

A new study evaluated the same 60 public canonical controls and 237 existing
mutations in three fresh passes. All **891 authorized model calls** were made:
**890 valid responses, one transport failure, no unstarted evaluations**.
The failed response was not replaced. The
[registered protocol](../experiments/results/llm-pilot/2026-10-07/nemotron-mutation-repeats-01/protocol.json)
and [verified summary](../experiments/results/llm-pilot/2026-10-07/nemotron-mutation-repeats-01/summary.json)
retain the complete accounting.

## Protocol and coverage

- Requested model: `nvidia/nemotron-3-super-120b-a12b:free`, OpenRouter chat completions.
- Existing `triage-v1` prompt, strict JSON Schema, temperature 0, required provider
  parameter support; no provider decoding seed.
- Three fixed-order passes, each containing 60 fresh canonical controls followed
  by all 237 existing mutations. Ninety batches, at most ten cases per batch.
- Each bundle's local repeat index 0 maps to the protocol batch's global index
  0, 1 or 2. On-disk records are preserved; replay applies this mapping in memory.
- No automatic retries or budget extensions. A cumulative cap of 891, 60-second
  request timeout, per-batch deadline and minimum 3.1-second start interval apply.
- Catalog and all listed endpoint prices were checked as zero before each batch.
  Access/rate-limit failure or an unsuccessful route check stops later calls.
  Response-level billing is not retained, so no exact billed total is asserted.
- Historical observations were not reused as new repeats or fresh parent controls.
  Private human adjudications did not change this suite's authored targets.

`mut-csvinj-017-professionalize-language-04` failed with `transport.error` in
repeat 0. This is the recorded error classification; its underlying exception
is not retained. All 90 bundles completed publication, but full response coverage
is **false**. Missing responses are not decisions or target mismatches.

## Decision stability

A case changes decision when at least two of its three valid decisions differ.
Only complete triples enter that denominator; incomplete cases stay explicit.

| Population | Eligible cases | Complete triples | Unanimous | Decision changed | Incomplete |
|---|---:|---:|---:|---:|---:|
| Canonical controls | 60 | 60 | 56 | 4 | 0 |
| Mutations | 237 | 236 | 217 | 19 | 1 |

Among complete mutation triples, 19/236 (8.05%) changed decision. This measures
variation on this collection, not correctness or general reliability. The summary
contains per-case decisions and per-operator coverage and change counts.

## Authored-target agreement and fresh pairing

| Global repeat | Canonical matches / valid | Mutation matches / valid | Decision-preserving drift / available pairs |
|---|---:|---:|---:|
| 0 | 57/60 | 143/236 | 8/140; one of 141 pairs missing |
| 1 | 60/60 | 141/237 | 2/141 |
| 2 | 59/60 | 142/237 | 9/141 |

There are 426 target matches among 710 valid mutation observations (60.00%).
This pooled descriptive count is not 710 independent samples. Canonical control
agreement is 176/180. Decision-changing target agreement (96 mutations whose authored decision
differs from the parent) is 4/96 in repeat 0, 2/96 in repeat 1 and 6/96 in
repeat 2. Full-suite production metrics are withheld for repeat 0 because
one response is missing; its valid-subset counts remain available.

Parent/child comparisons use fresh controls from the same global repeat. Stable
wrong decisions can coexist with low drift. Targets are authored synthetic
expectations, not independently established real-world truth. Cases share parents
and templates; no new independence-based confidence intervals are reported.
The free model alias and provider version are not pinned. Chronology and provider
changes cannot be separated from variation across these three fixed-order passes.

## Offline replay after maintenance commits

```bash
uv run python experiments/scripts/replay_nemotron_mutation_repeats.py
```

The replay needs no credentials, network or old Git objects. A post-study
[source/input snapshot](../experiments/frozen/nemotron-mutation-repeats-2026-10-07/snapshot-manifest.json)
preserves the registered 81 source/config files and public input files. The
protocol's original source hashes and input identities remain authoritative;
the snapshot does not create a new pre-dispatch registration.

The wrapper reconstructs a temporary tree and starts the original hash-bound
verifier in a separate Python process. Since that tree has no Git checkout, only
its HEAD lookup is replaced with the original recorded commit metadata. All
source hashes, report/target/input identities, route observations, bundle hashes,
unique outcome keys, request counts, fresh-parent pairing and saved summary are
checked by the original verifier. The recorded tree included the then-uncommitted
study tools; commit SHA alone is not the complete source identity.

The original current-checkout verifier remains available for an exact registered
checkout. The snapshot wrapper supports later code changes and shallow clones.
Pinned precisely: study source and public inputs come from the snapshot (hash
checked); third-party packages are not vendored, so the wrapper only checks that
the installed pydantic, pydantic-core and pyyaml versions equal those pinned in
the snapshot `uv.lock` and fails with a message naming the package otherwise.
The Python interpreter and the standard library are not pinned.
The runner rejects existing started archives, including interrupted ones. No live
calls are made by replay or tests.
