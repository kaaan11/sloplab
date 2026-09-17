"""Versioned analysis publication bound to verified metrics (E4b).

A versioned analysis (``analysis-vN.json``) is inseparable from its inputs:
it embeds the analysis definition version, the SHA-256 of the exact source
records file, and the selection/outcome coverage snapshot. Readers refuse
stale caches (records changed after publication), mixed analyses (bound to
another records file), coverage mismatches, and unknown definition
versions. Historical ``analysis.json`` files are never overwritten; the
versioned document is a separate file. No scientific preference beyond the
descriptive case-weighted contract is stated here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

#: Envelope version of the versioned analysis document itself.
ANALYSIS_SCHEMA_VERSION = 1

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
) -> Path:
    """Publish a versioned analysis bound to an exact records file.

    ``bundles`` maps evaluator name to a JSON-ready metric bundle dict (as
    produced by ``metrics_to_dict``); ``coverage`` maps evaluator name to
    its scored/failed counts. The document records the records bytes hash,
    so any later change to the records file invalidates this publication.
    """
    if kind not in ("study",):
        raise AnalysisError(f"unknown analysis kind {kind!r}")
    target = out_dir / analysis_filename()
    if not records_path.is_file():
        raise AnalysisError(f"records file missing: {records_path}")
    document = {
        "analysis_schema": ANALYSIS_SCHEMA_VERSION,
        "analysis_version": ANALYSIS_DEFINITION_VERSION,
        "kind": kind,
        "records_path": records_path.name,
        "records_sha256": _sha256_file(records_path),
        "records_count": sum(
            1 for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ),
        "evaluators": sorted(bundles),
        "coverage": coverage,
        "bundles": {name: bundles[name] for name in sorted(bundles)},
        "note": (
            "descriptive case-weighted metrics; no estimand, weighting, or "
            "interval claim beyond docs/metric-contracts.md"
        ),
    }
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def read_versioned_analysis(analysis_path: Path) -> dict[str, Any]:
    """Read a versioned analysis through the integrity boundary.

    Requires the enclosing bundle directory to verify as complete, then
    enforces the binding: known envelope and definition versions, a present
    records file whose bytes hash matches, a matching row count, and
    per-evaluator scored counts consistent with the bound records. Stale
    caches, mixed analyses, and coverage mismatches raise
    :class:`AnalysisError`.
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
            f"{analysis_path}: unsupported analysis_schema {document.get('analysis_schema')!r}"
        )
    if document.get("analysis_version") != ANALYSIS_DEFINITION_VERSION:
        raise AnalysisError(
            f"{analysis_path}: analysis version {document.get('analysis_version')!r} "
            f"is not current ({ANALYSIS_DEFINITION_VERSION}); recompute, do not reuse"
        )
    bundle_dir = analysis_path.parent
    try:
        mode = open_result_dir(bundle_dir, purpose="versioned analysis")
    except ValueError as exc:
        raise AnalysisError(str(exc)) from exc
    if mode != "complete":
        raise AnalysisError(f"{bundle_dir}: versioned analysis requires a complete bundle")
    records_name = document.get("records_path")
    records_path = bundle_dir / records_name if isinstance(records_name, str) else None
    if records_path is None or not records_path.is_file():
        raise AnalysisError(f"{analysis_path}: bound records file {records_name!r} missing")
    if _sha256_file(records_path) != document.get("records_sha256"):
        raise AnalysisError(
            f"{analysis_path}: records hash mismatch (stale cache or mixed records)"
        )
    rows = [line for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != document.get("records_count"):
        raise AnalysisError(f"{analysis_path}: records count mismatch (stale cache)")
    scored: dict[str, int] = {}
    for line in rows:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"{records_path}: unparsable record row: {exc}") from exc
        name = payload.get("evaluator_name")
        if isinstance(name, str):
            scored[name] = scored.get(name, 0) + 1
    embedded = document.get("coverage", {})
    if not isinstance(embedded, dict):
        raise AnalysisError(f"{analysis_path}: coverage block malformed")
    for name, entry in embedded.items():
        if not isinstance(entry, dict) or entry.get("scored") != scored.get(name, 0):
            raise AnalysisError(f"{analysis_path}: coverage mismatch for evaluator {name!r}")
    if set(scored) != set(embedded):
        raise AnalysisError(f"{analysis_path}: evaluator set mismatch (coverage)")
    return document
