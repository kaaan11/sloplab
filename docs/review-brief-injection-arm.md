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

## Defects found and fixed while writing this brief - verify the fixes

All three were found by probing *outside* the author's threat model, with the
suite fully green throughout. They are listed because the fixes need checking,
and because they calibrate how much the green suite is worth.

1. **The neutralizer matched literal ASCII and was trivially bypassable.**
   `END\nUNTRUSTED REPORT` (a plain newline between the words), a non-breaking
   space separator, a zero-width space inside the word, and a Cyrillic `Е` all
   walked straight through. The task called this stripping non-negotiable -
   "without it, Arm B measures a paper defense" - and it did.

   *Fix to verify:* detection now runs on a normalized view (format characters
   dropped, per-character NFKC, bounded confusables table), with matched spans
   mapped back to the original text so only the match is edited
   (`prompt_safety.py:detection_view`). Check the mapping is exact, check the
   over-match tests are the right ones, and check whether the confusables table's
   bounded scope is stated honestly enough.

2. **The wrap post-condition gave false assurance.** It counted occurrences of
   the literal marker, so every bypass above satisfied the check that existed to
   catch them. *Fix to verify:* the count now runs over the detection view.

3. **`injection_success_by_arm` counted correct evaluations as successes.** All
   operators demand `accept` and injected cases keep the parent's expected
   decision, so on a valid parent expected == demanded and obeying is
   indistinguishable from being right. *Fix to verify:* such cases are excluded
   and reported as `undecidable_cases`. Judge whether exclusion is the right
   remedy, or whether operators demanding `reject` on valid parents should be
   added instead - suppressing a real report is arguably the more interesting
   attack, and the corpus cannot currently express it.

Assume more remain. Every test was written by the author of the code it tests,
against the threat model the author imagined.

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
