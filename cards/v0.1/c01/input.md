# Case case-5e19a4c07b32

## Context

- P1 (setting): This is a fully fictional exercise about ToyTracker build 3.2.0 at https://tracker.example.org. There is no running target and no tests were executed to produce these materials.
- P2 (stipulated fact): ToyTracker's documented account policy for build 3.2.0 states that every outstanding password-reset link for an account stops working as soon as that account's password is changed.
- P3 (program policy): The fictional program includes account-security flaws in the core ToyTracker web application. To begin human verification it requires the exact build, the acting account, the ordered steps and the observed result. It sets no minimum report length and requires no particular headings, severity score or impact section.
- P4 (assistant role): Only a human can confirm whether a vulnerability exists. The assistant recommends a verification step, requests specific missing information, or identifies likely policy exclusions. It does not assign rewards, close submissions, or advise how a report could pass triage.
- P5 (stipulated fact): Artifacts E1 to E3 are stipulated fictional records of the reporter's session. They show what the reporter says they observed; they are not independent reproduction.

## Report

```text
R01: # Old reset link still works after password change
R02: ToyTracker 3.2.0, test account on tracker.example.org.
R03: 1. As user acct-310, request a password-reset link (E1).
R04: 2. While logged in as acct-310, change the password through account settings (E2).
R05: 3. Open the link from step 1 and set another password. It is accepted (E3).
R06: Expected the step-1 link to be rejected after step 2.
```

## Artifacts

E1: (stipulated_synthetic_artifact) Fictional record only: build=3.2.0; account=acct-310; event=reset_link_issued; link_id=rl-7731; time=T0.
E2: (stipulated_synthetic_artifact) Fictional record only: build=3.2.0; account=acct-310; event=password_changed; method=account_settings; result=success; time=T1 (after T0).
E3: (stipulated_synthetic_artifact) Fictional record only: build=3.2.0; account=acct-310; event=reset_link_used; link_id=rl-7731; result=password_updated; time=T2 (after T1).

## Claims

C1: A password-reset link issued before a password change was accepted after that change.
  report refs: `R03`, `R04`, `R05`
C2: Accepting that link differs from the product's documented behavior.
  report refs: `R06`

## How to record your judgment

Before looking at any answer key, copy `owner-judgment.template.yaml` in this directory to `owner-judgment.yaml` and fill it in for this card:
- one `action` for the card as a whole (verify / request_specific_information / likely_out_of_scope)
- optionally the `action_claim_ids` the action is about
- one `confidence` (low / medium / high)
- one short single-line `rationale`
- for every claim listed above one `status`: supported / missing / contradictory

