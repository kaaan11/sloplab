# SlopLab Safety Policy

## Purpose

SlopLab exists for evaluation, education, and defensive research: measuring whether
triage systems classify degraded reports correctly. This policy is binding for all
corpus content, mutation operators, and contributions.

## Hard rules

1. **Evaluation only.** SlopLab never scans, attacks, exploits, or connects to real
   targets. There is no network code in the deterministic pipeline.

   The live LLM pilot is the single exception that opens a socket, and it is bound
   by the same rule: it may be pointed **only** at a model endpoint you own or are
   explicitly authorized to test. Running any operator family against a third-party
   service - and the `INJECTION` family in particular, whose payloads target the
   evaluator rather than the report - is outside this policy and outside this
   project's purpose. The policy governs how corpus content is written; this clause
   governs where it may be sent, and both are binding.
2. **No working exploits.** Fixtures describe synthetic vulnerabilities in fictional
   demo applications. Code blocks contain at most illustrative request/response
   sketches against `example.*` hosts - never weaponized payloads, shellcode,
   obfuscation chains, or automation scripts.
3. **Reserved namespaces only for fabricated identifiers.**
   - CVE references: `CVE-2099-NNNN` (fictional far-future year) exclusively.
   - URLs/hosts: RFC 2606 reserved domains (`example.com`, `example.org`,
     `example.net`, `example.edu`) and their subdomains.
   - Products, components, researchers: fixed synthetic lists in
     `src/sloplab/safety/policy.py`.
4. **No real-report ingestion in V1.** The corpus is synthetic. Publicly disclosed
   sanitized examples may be considered later only with explicit license, permission,
   PII scrubbing, and target de-identification (see backlog).
5. **No evasion optimization.** New operators must model report *quality degradation*
   or *presentation manipulation*, must be individually documented, and must not
   materially advance deceptive-report-writing capability beyond what the benchmark
   requires for measurement.
6. **Rejected contribution classes:** triage bypass techniques, identity impersonation,
   false attribution of claims to real products/CVEs/people, exploit automation,
   unlicensed or private report material.

### Exception 7: evaluator-directed content, in two named classes

Rules 5 and 6 reject content that targets the evaluator rather than degrading
report quality. A bounded exception applies, because whether an LLM triage
evaluator can be steered by the text it is reading - and whether a defense stops
it - is the robustness question this benchmark exists to answer, and it cannot be
answered without such cases in the corpus.

The exception is written by mechanism, not by implementation. Two classes are
admitted, each on its own terms. A payload that is neither is **not** covered,
and a new mechanism needs a new clause here before any operator implements it.

**7a - Instruction override.** Content that directs the reader to disregard its
own task or its prior instructions. Admitted when:

- the text is a generic, widely published shape, not novel and not optimized
  against any observed system's behavior;
- it names, targets, or is calibrated against no real triage system, product,
  vendor, or bug-bounty program;
- a defense is measured against it, so the payload exists to test a mitigation
  rather than on its own.

**7b - Fabricated authority.** Content that asserts a verdict, status, or
approval as though it came from outside the report - an automated check, a prior
review, a pipeline result - in order to substitute for the evaluator's own
judgement. This is a different mechanism from 7a: nothing is overridden, an
answer is supplied and dressed as established fact. Rule 6 does not reach it,
because rule 6 forbids impersonating an identity and attributing claims to real
named things, while this attributes to nothing at all. That gap is closed here
rather than left to interpretation. Admitted when, in addition to every condition
in 7a:

- the asserted authority is unattributed: no real or plausible tool, team,
  vendor, workflow, or product name appears, so nothing is impersonated and no
  claim is attributed to anything real;
- the payload is a demonstration of the mechanism, not a finished artifact for a
  particular target's workflow - it must not be tuned to imitate the output
  format of any real triage system.

**Bounds on both classes.** These are limits the first version of this exception
omitted, and their absence is what let an operator be admitted under a clause
that did not describe it:

- the corpus carries at most a handful of operators per class - enough to measure
  a mechanism, not a library of payloads;
- every admitted operator must name, in code, which clause admits it, and a test
  asserts that the named clause exists in this document;
- an operator whose mechanism drifts out of its clause must be re-argued here,
  not quietly reclassified.

Everything else in rules 5 and 6 stands. This exception licenses nothing aimed at
systems outside this benchmark, and impersonation of a real person, team, or
organization remains rejected with no exception.

## Enforcement

- `src/sloplab/safety/policy.py` provides the only approved generators for synthetic
  identifiers; operators import from there.
- Corpus validation (`sloplab validate`) checks manifests and reports for policy
  compliance (reserved-namespace regexes, forbidden-content markers).
- Every output boundary validates content before anything is written or emitted:
  the materializer refuses unsafe derived cases (recorded as safety violations,
  nonzero exit), the `sloplab mutate` CLI refuses to write unsafe output, and tests
  assert that every generated adversarial fixture passes safety validation -
  including a fake unsafe-operator test proving both boundaries fail closed
  (v0.2.2, R03).

## Reporting a problem

If you find sensitive data, unsafe content, or a policy violation in this repository,
do not open a public issue. Contact the maintainers privately (see SECURITY.md).
