# Review brief: prompt-boundary arm + injection operators

For whoever reviews this change before it goes public - a second model, or a
human. Written by the author of the change, so treat every claim in it as a claim
to be checked, not a conclusion to be accepted.

## Scope

Under review: the uncommitted working tree - ~334 changed lines across 14 files
plus 7 new files (~1300 lines, mostly tests).

```
src/sloplab/evaluators/llm/prompt_safety.py     new    the neutralizer
src/sloplab/evaluators/llm/adapter.py           +100   the two arms
src/sloplab/mutations/operators/injection.py    new    3 attack operators
src/sloplab/scoring/comparison.py               +71    injection_success_by_arm
src/sloplab/models/enums.py, mutations/base.py  small  INJECTION category, spec field
src/sloplab/experiments/config.py, pilot.py     small  defense axis plumbing
src/sloplab/cli/main.py                         +14    metric into analysis.json
docs/safety.md, threat-model.md, decision-log   +90    the policy carve-out
```

Not under review: `experiments/history.py` (already committed as `cee1fde`),
formatting and typing (machine-checked: ruff, ruff format, mypy strict all clean,
314 tests pass).

**A green suite is not evidence here.** Every test was written by the author of
the code it tests, against the threat model the author imagined. Three defects
listed below were found by probing *outside* that model, with the suite fully
green the whole time. Assume more remain.

## Round 2: an independent review found 15 defects. All were real.

The first round of this brief listed three defects the author found by probing
outside their own threat model. An independent review then found **fifteen**,
every one of which reproduced against the working tree. That result is the most
useful thing in this document: the suite was green, the gate was green, and the
author had already been told once that the tests only cover the threats the
author imagined.

Fixed in round 2 - verify the fixes rather than re-finding the defects:

**Arm B was not a fence at all.** Five separate bypasses reached the model
verbatim: the marker words split across a *blank* line; a bare `---` fence in any
CRLF-encoded report; a lowercase Cyrillic homoglyph (the table held only
uppercase, while matching is case-insensitive); a precomposed or combining accent
(`ÉND`); and, in the other direction, benign prose - "our policy on end
untrustedness" - raising `BoundaryError` and causing the adapter to discard the
whole evaluation, which any report could trigger against itself.

The verifier disagreeing with the neutralizer was the root cause of the last one,
and it is now structural: `wrap_untrusted` counts markers with `_MARKER_RE`
itself, so a looser or stricter check cannot drift back in. `_SEP` is unbounded
whitespace, the fence pattern tolerates `\r`, the confusables table is folded in
both cases, and the detection view strips nonspacing marks after NFKD.

**The fixpoint loop was theatre.** Instrumentation showed it could never do more
than one productive pass, and on exhaustion it returned still-dirty text
silently. It is now one pass plus a verification pass that raises.

**History could destroy data.** A file written by a newer schema was treated as
corrupt: warned about, then overwritten with only the current run's entries. A
forward version is now refused without writing, distinct from corruption.

**Provenance could lie on the metered path.** The pilot recorded `config.defense`
in the manifest while sending prompts built from `evaluator.defense`, with no
check that they agreed; the run id collided for two dispatches in the same
second; and history tagged the producer by model alone, so the two arms of one
model merged in `stable_cases(model=...)`.

**Two latent measurement defects.** `injection_success_by_arm` counted records
rather than cases, so repeats would have multiplied it; and neither feature could
be exercised from the metered dispatch path at all - no `--defense` flag, no
`defense` key in the pilot config, no `--history` in the workflow.

Still open, deliberately: the fence neutralizer rewrites any all-dash line, so
Arm B would also rewrite Markdown setext headings. No committed fixture uses
them and a test now pins that, but the confound is latent rather than absent.

Assume more remain.

## Review areas, in order of what a mistake would cost

### 1. The adversary model (agree this before judging anything else)

What can the report author actually control? Answer from the code: arbitrary
UTF-8 inside `report.md`, constrained only by `validate_content_safety`
(`safety/policy.py:86-94`), which checks CVE years and URL hosts and nothing
else. So: effectively arbitrary text.

The neutralizer must be judged against that, not against ASCII. If the reviewer
and the author disagree about the adversary model, every downstream judgement is
noise.

### 2. Is "neutralize then wrap" the right architecture at all?

This is the question most likely to change the design, and the author did not
consider it. The bypass class exists only because the delimiter is a fixed,
guessable string. A delimiter the content cannot predict - a per-case nonce, e.g.
`--- END UNTRUSTED 7f3a91c4 ---` - makes forgery impossible by construction and
removes the need to strip anything.

The tension to weigh: this repository is obsessive about byte-reproducibility
(`docs/reproducibility.md`). A random nonce breaks it. A nonce derived
deterministically from the case would preserve reproducibility but is computable
by anyone who knows the case id - which the mutation author does, though a real
report author would not.

A reviewer should decide whether the stripping design is defensible or whether it
should be replaced. Patching four regexes is the cheap answer; it may be the
wrong one.

### 3. The safety-policy carve-out

The author wrote both the exception in `docs/safety.md` and the operators the
exception permits. That is a structural conflict of interest and the reviewer is
the only control on it.

Concrete method: **read the exception without reading the operators**, write down
what you believe it permits, then read the operators. Divergence in either
direction is a finding - too narrow means the code violates the policy, too wide
means the policy was drafted to fit the code.

Specific things to press on:

- *"generic and widely published"* - who adjudicates this? No test can. The
  author's test checks that payloads do not contain a hardcoded list of company
  names (`test_payload_never_names_a_real_system`), which is a weak proxy
  presented as enforcement.
- `FabricatedTriageNote` invents an `## Automated Triage Result` block asserting a
  verdict. Rule 6 forbids *identity impersonation*. The author judged that
  impersonating a generic automated tool is not impersonating a person or
  organization. That is the closest call in the set and deserves a second opinion.
- Does the amended `threat-model.md` still describe this project honestly to
  someone evaluating whether to adopt it?
- Is shipping three working injection payloads in a public repository the right
  call at all? This is a judgement about audience and context, not correctness,
  and more testing cannot answer it.

### 4. Measurement validity

- **Arm B is two treatments.** It fences *and* modifies content. The author
  documented the confound rather than adding a third arm (fence without
  stripping). Is documenting it sufficient, or does it invalidate the comparison?
- **The A/B pairing is not clean.** The same case yields different *content* in
  the two arms, because Arm B neutralizes. `paired_win_loss` assumes shared cases;
  here the case id is shared but the stimulus is not.
- **Defect 3 above** - is excluding cases where demanded == expected the right
  fix, or should operators demanding `reject` on valid parents be added instead?
  The latter is arguably the more interesting attack (suppressing a real report)
  and the corpus currently cannot express it.

### 5. Control integrity (Arm A must not have moved)

Independently verifiable, and the reviewer should verify it rather than trust the
test. This reconstructs the pre-change prompt from git and hashes it:

```bash
uv run python -c "
import subprocess, hashlib, re
src = subprocess.run(['git','show','HEAD:src/sloplab/evaluators/llm/adapter.py'],
                     capture_output=True, text=True).stdout
ns={}; exec(compile(re.search(r'PROMPT_TEMPLATE = \"\"\".*?\"\"\"', src, re.S).group(0),'<t>','exec'), ns)
print(hashlib.sha256(ns['PROMPT_TEMPLATE'].format(
    report_text='# Sample\n\n## Summary\n\nBody text.\n').encode()).hexdigest())"
```

It must print `ed43b2c7194119c5cc948e57eee0f5166c2935926589b6d4706244a1ffc17bee`,
the value asserted in `tests/unit/test_prompt_boundary.py`. Also confirm the
committed reference results still reproduce byte-identically
(`docs/reproducibility.md` has the command).

### 6. The import-boundary tests

`test_prompt_safety_boundary.py` and `test_history_isolation.py` scan the AST for
`Import`/`ImportFrom` nodes. They therefore **do not** catch
`importlib.import_module("...")`, `__import__`, or reading the module's source as
a file. Whether that residual gap matters is a judgement about the threat being
defended against - benchmark gaming by a contributor - and the reviewer should
say whether a stricter check is warranted or whether the current one is
proportionate.

## What not to spend review time on

Style, formatting, type annotations, and test naming are machine-checked and
clean. Time spent there is time not spent on sections 2 and 3, which are the two
places where a mistake is expensive and where no tool will help.
