"""Versioned analysis publication bound to verified metrics (E4b-r1).

A versioned analysis (``analysis-vN.json``) is inseparable from its inputs:
it embeds the analysis definition version, the SHA-256 of the exact source
records file, the outcomes source binding (presence, path, hash, lines),
and the selection/outcome coverage snapshot. Readers re-derive the
evaluator set, scored/failed counts, case identities, collisions, and the
planned union from the bound rows, and re-verify every embedded E4a metric
bundle by recomputation. Stale caches, mixed analyses, coverage mismatches,
and unknown definition versions are refused. Historical ``analysis.json``
files are never overwritten; the versioned document is a separate file. No
scientific preference beyond the descriptive case-weighted contract is
stated here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sloplab.path_boundary import PathBoundaryError, resolve_within_root

#: Envelope version of the versioned analysis document itself. Version 2
#: adds the outcomes binding and the planned/not_run selection coverage;
#: schema-1 documents are refused (recompute, do not reuse).
ANALYSIS_SCHEMA_VERSION = 2

#: Definition version: metrics set, formulas, and eligibility rules covered.
#: Bump when any of those change; readers accept only the current version
#: and direct anything else to recomputation (no silent cross-version reads).
ANALYSIS_DEFINITION_VERSION = 1


def operator_metric_eligibility() -> dict[str, dict[str, object]]:
    """Measurement eligibility per registered mutation operator (E4b).

    Derived from operator metadata, never hand-listed per operator: every
    registered operator appears exactly once, so newly added operators
    cannot silently fall out of the table. ``degrading_capable`` reads the
    operator spec (non-empty ``decision_by_parent_class``);
    ``presentation`` reads the shared presentation set. Drift eligibility
    stays per-case (a neutral edit of any operator), never per-operator.
    The ``invariance`` note states what unchanged decisions do and do not
    mean; decision invariance is never interpreted as quality neutrality.
    """
    from sloplab.mutations.base import get_operator, list_operators
    from sloplab.scoring.metrics import PRESENTATION_OPERATORS

    table: dict[str, dict[str, object]] = {}
    for name in sorted(list_operators()):
        spec = get_operator(name).spec
        degrading = bool(spec.decision_by_parent_class)
        presentation = name in PRESENTATION_OPERATORS
        if presentation:
            invariance = (
                "acceptance gain on still-broken content is susceptibility signal; "
                "unchanged decisions prove nothing about quality"
            )
        elif degrading:
            invariance = (
                "unchanged decisions on degrading edits are detection misses, "
                "not robustness evidence"
            )
        else:
            invariance = (
                "no expectation change by spec; drift near zero is stability "
                "signal only, never quality approval"
            )
        table[name] = {
            "category": str(spec.category),
            "degrading_capable": degrading,
            "presentation": presentation,
            "detection_eligible": degrading,
            "susceptibility_eligible": presentation,
            "drift_pair_context": "parent row required in the same input; else unresolved",
            "invariance": invariance,
        }
    return table


class AnalysisError(ValueError):
    """A versioned analysis cannot be trusted for the requested use."""


def analysis_filename(version: int = ANALYSIS_DEFINITION_VERSION) -> str:
    """Separate name for the versioned publication (never ``analysis.json``)."""
    return f"analysis-v{version}.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_versioned_analysis(
    out_dir: Path,
    *,
    records_path: Path,
    bundles: dict[str, Any],
    coverage: dict[str, Any],
    kind: str = "study",
    outcomes_path: Path | None = None,
) -> Path:
    """Publish a versioned analysis bound to exact records + outcomes sources.

    ``bundles`` maps evaluator name to a JSON-ready metric bundle dict (as
    produced by ``metrics_to_dict``); ``coverage`` maps evaluator name to
    ``{"planned", "scored", "failed", "not_run"}``. The outcomes source
    binding records presence (or explicit absence), path, hash, and line
    count. Every evaluator entry must satisfy
    ``scored + failed + not_run == planned`` or publication itself fails:
    the envelope can never be born inconsistent. The document records the
    records bytes hash, so any later change to either source file
    invalidates this publication.
    """
    if kind not in ("study",):
        raise AnalysisError(f"unknown analysis kind {kind!r}")
    for name, entry in coverage.items():
        if not isinstance(entry, dict):
            raise AnalysisError(f"coverage for {name!r} is malformed")
        try:
            planned = int(entry["planned"])
            scored = int(entry["scored"])
            failed = int(entry["failed"])
            not_run = int(entry["not_run"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AnalysisError(f"coverage for {name!r} is malformed: {exc}") from exc
        if scored + failed + not_run != planned:
            raise AnalysisError(
                f"coverage for {name!r} does not reconcile "
                f"({scored}+{failed}+{not_run} != {planned})"
            )
    if set(coverage) != set(bundles):
        raise AnalysisError("coverage evaluator set differs from bundles set")
    target = out_dir / analysis_filename()
    if not records_path.is_file():
        raise AnalysisError(f"records file missing: {records_path}")
    if outcomes_path is not None and outcomes_path.is_file():
        outcomes_binding: dict[str, Any] = {
            "present": True,
            "path": outcomes_path.name,
            "sha256": _sha256_file(outcomes_path),
            "lines": sum(
                1 for line in outcomes_path.read_text(encoding="utf-8").splitlines() if line.strip()
            ),
        }
    else:
        outcomes_binding = {"present": False, "path": None, "sha256": None, "lines": 0}
    document = {
        "analysis_schema": ANALYSIS_SCHEMA_VERSION,
        "analysis_version": ANALYSIS_DEFINITION_VERSION,
        "kind": kind,
        "records_path": records_path.name,
        "records_sha256": _sha256_file(records_path),
        "records_count": sum(
            1 for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ),
        "outcomes": outcomes_binding,
        "evaluators": sorted(bundles),
        "coverage": {name: coverage[name] for name in sorted(coverage)},
        "bundles": {name: bundles[name] for name in sorted(bundles)},
        "note": (
            "descriptive case-weighted metrics; no estimand, weighting, or "
            "interval claim beyond docs/metric-contracts.md"
        ),
    }
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _read_json_rows(path: Path, *, purpose: str) -> list[dict[str, Any]]:
    """Parse a JSONL source file into row dicts (rejects malformed rows)."""
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"{path}:{lineno}: unparsable {purpose} row: {exc}") from exc
        if not isinstance(payload, dict):
            raise AnalysisError(f"{path}:{lineno}: malformed {purpose} row (not an object)")
        rows.append(payload)
    return rows


def read_versioned_analysis(analysis_path: Path) -> dict[str, Any]:
    """Read a versioned analysis through the integrity boundary.

    Requires the enclosing bundle directory to verify as complete, then
    re-derives everything from the bound sources: the records and outcomes
    rows yield the evaluator set, scored/failed counts, case identities,
    collisions/singularity, and the planned union (checked against the
    bundle's suite index); every embedded E4a metric bundle is recomputed
    from the bound records with the current definition and must match
    exactly. Stale caches, mixed sources, coverage mismatches, and unknown
    versions raise :class:`AnalysisError`.
    """
    from sloplab.experiments.bundle import open_result_dir

    try:
        document = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"{analysis_path}: unreadable versioned analysis: {exc}") from exc
    if not isinstance(document, dict):
        raise AnalysisError(f"{analysis_path}: versioned analysis is not an object")
    if document.get("analysis_schema") != ANALYSIS_SCHEMA_VERSION:
        raise AnalysisError(
            f"{analysis_path}: unsupported analysis_schema {document.get('analysis_schema')!r}; "
            "recompute, do not reuse"
        )
    if document.get("analysis_version") != ANALYSIS_DEFINITION_VERSION:
        raise AnalysisError(
            f"{analysis_path}: analysis version {document.get('analysis_version')!r} "
            f"is not current ({ANALYSIS_DEFINITION_VERSION}); recompute, do not reuse"
        )
    evaluators = document.get("evaluators")
    if (
        not isinstance(evaluators, list)
        or not evaluators
        or any(not isinstance(name, str) or not name for name in evaluators)
        or evaluators != sorted(set(evaluators))
    ):
        raise AnalysisError(
            f"{analysis_path}: evaluators must be a sorted, unique, non-empty string list"
        )
    bundle_dir = analysis_path.parent
    try:
        mode = open_result_dir(bundle_dir, purpose="versioned analysis")
    except ValueError as exc:
        raise AnalysisError(str(exc)) from exc
    if mode != "complete":
        raise AnalysisError(f"{bundle_dir}: versioned analysis requires a complete bundle")

    records_name = document.get("records_path")
    if not isinstance(records_name, str) or not records_name:
        raise AnalysisError(f"{analysis_path}: bound records path is malformed")
    try:
        records_path = resolve_within_root(
            bundle_dir, records_name, label="analysis records_path"
        )
    except PathBoundaryError as exc:
        raise AnalysisError(f"{analysis_path}: {exc}") from exc
    if not records_path.is_file():
        raise AnalysisError(f"{analysis_path}: bound records file {records_name!r} missing")
    if _sha256_file(records_path) != document.get("records_sha256"):
        raise AnalysisError(
            f"{analysis_path}: records hash mismatch (stale cache or mixed records)"
        )
    record_rows = _read_json_rows(records_path, purpose="records")
    if len(record_rows) != document.get("records_count"):
        raise AnalysisError(f"{analysis_path}: records count mismatch (stale cache)")

    outcomes_binding = document.get("outcomes")
    if not isinstance(outcomes_binding, dict) or "present" not in outcomes_binding:
        raise AnalysisError(f"{analysis_path}: outcomes binding malformed")
    outcomes_path: Path | None = None
    if outcomes_binding["present"]:
        outcomes_name = outcomes_binding.get("path")
        if not isinstance(outcomes_name, str) or not outcomes_name:
            raise AnalysisError(f"{analysis_path}: bound outcomes path is malformed")
        try:
            outcomes_path = resolve_within_root(
                bundle_dir, outcomes_name, label="analysis outcomes path"
            )
        except PathBoundaryError as exc:
            raise AnalysisError(f"{analysis_path}: {exc}") from exc
        if not outcomes_path.is_file():
            raise AnalysisError(f"{analysis_path}: bound outcomes file missing")
        if _sha256_file(outcomes_path) != outcomes_binding.get("sha256"):
            raise AnalysisError(f"{analysis_path}: outcomes hash mismatch (stale cache)")
        outcome_rows = _read_json_rows(outcomes_path, purpose="outcomes")
        if len(outcome_rows) != outcomes_binding.get("lines"):
            raise AnalysisError(f"{analysis_path}: outcomes line count mismatch")
    else:
        planted = bundle_dir / "outcomes.jsonl"
        if planted.is_file():
            raise AnalysisError(f"{analysis_path}: unbound outcomes file present (mixed bundle)")
        outcome_rows = []
    for row in outcome_rows:
        if row.get("status") != "failed":
            raise AnalysisError(
                f"{analysis_path}: study outcomes rows must be failed (found {row.get('status')!r})"
            )

    _verify_accounting(analysis_path, document, record_rows, outcome_rows)
    _verify_recomputed_bundles(analysis_path, document, records_path)
    return document


def _verify_accounting(
    analysis_path: Path,
    document: dict[str, Any],
    record_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
) -> None:
    """Re-derive evaluator set, counts, identities, and planned union."""
    from sloplab.scoring.harness import read_suite_index

    scored: dict[str, list[str]] = {}
    for row in record_rows:
        name = row.get("evaluator_name")
        case_id = row.get("case_id")
        if not isinstance(name, str) or not isinstance(case_id, str):
            raise AnalysisError(f"{analysis_path}: records row lacks evaluator/case identity")
        scored.setdefault(name, []).append(case_id)
    failed: dict[str, list[str]] = {}
    for row in outcome_rows:
        name = row.get("evaluator_name")
        case_id = row.get("case_id")
        if not isinstance(name, str) or not isinstance(case_id, str):
            raise AnalysisError(f"{analysis_path}: outcomes row lacks evaluator/case identity")
        failed.setdefault(name, []).append(case_id)

    embedded_evaluators = document.get("evaluators")
    embedded_coverage = document.get("coverage")
    if not isinstance(embedded_coverage, dict):
        raise AnalysisError(f"{analysis_path}: coverage block malformed")
    if set(scored) | set(failed) != set(embedded_coverage) or (
        isinstance(embedded_evaluators, list) and set(embedded_evaluators) != set(embedded_coverage)
    ):
        raise AnalysisError(f"{analysis_path}: evaluator set mismatch (coverage)")
    for name, entry in embedded_coverage.items():
        if not isinstance(entry, dict):
            raise AnalysisError(f"{analysis_path}: coverage for {name!r} malformed")
        for key in ("planned", "scored", "failed", "not_run"):
            if entry.get(key) is None:
                raise AnalysisError(f"{analysis_path}: coverage for {name!r} lacks {key}")
        if entry["not_run"] != 0:
            raise AnalysisError(
                f"{analysis_path}: study path has no not_run (found {entry['not_run']})"
            )
        if entry["scored"] != len(scored.get(name, [])):
            raise AnalysisError(f"{analysis_path}: coverage mismatch (scored) for {name!r}")
        if entry["failed"] != len(failed.get(name, [])):
            raise AnalysisError(f"{analysis_path}: coverage mismatch (failed) for {name!r}")
        if entry["scored"] + entry["failed"] + entry["not_run"] != entry["planned"]:
            raise AnalysisError(f"{analysis_path}: planned equation broken for {name!r}")

    # Singularity within each source plus success/failed collision across them.
    for name, case_ids in scored.items():
        if len(set(case_ids)) != len(case_ids):
            raise AnalysisError(f"{analysis_path}: duplicate records case for {name!r}")
    for name, case_ids in failed.items():
        if len(set(case_ids)) != len(case_ids):
            raise AnalysisError(f"{analysis_path}: duplicate outcomes case for {name!r}")
    for name in set(scored) & set(failed):
        collision = set(scored[name]) & set(failed[name])
        if collision:
            raise AnalysisError(
                f"{analysis_path}: case scored and failed for {name!r}: {sorted(collision)[:3]}"
            )

    # Planned union: per evaluator, records + failed case identities must
    # equal the bundle's suite index (selection coverage, re-derived).
    index_path = analysis_path.parent / "suite-index.jsonl"
    if not index_path.is_file():
        raise AnalysisError(f"{analysis_path}: suite index missing for planned check")
    _, entries = read_suite_index(index_path)
    planned_cases = sorted(
        entry["case_id"] for entry in entries if isinstance(entry.get("case_id"), str)
    )
    if not planned_cases:
        raise AnalysisError(f"{analysis_path}: suite index carries no cases")
    for name in embedded_coverage:
        union = sorted(set(scored.get(name, [])) | set(failed.get(name, [])))
        if union != planned_cases:
            raise AnalysisError(
                f"{analysis_path}: planned union mismatch for {name!r} "
                f"(rows {len(union)}, index {len(planned_cases)})"
            )
        if embedded_coverage[name]["planned"] != len(planned_cases):
            raise AnalysisError(f"{analysis_path}: planned count mismatch for {name!r}")


def _verify_recomputed_bundles(
    analysis_path: Path, document: dict[str, Any], records_path: Path
) -> None:
    """Recompute every embedded E4a metric bundle from the bound records.

    Uses the current definition; any embedded value (accuracy,
    susceptibility, ECE, coverage) that no longer matches is refused, so a
    tampered metric cannot hide behind a valid records hash — even with a
    freshly regenerated completion marker.
    """
    from sloplab.reporting.writers import metrics_to_dict, read_run_jsonl
    from sloplab.scoring.metrics import compute_metrics

    _, records = read_run_jsonl(records_path)
    by_evaluator: dict[str, list[Any]] = {}
    for record in records:
        by_evaluator.setdefault(record.evaluator_name, []).append(record)
    embedded_bundles = document.get("bundles")
    if not isinstance(embedded_bundles, dict):
        raise AnalysisError(f"{analysis_path}: bundles block malformed")
    for name in document.get("evaluators", []):
        expected = metrics_to_dict(compute_metrics(by_evaluator.get(name, []), name))
        actual = embedded_bundles.get(name)
        if actual != expected:
            raise AnalysisError(
                f"{analysis_path}: embedded metrics for {name!r} do not match "
                "recomputation from the bound records"
            )
    if set(embedded_bundles) != set(document.get("evaluators", [])):
        raise AnalysisError(f"{analysis_path}: bundles set mismatch")
