# SlopLab Report Builder

Report Builder is the optional, keyboard-first terminal presentation of the same
synthetic canonical-fixture creation API used by the classic Click wizard. It is
not a live triage evaluator, real-report importer, or hosted application.

## Install and start

From a repository checkout:

```bash
uv sync --extra ui
uv run sloplab add-report path/to/report.md --ui
# Existing custom corpus:
uv run sloplab add-report path/to/report.md --corpus path/to/corpus --ui
```

For a package installation, install `sloplab[ui]` (or `pip install -e '.[ui]'`
from the checkout). Without the extra, `--ui` prints those installation steps.
`sloplab add-report report.md` still uses the existing CLI without importing the
UI toolkit. Development installs include the toolkit so CI runs, rather than
skips, the headless UI tests.

This implementation uses **prompt_toolkit 3.0.52**, not Textual. Textual was the
preferred candidate in #11, but was unavailable in the implementation sandbox;
prompt_toolkit was locally available for actual keyboard/lifecycle testing. It is
an optional full-screen presentation dependency, not a domain dependency. The
core, schemas and transactions were not modified to accommodate this choice.
The lockfile adds only prompt-toolkit and its wcwidth dependency; existing package
versions stay unchanged.

Package installation can require internet access. The installed builder itself
uses no network, API keys, evaluator calls or subprocesses.

## Keyboard and terminal support

Use Tab / Shift-Tab for focus, arrow keys plus Space for choices, and Enter on a
focused button. F6 moves Back, F7 continues, F8 requests Create. Ctrl-Q or Ctrl-C
cancels a non-busy builder; after success it closes the result screen. The same
buttons are keyboard-focusable, so function keys are not required.

During a blocking core operation, navigation and repeat Create are disabled.
Cancel does not interrupt an in-flight filesystem operation: the UI explains that
it must finish first. The result can then be inspected and closed. If terminal
EOF or external asyncio cancellation arrives instead, shutdown drains the worker
and closes the preparation scope before returning. SIGKILL/power loss remain the
core's documented limitations; do not close the terminal during creation.

Minimum supported size is **70 columns by 20 rows**. Smaller terminals show an
explicit size warning and cannot advance/create; cancel remains available. Forms
scroll with focus, and Review/Success are scrollable read-only text. Set
`NO_COLOR=1` for monochrome output. Statuses use text (`[OK]`, `[!]`, `[--]`), never
color alone. Linux headless and real terminal rendering were checked; Windows
and macOS were not exercised in this delivery. No mouse is needed.

## Steps

**Source.** The existing `read_report` parser detects H1 and evidence headings.
The slug preview is validated by `build_manifest`; no parallel regex is used.
Continue checks collision/corpus status by a short-lived core preparation,
closed immediately. This early probe uses empty review annotations and is not
an approved plan; final preparation uses all of the user's annotations.

**Ground truth.** Select Valid / Accept, Invalid / Reject, or Manual Review /
Needs Manual Review. Set reproducibility, impact, rationale and sanitization
note. Unknown impact is distinct from `none`. These are human-authored targets,
not labels inferred by the UI.

**Evidence.** Requirements come from `EVIDENCE_SECTION_PATTERNS`; found/not-found
text comes from `ReportSource.evidence_keys`. Heading detection is structural,
not proof of correctness. Optional disallowed claims are entered one per line.

**Dimensions.** All five fields follow `DIMENSIONS`. Numeric inputs keep their
exact entered value (subject to the existing float-based schema); the visual
meter is only approximate. `GroundTruth` rejects nonfinite and out-of-range
scores. No UI-side replacement validation schema exists.

**Review.** Displays ID/title/class/expected decision/impact/destination,
`PreparedReport.fixture_validation`, `PreparedReport.preflight`, and the complete
manifest YAML. It does not decorate unperformed checks as passed. Create is only
available for an active prepared review. An initially unchecked confirmation
requires the user to attest synthetic content and authorize creation; entering
Review or pressing F8 without checking it never publishes a fixture.

**Success.** Displays actual result paths, before/after canonical counts and
full-corpus validation, including warnings, plus a benchmark command. Custom
corpora need a suite with a matching `corpus_root`. README/dataset-card counts and
reference results remain the author's responsibility, not automatic edits.

## Lifecycle and core reuse

`sloplab.tui.session.BuilderSession` only owns the existing context; it contains
no filesystem transaction, collision algorithm, validator or rollback. Its
`ExitStack` keeps one `prepare_add_report` scope alive across review events.
Back/edit, cancel, errors, shutdown and success all close that scope. A changed
form requires a new preparation and explicit confirmation.

`sloplab.tui.app.ReportBuilder` schedules source reads, preparation, commit and
scope closing on **one serial ThreadPoolExecutor worker**, not the event loop.
The application owns and joins its tasks. It does not rely on framework tasks
that are abandoned or cancelled when the view closes. See
[the core contract](add-report.md) for the underlying transaction guarantees.

```text
read_report -> build_manifest -> ExitStack.enter_context(prepare_add_report)
                                       |
                                real Review + approval
                                       |
                         commit_add_report(confirmed=True)
                                       |
                         close preparation / ExitStack
                                       |
                    read retained commit_result + warnings
                                       |
                                Success + next steps
```

Successful commit and incomplete resource cleanup are different states. The
session reads `PreparedReport.commit_result` **after scope exit**, preserving the
same `AddReportResult` object. Lock/stage cleanup OSError or KeyboardInterrupt
therefore shows **Fixture added + Cleanup incomplete**, not Creation failed.
Warnings include paths and the core's explanation. Do not retry creation to fix
cleanup; inspect remaining resources and verify no writer is active before
removing any stale lock. The final result is also printed after leaving the
alternate screen so paths, warnings and next commands remain in scrollback.

Before verified commit, failures show actual core error text, validation output
and exception notes, not a traceback or fabricated success. A failed/expired
review cannot be reused. The original identity-checked rollback remains entirely
in the core. UI callback failure also closes any live preparation on shutdown;
a verified result is not lost merely because the view could not render it.

## Validation and non-goals

Tests use real prompt_toolkit pipe input and the real core against temporary
corpora: keyboard-only creation, form navigation, equivalence to CLI, collisions,
source/manifest validation, stale snapshots, post-write rollback, optional import
failure, no-network/no-subprocess operation, cleanup faults and interrupted UI
shutdown. No committed corpus fixtures or reference runs are modified.

There is no `sloplab tui` dashboard, Results Explorer, Mutation Lab, file editor,
cloud account, collaboration, web service, live evaluation UI or real-report
import. This release is only the Report Builder.
