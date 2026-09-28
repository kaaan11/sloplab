# Case case-2f6bc8e91d47

## Context

- P1 (setting): This is a fully fictional exercise about AcmePortal build 7.1.4 at https://portal.example.org. There is no running target and no tests were executed to produce these materials.
- P2 (stipulated fact): In AcmePortal a customer-role account may view only invoices owned by its own customer account, unless billing access has been explicitly delegated by the owning account.
- P3 (program policy): The fictional program includes cross-account data access in the AcmePortal customer portal. To begin human verification it requires the exact build, the acting account and role, the ownership of the affected object, a bounded procedure and an observed result. Proof of additional claimed impact is not required to investigate a sufficiently evidenced core issue.
- P4 (assistant role): Only a human can confirm whether a vulnerability exists. The assistant recommends a verification step, requests specific missing information, or identifies likely policy exclusions. It does not assign rewards, close submissions, or advise how a report could pass triage.
- P5 (stipulated fact): Artifacts E1 and E2 are stipulated fictional records of the reporter's session. They show what the reporter says they observed; they are not independent reproduction.

## Report

```text
R01: # Invoice page shows another customer's invoice
R02: Build: AcmePortal 7.1.4, demo tenant on portal.example.org.
R03: Logged in as account cust-17 with the customer role.
R04: Opened my own invoice INV-2203, then requested invoice INV-2204 through the same invoice page.
R05: INV-2204 belongs to account cust-42. cust-17 has no delegated billing access to cust-42 (E1).
R06: The page showed INV-2204 with cust-42's billing name, amounts and line items (E2).
R07: Impact: customer invoice data is exposed across accounts.
R08: Impact: this also lets an attacker change other customers' saved payment details.
R09: I did not try changing any payment details.
```

## Artifacts

E1: (stipulated_synthetic_artifact) Fictional record only: account=cust-17 (role=customer); account=cust-42; delegations between cust-17 and cust-42: none.
E2: (stipulated_synthetic_artifact) Fictional record only: build=7.1.4; caller=cust-17; caller_role=customer; object=INV-2204; object_owner=cust-42; result=200; rendered=billing name, amounts and line items of INV-2204.

## Claims

C1: A customer-role account was shown an invoice owned by an unrelated customer account.
  report refs: `R03`, `R04`, `R05`, `R06`, `R07`
C2: The same issue lets another account's saved payment details be changed.
  report refs: `R08`, `R09`

## How to record your judgment

Before looking at any answer key, copy `owner-judgment.template.yaml` in this directory to `owner-judgment.yaml` and fill it in for this card:
- one `action` for the card as a whole (verify / request_specific_information / likely_out_of_scope)
- optionally the `action_claim_ids` the action is about
- one `confidence` (low / medium / high)
- one short single-line `rationale`
- for every claim listed above one `status`: supported / missing / contradictory

