"""Benchmark harness: run evaluators over a materialized suite index.

The harness is the ONLY component that reads ground-truth labels from manifests and
passes them to evaluators via ``EvaluationContext.labels``. Content-based evaluators
must ignore labels; the oracle consumes them.

Identity hygiene (v0.2.2, R04): evaluators never see case identifiers or report
paths that encode mutation identity. Each evaluation receives an opaque,
deterministic handle (``case-<sha256[:16]>``) as ``context.case_id`` and as the
report's ``fixture_id``/``path``. The true case identifier is restored when the
result is recorded into benchmark provenance (``CaseRecord``), so records remain
fully traceable while evaluator-visible input stays identity-free.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sloplab.corpus.loader import (
    CanonicalFixture,
    FixtureError,
    discover_fixtures,
    load_derived_fixture,
)
from sloplab.evaluators.base import Evaluator, evaluator_requires_labels
from sloplab.evaluators.llm.failures import EvaluationFailure, raise_if_failed_result
from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationContext
from sloplab.models.report import ReportDocument
from sloplab.models.run import CaseRecord
from sloplab.path_boundary import PathBoundaryError, resolve_within_root


def opaque_case_handle(case_id: str) -> str:
    """Opaque, deterministic handle that hides mutation identity."""
    return "case-" + hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SuiteCase:
    case_id: str
    kind: str  # canonical | mutated
    parent_id: str | None
    operator: str | None
    report_class: str
    expected_decision: str | None
    expected_dimensions: dict[str, float]
    seed: int | None
    fixture_dir: Path | None  # mutated cases only
    canonical_fixture: CanonicalFixture | None = None
    # Frozen run input (E1b): the loaded report held for the whole run, so later
    # disk changes or deletions cannot alter what evaluators see. build_cases
    # always fills this; direct constructors predating the field leave it None
    # and fall back to legacy loading (documented below, no snapshot guarantee).
    report: ReportDocument | None = None


def case_document(case: SuiteCase) -> ReportDocument:
    """Return the run input report for ``case``.

    Prefers the snapshot stored by :func:`build_cases`. The legacy fallback
    (canonical fixture object, then disk reload) exists only for directly
    constructed cases without a snapshot and carries no snapshot guarantee;
    the build_cases path never reaches it.
    """
    if case.report is not None:
        return case.report
    if case.kind == "canonical" and case.canonical_fixture is not None:
        return case.canonical_fixture.report
    if case.fixture_dir is not None:
        return load_derived_fixture(case.fixture_dir, case.fixture_dir.parents[2]).report
    raise ValueError(f"case {case.case_id} is not loadable")


def read_suite_index(index_path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return ``(header, case_entries)`` from a suite index file."""
    header: dict[str, Any] | None = None
    entries: list[dict[str, Any]] = []
    for raw in index_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        line = json.loads(raw)
        record_type = line.get("record_type")
        if record_type == "suite_header":
            header = line
        elif record_type == "suite_case":
            entries.append(line)
        else:
            raise ValueError(f"{index_path}: unexpected record_type {record_type!r}")
    if not entries:
        raise ValueError(f"{index_path}: suite index contains no cases")
    return header, entries


def build_cases(index_path: Path, corpus_root: Path, materialized_root: Path) -> list[SuiteCase]:
    """Resolve suite-index entries into loadable cases."""
    _header, entries = read_suite_index(index_path)
    canonical, _derived = discover_fixtures(corpus_root)
    canonical_by_id = {canon.fixture_id: canon for canon in canonical}

    cases: list[SuiteCase] = []
    for entry in entries:
        if entry["kind"] == "canonical":
            canon = canonical_by_id.get(entry["case_id"])
            if canon is None:
                raise FixtureError(
                    f"suite index references unknown canonical fixture '{entry['case_id']}'"
                )
            gt = canon.manifest.ground_truth
            cases.append(
                SuiteCase(
                    case_id=canon.fixture_id,
                    kind="canonical",
                    parent_id=None,
                    operator=None,
                    report_class=canon.manifest.report_class.value,
                    expected_decision=canon.manifest.expected_decision().value,
                    expected_dimensions=dict(gt.expected_dimensions),
                    seed=None,
                    fixture_dir=None,
                    canonical_fixture=canon,
                    report=canon.report,
                )
            )
        else:
            manifest_rel = entry.get("manifest_path")
            if not isinstance(manifest_rel, str) or not manifest_rel:
                raise ValueError(f"suite index entry '{entry['case_id']}' has no manifest_path")
            try:
                manifest_path = resolve_within_root(
                    materialized_root, manifest_rel, label="suite manifest_path"
                )
            except PathBoundaryError as exc:
                raise FixtureError(f"suite index entry '{entry['case_id']}': {exc}") from exc
            case_dir = manifest_path.parent
            derived = load_derived_fixture(case_dir, materialized_root)
            manifest = derived.manifest
            cases.append(
                SuiteCase(
                    case_id=manifest.id,
                    kind="mutated",
                    parent_id=manifest.parent_id,
                    operator=manifest.operator,
                    report_class=entry["report_class"],
                    expected_decision=manifest.expected_decision.value,
                    expected_dimensions=dict(manifest.expected_dimensions),
                    seed=manifest.seed,
                    fixture_dir=case_dir,
                    report=derived.report,
                )
            )
    cases.sort(key=lambda c: c.case_id)
    return cases


def run_case(evaluator: Evaluator, case: SuiteCase) -> CaseRecord:
    """Evaluate one case with one evaluator and normalize into a record.

    The evaluator-visible report and case handle carry no mutation identity
    (R04); the true case identifier is restored on the returned record.
    The report comes from the case snapshot, never from a run-time disk reload.
    Ground-truth labels are handed out only to evaluators declaring the
    ``requires_labels`` capability; everyone else sees an empty mapping (each
    call gets a fresh copy, so label mutation cannot leak across evaluators).
    A legacy failed placeholder is rejected at this boundary instead of
    becoming a success record.
    """
    document = case_document(case)

    handle = opaque_case_handle(case.case_id)
    sanitized_document = document.model_copy(update={"fixture_id": handle, "path": handle})

    labels: dict[str, Any] = {}
    if evaluator_requires_labels(evaluator):
        labels = {
            "expected_decision": case.expected_decision,
            "expected_dimensions": dict(case.expected_dimensions),
        }
    context = EvaluationContext(report=sanitized_document, case_id=handle, labels=labels)
    result = raise_if_failed_result(evaluator.evaluate(sanitized_document, context))

    expected = Decision(case.expected_decision) if case.expected_decision else None
    return CaseRecord.from_result(
        result,
        case_id=case.case_id,
        case_kind="mutated" if case.kind == "mutated" else "canonical",
        report_class=case.report_class,
        expected_decision=expected,
        parent_id=case.parent_id,
        operator=case.operator,
        expected_dimensions=dict(case.expected_dimensions),
        seed=case.seed,
    )


def run_suite(evaluator: Evaluator, cases: list[SuiteCase]) -> list[CaseRecord]:
    return [run_case(evaluator, case) for case in cases]


@dataclass(frozen=True)
class CaseOutcome:
    """One case evaluation isolated at the shared study coordination boundary.

    ``status`` is ``"success"`` with a scored ``record``, or ``"failed"``
    with the expected operational ``failure`` and no record: a failed case
    never becomes an invented decision. Unexpected program/config errors are
    never captured here — they propagate.
    """

    case_id: str
    evaluator_name: str
    status: str  # success | failed
    record: CaseRecord | None = None
    failure: EvaluationFailure | None = None


def _evaluator_name(evaluator: Evaluator) -> str:
    name = getattr(evaluator, "name", None)
    return name if isinstance(name, str) and name else type(evaluator).__name__


def run_case_outcome(evaluator: Evaluator, case: SuiteCase) -> CaseOutcome:
    """Evaluate one case, isolating expected operational failures as outcomes."""
    try:
        record = run_case(evaluator, case)
    except EvaluationFailure as exc:
        return CaseOutcome(
            case_id=case.case_id,
            evaluator_name=_evaluator_name(evaluator),
            status="failed",
            record=None,
            failure=exc,
        )
    return CaseOutcome(
        case_id=case.case_id,
        evaluator_name=_evaluator_name(evaluator),
        status="success",
        record=record,
        failure=None,
    )


def run_suite_with_outcomes(
    evaluator: Evaluator, cases: list[SuiteCase]
) -> tuple[list[CaseRecord], list[CaseOutcome]]:
    """Evaluate all cases; expected failures surface as outcomes, not crashes.

    Returns ``(records, failed_outcomes)`` with
    ``len(records) + len(failed_outcomes) == len(cases)``. Only the typed
    operational :class:`EvaluationFailure` is isolated; any other exception
    (config/programming errors) propagates unwrapped.
    """
    records: list[CaseRecord] = []
    failed: list[CaseOutcome] = []
    for case in cases:
        outcome = run_case_outcome(evaluator, case)
        if outcome.status == "success":
            assert outcome.record is not None
            records.append(outcome.record)
        else:
            failed.append(outcome)
    return records, failed
