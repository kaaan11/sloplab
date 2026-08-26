# SlopLab Dataset Card

## Corpus identity

- **Name:** SlopLab V1 corpus
- **Version:** 0.2.2 (matches package version)
- **License:** CC0-1.0 (all fixture text and manifests)
- **Composition (60 canonical fixtures):**
  - 18 `valid` - complete, well-calibrated reports of synthetic issues
  - 10 standalone `invalid` - plausible-looking reports that cross no security boundary
  - 16 `review` - honest, genuinely ambiguous reports requiring human triage
  - 8 presentation pairs (16 files, `invalid` class) - the same invalid finding
    written plainly (`pair_role: plain`) and professionally (`pair_role: polished`)

Derived adversarial cases are generated deterministically from these canonicals by
the mutation engine and are not committed as source data.

## Provenance

Every fixture is **fully synthetic**, authored for SlopLab. No real bug-bounty
reports, private program data, or third-party copyrighted material is included.
All scenarios take place in fictional demo applications:

| Fictional asset | Used for |
|---|---|
| DemoVault (`demo.example.org`) | documents, authz, TLS/session scenarios |
| AcmePortal (`portal.example.org`) | workspace/portal scenarios |
| MockMart (`shop.example.org`) | storefront scenarios |
| ToyTracker (`tracker.example.org`) | billing/profile scenarios |
| SampleStack (`stack.example.org`) | API/identity scenarios |
| PlaygroundAPI (`api.example.org`) | commerce/API scenarios |

## Safety properties

- All fabricated CVE references use the fictional far-future year: `CVE-2099-*`.
- All URLs use RFC 2606 reserved domains or loopback/private addresses; no public
  host is ever named as a target.
- Product, component, and person names come from fixed synthetic lists
  (`src/sloplab/safety/policy.py`).
- No working exploit code: code blocks contain at most inert request sketches
  against reserved hosts.
- Automated validation (`sloplab validate corpus/`) enforces these rules on every
  canonical and derived fixture.

## Ground truth

Each manifest records:

- `ground_truth.reproducible` - whether the claimed behavior reproduces as written
- `ground_truth.impact_class` - calibrated severity within the sandbox context
- `ground_truth.required_evidence` - report sections the class requires
- `ground_truth.disallowed_claims` - claims that would make the report wrong
- `ground_truth.expected_dimensions` - target quality-dimension scores (0..1)
- `ground_truth.rationale` - why this class is correct

Expected triage decisions by class: valid -> accept, invalid -> reject,
review -> needs_manual_review. Presentation-pair members share identical ground
truth across the pair by construction.

## Known limitations

- English only; phrasing diversity is limited to what 60 hand-authored reports can
  cover.
- Review-class ground truth reflects maintainer judgment for the fictional
  scenarios; reasonable people could disagree on individual classifications.
- The uncertainty-detector overlap noted in methodology.md applies to baseline
  evaluation of review-class fixtures.
