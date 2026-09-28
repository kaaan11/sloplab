# Dataset exposure register

This register distinguishes public source ancestry from when a specific input
became public. A public benchmark is **not** an unseen test set. Dates below are
the first repository publication found with `git log --reverse -- <path>`;
later edits and repackaging do not reset exposure.

| Material | First public date | Labels/answers public? | Authoring and ancestry | Measurement status |
|---|---|---|---|---|
| 60 canonical fixtures in `corpus/canonical/` | 2026-08-25, beginning at `18c52d9` | Yes: class and numeric targets in adjacent manifests | Fully synthetic, model assisted by Codex and/or Muse Spark; no per-fixture attribution | Public development corpus; possible training exposure is unknown |
| Derived `v1-core` variants and reference decisions in `benchmarks/results/v1-core-example/` | 2026-08-25, beginning at `f98107e` | Yes: mutation manifests and run records | Generated from public canonicals; current 237-case population was regenerated later | Public development corpus, not held out |
| Three `cards/v0.1/` annotator inputs | 2026-09-27, beginning at `70b32cc` | Answer keys added 2026-09-28 at `c534002`; owner judgments were committed first | Fully synthetic, Anthropic Claude authored; no existing fixture ancestry | Public examples; exclude Anthropic, OpenAI and Meta from a future model panel as recorded in card provenance |
| Canonical OpenRouter pilot records | 2026-09-28, PR #77 | Yes: normalized decisions and authored targets | Same public canonical inputs | Descriptive run only; 59/60 cases with valid responses, not an independent accuracy estimate |
| Nine fresh private card inputs, c04–c12 | Not published; created locally 2026-09-28 | No: author key sealed outside Git; owner judgment pending | OpenAI-authored, fully synthetic, no copied fixture text; source SHA-256 `2348100781dc3dca5dabd877fd236fb0a600cad8b253044b085fb58778e35feb` | Access-controlled candidate set under ignored `heldout-private/`; no model dispatch yet |

## Exposure policy for new evaluation inputs

1. Generate fresh, fully synthetic scenarios without copying a public fixture or
   its mutation text. Record authoring family, date, source ancestry and content
   hash before any model dispatch.
2. Keep raw inputs and the sealed answer key outside tracked repository paths.
   Commit only a count, protocol version, hashes and aggregate results after
   adjudication. The private path is ignored by Git.
3. Give the owner only the neutral `input.md` view and an empty judgment
   template. Record the owner's judgment **before** model votes or the sealed
   key are opened. Preserve disagreements rather than overwriting either vote.
4. Exclude each input's authoring family and the corpus-authoring families
   (OpenAI, Meta, Anthropic) from the panel. Use at least three distinct
   remaining model families, with resolved model identifiers and request
   settings recorded. Never assume a provider's family from its display name.
5. Treat any release of raw inputs, public answer keys, prompt logs or
   aggregate per-case labels as the end of that set's future held-out status.
   A later evaluation needs newly authored inputs. Sending inputs to a model
   provider is a controlled exposure and must be recorded even if the
   repository remains private.

No held-out model accuracy claim exists yet. The [canonical LLM
study](llm-pilot-canonical-coverage-2026-09-28.md) used the public corpus and
does not satisfy this protocol.
