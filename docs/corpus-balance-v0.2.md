# Corpus Balance Report - v0.2 (V22)

## Summary

Twelve new synthetic canonical fixtures were added (6 valid, 6 review), bringing
the corpus from 48 to **52 files / 40 logical reports** - within the charter cap of
60. All fixtures pass `sloplab validate` with zero errors and warnings.

## Class distribution

| Class | v0.1.1 files | Added | v0.2 files | Logical share |
|---|---:|---:|---:|---|
| valid | 12 | +6 | **18** | ~35% |
| invalid | 18 (10 standalone + 8 pair members) | +0 | **18** | ~35% |
| review | 10 | +6 | **16** | ~30% |

Presentation pairs remain 8 pairs (16 files) inside the invalid count; their
plain/polished roles are unchanged.

## New fixtures

| ID | Class | Scenario |
|---|---|---|
| canonical-tokenurl-013 | valid | Session token echoed in redirect query parameter |
| canonical-massign-014 | valid | Mass assignment of display-role field |
| canonical-ghauthz-015 | valid | GraphQL mutation skips workspace membership check |
| canonical-xssref-016 | valid | Reflected injection in search error attribute context |
| canonical-csvinj-017 | valid | Spreadsheet formula injection via exported CSV |
| canonical-websig-018 | valid | Webhook accepts unsigned/missigned payloads |
| canonical-totiming-019 | review | Sign-in timing gap, inconclusive across runs |
| canonical-permdiff-020 | review | API version field-set divergence, intent undocumented |
| canonical-cspnonc-021 | review | CSP permissiveness varies by undocumented profile |
| canonical-wstoken-022 | review | Websocket token expiry semantics inconsistent |
| canonical-filetype-023 | review | Double-extension upload, backend-dependent serving |
| canonical-cachehdr-024 | review | Rare cross-account cached response, mechanism unconfirmed |

## Design rationale

- The **review** class gained the most because it is where evaluator discrimination
  is hardest and most informative: these fixtures require deferring judgment rather
  than pattern-matching to a verdict.
- New **valid** fixtures extend coverage into control families absent from v0.1
  (credential transport, mass assignment, GraphQL authorization, CSV export,
  webhook authenticity).
- The **invalid** class was left untouched: it is already the largest and its
  presentation-pair structure is load-bearing for susceptibility measurement.

## Safety verification

All twelve additions are fully synthetic, set in fictional demo applications,
reference only reserved namespaces (`example.*`, loopback), contain inert payloads,
and carry per-fixture sanitization notes. `sloplab validate corpus/` enforces these
properties mechanically.
