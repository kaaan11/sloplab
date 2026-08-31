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

### Narrow exception: instruction-override operators (D-0015)

Rules 5 and 6 would otherwise reject prompt-injection operators, which target the
evaluator rather than degrading report quality. A single, bounded exception
applies, because measuring whether an LLM triage evaluator can be hijacked by
report content - and whether a delimiting defense stops it - is exactly the kind
of robustness question this benchmark exists to answer, and cannot be answered
without such cases in the corpus.

The exception permits instruction-override payloads **only** when all of the
following hold:

- they appear only as registered mutation operators under
  `MutationCategory.INJECTION`, each individually documented with the decision
  its payload demands;
- the text is generic and widely published, not novel or tuned - no operator may
  be optimized against a specific system's observed behavior;
- no payload names, targets, or is calibrated against any real triage system,
  product, vendor, or bug-bounty program; reserved namespaces (rule 3) still
  apply in full;
- a defense is measured against them: the operators exist to populate the
  control/treatment comparison recorded in D-0015 (docs/decision-log.md), not on their
  own;
- impersonation of a real person, team, or organization remains rejected under
  rule 6 with no exception.

Everything else in rules 5 and 6 stands. This exception does not license bypass
techniques aimed at systems outside this benchmark.

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
