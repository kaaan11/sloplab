# Case case-a83d51f6e0c9

## Context

- P1 (setting): This is a fully fictional exercise about SandboxSuite 5.0. There is no running target and no tests were executed to produce these materials.
- P2 (program policy): The fictional program scope. In scope: the SandboxSuite web application and API at https://app.example.org. Out of scope: https://status.example.org, which is operated by a third-party status provider outside this program; and disclosure of software names or version strings without a demonstrated security impact on an in-scope asset.
- P3 (program policy): To begin human verification the program requires the exact asset, the observed result and, for in-scope assets, the affected build.
- P4 (assistant role): Only a human can confirm whether a vulnerability exists. The assistant recommends a verification step, requests specific missing information, or identifies likely policy exclusions. It does not assign rewards, close submissions, or advise how a report could pass triage.
- P5 (stipulated fact): Artifact E1 is a stipulated fictional record of what the reporter says they observed; it is not independent reproduction.

## Report

```text
R01: # Internal component versions visible on public status page
R02: Asset https://status.example.org/components, observed on the public status page for SandboxSuite.
R03: Without logging in, the page lists internal component names with exact version strings (E1).
R04: Examples from the page: queue-worker 2.8.4, report-renderer 1.19.0, auth-gateway 4.2.1.
R05: An attacker could use these versions to look for known weaknesses in those components.
R06: I did not test any SandboxSuite application or API endpoint.
```

## Artifacts

E1: (stipulated_synthetic_artifact) Fictional record only: host=status.example.org; path=/components; authenticated=false; result=200; listed=queue-worker 2.8.4, report-renderer 1.19.0, auth-gateway 4.2.1.

## Claims

C1: The status page lists internal component names with exact version strings.
  report refs: `R02`, `R03`, `R04`
C2: The list is visible without authentication.
  report refs: `R03`
C3: The listed versions could help someone look for known weaknesses in those components.
  report refs: `R05`

## How to record your judgment

Before looking at any answer key, copy `owner-judgment.template.yaml` in this directory to `owner-judgment.yaml` and fill it in for this card:
- one `action` for the card as a whole (verify / request_specific_information / likely_out_of_scope)
- optionally the `action_claim_ids` the action is about
- one `confidence` (low / medium / high)
- one short single-line `rationale`
- for every claim listed above one `status`: supported / missing / contradictory

