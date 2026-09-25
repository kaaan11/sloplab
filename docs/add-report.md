# Adding a synthetic canonical report

From a repository checkout, run:

```bash
sloplab add-report path/to/report.md
# An existing custom corpus root is also supported:
sloplab add-report path/to/report.md --corpus path/to/corpus
```

This is a local/offline **annotation and creation** workflow, not an import or
sanitization service for real bug-bounty reports. It neither calls an evaluator
nor submits reports anywhere. The only generated files in the final fixture are
`report.md` and `manifest.yaml`. No new dependencies are required.

## Walkthrough

1. The source must be a readable UTF-8 regular file with an ATX H1 (`# Title`)
   outside a code fence. SlopLab's existing parser detects the title and evidence
   headings; its existing manifest schema validates the title and fixture slug.
2. Enter a slug such as `authz-033`, **not** a full canonical ID. The generated
   ID is `canonical-authz-033` and the destination is
   `corpus/canonical/authz-033/`. Invalid slugs are re-prompted, not silently
   renamed or normalized.
3. Select `valid` (accept as written), `invalid` (reject as written), or `review`
   (genuinely unresolved; needs manual review). Select reproducibility and impact;
   `unknown` means a null ground-truth value, distinct from impact `none`.
4. Select required evidence from the actual `EVIDENCE_SECTION_PATTERNS` keys.
   The prompt shows which headings the parser found. Detection is structural,
   **not** proof that an evidence claim is true. Enter disallowed claims one per
   line, then finish with an empty line.
5. Annotate the five `DIMENSIONS` with finite scores in [0, 1], followed by the
   rationale and sanitization note. These are human-authored targets, not inferred
   labels; a successful validator does not establish scientific ground truth.
6. Review the complete YAML, destination, expected decision, and actual full-corpus
   preflight results, including warnings. Confirmation defaults to **No**. Cancel,
   EOF, and Ctrl-C before publication do not add a fixture.
7. On success, inspect the final paths and validation summary. Run the full
   benchmark from the repository root:

   ```bash
   sloplab benchmark benchmarks/suites/v1-core.yaml \
     --evaluator rules-baseline --out benchmarks/results/new-report-run
   ```

   For a custom corpus, use a suite YAML whose `corpus_root` points to that corpus;
   the stock suite is not silently rewritten. Before committing an expanded
   corpus, update README/dataset-card counts and regenerate applicable reference
   results and their documentation. Documentation-consistency tests enforce this.
   The wizard does not edit those files automatically.

## Core API for the #11 TUI

Import from `sloplab.corpus.add_report`, never from the Click command:

```python
from pathlib import Path

from sloplab.corpus.add_report import (
    build_manifest,
    commit_add_report,
    prepare_add_report,
    read_report,
)
from sloplab.models.enums import DIMENSIONS, ReportClass
from sloplab.models.manifest import GroundTruth

source = read_report(Path("report.md"))
# These example annotations must be replaced with the user's actual judgments.
manifest = build_manifest(
    source,
    slug="authz-033",
    report_class=ReportClass.REVIEW,
    ground_truth=GroundTruth(
        reproducible=None,
        required_evidence=["reproduction_steps"],
        expected_dimensions={name: 0.5 for name in DIMENSIONS},
        rationale="Synthetic example; decisive evidence is unresolved.",
    ),
    sanitization_note="Fully synthetic example.",
)
with prepare_add_report(source, manifest, Path("corpus")) as prepared:
    # Display prepared.manifest_text, destination, fixture_validation and preflight.
    # Only after an explicit user action should the UI call:
    result = commit_add_report(prepared, confirmed=True)
```

The example's commit call represents the UI's confirmed action; do not place it
on automatic screen entry. Exiting the context without committing is cancellation.
A TUI can retain this context using `contextlib.ExitStack`, closing it on cancel,
edit/re-prepare, success, error, or application shutdown. Do not reuse an expired
prepared object. Blocking preparation/commit should run off the UI event loop;
keep the commit alive until it finishes rather than abandoning its worker thread.

- `read_report(path) -> ReportSource`: immutable source bytes, resolved path, title,
  detected evidence keys. No files written.
- `build_manifest(source, *, slug, report_class, ground_truth, sanitization_note)`:
  an existing `CanonicalManifest`, with nested schema validation reapplied. No
  parallel schemas; no files written.
- `manifest_yaml(manifest) -> str`: deterministic safe YAML, with optional nulls
  omitted (existing schema defaults restore them on load).
- `prepare_add_report(source, manifest, corpus_root)`: context manager yielding
  `PreparedReport`. Creates an external stage, loads it through
  `load_canonical_fixture`, invokes `validate_canonical_fixture` (including the
  existing safety policy), and calls `validate_corpus` with the existing canonical
  **and derived** fixtures plus the staged fixture. `prepared.manifest` is a fresh
  model on each access; changing a preview model cannot change the approved bytes.
- `commit_add_report(prepared, *, confirmed=False) -> AddReportResult`: rejects
  missing approval, stale corpus/source/stage snapshots and collisions; repeats
  preflight, publishes, rediscovers and validates the full corpus, and verifies
  that the new bytes match the stage and the existing tree is unchanged.
- `AddReportError`: expected, actionable error. Its optional `.validation` field
  carries the original `ValidationResult`; render actual issues rather than
  fabricating UI status checks. Schema creation by the caller may also raise
  Pydantic's `ValidationError` before preparation starts.

`AddReportResult` includes `fixture_id`, `destination`, `report_path`,
`manifest_path`, `before_count`, and the final `validation` (including real counts
and warnings). Show success **only after commit returns**. A changed input or
corpus requires a new preparation and a new user confirmation, not a blind retry.

## Transaction boundary and deliberate limitations

The corpus root must already exist and must not be a filesystem root. Its parent
must be writable for external staging and the lock. An absent `canonical/` is
created only after approval and removed on rollback if still owned and empty.
This write workflow refuses corpus symlinks, special files and existing
`report.path` references outside the corpus; read-only workflows are unchanged.

Preparation writes only an external sibling stage. Commit takes a sibling
`.CORPUSNAME.sloplab-add-report.lock` directory, checks the reviewed snapshots,
and creates a same-filesystem temporary wrapper. That wrapper carries the existing
suite-index discovery marker so incomplete scratch content is not discovered as
canonical data. It is removed before final validation.

Publication uses Linux `renameat2(RENAME_NOREPLACE)`, macOS
`renamex_np(RENAME_EXCL)`, or Windows' no-replace `os.rename`. There is deliberately
**no unsafe exists()+POSIX rename fallback**: an unavailable primitive or unsupported
filesystem fails closed. Even an empty destination created after the collision
check is never replaced. A cooperating second writer cannot commit concurrently;
a prepared plan becomes stale after another writer commits.

Ordinary exceptions and Ctrl-C during the operation clean temporary resources and
roll back only the newly published directory, checked by its pre-rename filesystem
identity. If rollback fails or ownership changes, the error explicitly reports
incomplete cleanup and the path to inspect; it does not delete unrelated data or
claim success. Existing fixtures and source bytes are never intentionally modified.

These are **not** power-loss durability or multi-process database guarantees.
SIGKILL, power loss, or a filesystem that becomes unwritable can leave scratch
state, a published fixture, and/or a lock. Do not auto-delete a stale-looking lock:
first verify that no writer is active, inspect the reported paths, and validate the
corpus. Directory timestamps/metadata are not restored. Other programs that edit
the corpus without honoring this lock must not run concurrently; their changes
are detected where possible, never reverted on their behalf. The atomic guarantee
is directory publication, not isolation from arbitrary concurrent readers/writers.

Single-report creation only: no presentation pairs, overwrite/edit mode, TUI,
web server, real-report ingestion, or live LLM evaluation. The existing safety
validator remains a namespace check, not a comprehensive private-data detector.
