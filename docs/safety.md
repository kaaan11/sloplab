# SlopLab Safety Policy

## Purpose

SlopLab exists for evaluation, education, and defensive research: measuring whether
triage systems classify degraded reports correctly. This policy is binding for all
corpus content, mutation operators, and contributions.

## Hard rules

1. **Evaluation only.** SlopLab never scans, attacks, exploits, or connects to real
   targets. There is no network code in the deterministic pipeline.
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

## Enforcement

- `src/sloplab/safety/policy.py` provides the only approved generators for synthetic
  identifiers; operators import from there.
- Corpus validation (`sloplab validate`) checks manifests and reports for policy
  compliance (reserved-namespace regexes, forbidden-content markers).
- Tests assert that every generated adversarial fixture passes safety validation.

## Reporting a problem

If you find sensitive data, unsafe content, or a policy violation in this repository,
do not open a public issue. Contact the maintainers privately (see SECURITY.md).
