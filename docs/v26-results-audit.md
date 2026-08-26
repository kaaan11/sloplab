# V26 Results Audit - evidence-graph-baseline MDR/FAR root cause (2026-08-25)

Question audited: why does `evidence-graph-baseline` score mutation detection
rate = 0.000 and false reassurance rate = 0.438 on the v0.2 study?

## Method

1. Compared normalized outputs for **12 canonical/mutated pairs** (one per mutation
   family) from `experiments/results/deterministic/study-v02/records.jsonl`.
2. For every pair, recorded decision, edge count, and the two dimensions most
   sensitive to mutations (reproducibility, claim-evidence consistency).
3. Added hand-crafted, minimal family tests
   (`tests/unit/test_evidence_graph_families.py`).

## Result: every family leaves the graph unchanged

All 12 mutated pairs showed **edges=4/4 and identical decisions** to their canonical
parents. Two independent causes, with different dispositions:

### Cause A - contract-conformance gap (fixed, one family)

The edge named "supports" counted an observation as support purely on presence,
even when the observation's own text undermined the claim. That contradicts the
evaluator's documented semantics ("supported by reproduction evidence"). This is
the implementation defect portion of the result.

**Fix:** undermining language in the observed-result section ("however",
"could not reproduce", "returned 403", ...) now breaks the claim-observation edge
(`GRAPH_OBSERVED_UNDERMINES_CLAIM`, high severity) and routes the case to reject.
Reproduction support additionally requires >= 2 ordered steps
(`GRAPH_THIN_REPRO_SUPPORT` otherwise).

### Cause B - by-design blindness (documented, eleven families)

The remaining operators mutate *content quality* inside sections the graph reads
only for presence (impact inflation, fabricated references, invented identifiers,
scope expansion, professionalization, noise, precondition contradictions). Presence
semantics cannot see them; that is the evaluator's declared design.

## Hand-crafted family tests added

| Family | Assertion | Status |
|---|---|---|
| contradict_observed_result | must REJECT (undermined observation breaks support edge) | catch |
| remove_reproduction_step | below 2-step support floor acceptance is unavailable | catch (downgrade) |
| fabricate_reference | decision unchanged - pinned negative control | documented blind |
| impact_inflation | decision unchanged - pinned negative control | documented blind |

## Post-fix study numbers

| Metric | rules-baseline | evidence-graph (negative control) |
|---|---|---|
| Decision accuracy | **0.824** | 0.582 |
| Mutation detection rate | **0.802** | **0.125** |
| False reassurance rate | **0.088** | **0.394** |

MDR moved 0.000 -> 0.125 solely from the contradict family; FAR improved
0.438 -> 0.394 because previously accepted self-undermining cases now reject.

> **v0.2.2 correction:** the "solely" claim above described the V26-era artifact
> set and was imprecise. In the regenerated v0.2.2 study the graph's 12/96 = 0.125
> MDR comprises contradict-observed-result 11/11 **plus one**
> remove-reproduction-step detection (1/10, two-step support floor broken by the
> mutation). The fix description and family tests in this document are unchanged.

## Verdict

- One implementation/contract defect found and fixed (Cause A).
- The evaluator is otherwise a **deliberate negative control**: it proves SlopLab
  detects structure-only triage that ignores content-quality mutations. README and
  docs/evaluator-study-v0.2.md now position it accordingly; it must not be presented
  as a competitive baseline.
