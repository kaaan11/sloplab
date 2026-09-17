"""Materialization: execute planned mutations and write derived fixture directories.

Every plan lands exactly once in the materialization ledger
(``materialization-ledger.jsonl``) as ``written``, ``no_op``, ``duplicate``,
``safety_blocked``, or ``error`` — a per-plan error never aborts the run, so
population loss stays visible instead of silent. Use
:func:`check_materialization` to reconcile planned/produced/selected counts.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sloplab import __version__
from sloplab.corpus.loader import CanonicalFixture
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.base import get_operator
from sloplab.mutations.planner import PlannedMutation, plan_suite
from sloplab.safety.policy import validate_content_safety

SUITE_INDEX_NAME = "suite-index.jsonl"  # re-exported from corpus.loader

#: Per-plan ledger written next to the suite index (deterministic plan order).
LEDGER_FILE_NAME = "materialization-ledger.jsonl"

#: The only materialization outcome states; every plan reaches exactly one.
MATERIALIZATION_STATUSES = ("written", "no_op", "duplicate", "safety_blocked", "error")


@dataclass(frozen=True)
class MaterializationOutcome:
    """One plan's ledger row: exactly one status per plan, stable detail text."""

    case_id: str
    operator_name: str
    status: str
    detail: str


@dataclass
class MaterializationResult:
    out_root: Path
    cases_written: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)
    safety_violations: list[str] = field(default_factory=list)
    outcomes: list[MaterializationOutcome] = field(default_factory=list)

    def summary(self) -> str:
        tallies = _tally_outcomes(self.outcomes)
        lines = [
            f"materialized {self.cases_written} derived cases into {self.out_root} "
            f"(planned {len(self.outcomes)}: "
            + ", ".join(f"{status} {tallies[status]}" for status in MATERIALIZATION_STATUSES)
            + ")",
        ]
        for case_id, reason in self.skipped:
            lines.append(f"  skipped {case_id}: {reason}")
        for violation in self.safety_violations:
            lines.append(f"  SAFETY: {violation}")
        return "\n".join(lines)


def _tally_outcomes(outcomes: list[MaterializationOutcome]) -> dict[str, int]:
    tallies = dict.fromkeys(MATERIALIZATION_STATUSES, 0)
    for outcome in outcomes:
        tallies[outcome.status] += 1
    return tallies


def _write_derived_case(
    plan: PlannedMutation,
    mutated_text: str,
    parameters: dict[str, Any],
    out_root: Path,
) -> Path:
    case_dir = out_root / "adversarial" / plan.parent_id.removeprefix("canonical-") / plan.case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    report_rel = f"adversarial/{plan.parent_id.removeprefix('canonical-')}/{plan.case_id}/report.md"
    (case_dir / "report.md").write_text(mutated_text, encoding="utf-8")

    manifest_data = {
        "schema_version": 1,
        "id": plan.case_id,
        "parent_id": plan.parent_id,
        "operator": plan.operator_name,
        "category": plan.spec.category.value,
        "parameters": {"choices": parameters},
        "seed": plan.seed,
        "variant_index": plan.variant_index,
        "base_seed": plan.base_seed,
        "expected_decision": plan.expected_decision.value,
        "expected_effect": {
            "report_validity": plan.expected_effect.report_validity,
            "claim_quality": plan.expected_effect.claim_quality,
            "presentation_strength": plan.expected_effect.presentation_strength,
        },
        "expected_dimensions": plan.expected_dimensions,
        "generator_version": __version__,
        "report": {"path": report_rel},
    }
    (case_dir / "mutation-manifest.yaml").write_text(
        yaml.safe_dump(manifest_data, sort_keys=False), encoding="utf-8"
    )
    return case_dir


def _index_line(plan: PlannedMutation, case_dir: Path) -> dict[str, Any]:
    return {
        "record_type": "suite_case",
        "case_id": plan.case_id,
        "kind": "mutated",
        "parent_id": plan.parent_id,
        "operator": plan.operator_name,
        "expected_decision": plan.expected_decision.value,
        "report_class": plan.parent.manifest.report_class.value,
        # path relative to the materialization output root (parents[2] == out_root)
        "manifest_path": str(
            (case_dir / "mutation-manifest.yaml").relative_to(case_dir.parents[2])
        ),
    }


def materialize_suite(
    config: SuiteConfig,
    fixtures: list[CanonicalFixture],
    out_root: Path,
    *,
    corpus_root_resolved: Path | None = None,
) -> MaterializationResult:
    """Apply every planned mutation and write derived cases under ``out_root``.

    ``corpus_root_resolved`` overrides the corpus-root string recorded in the
    suite-index header (pass the absolute path used during discovery so later
    evaluation stages can relocate fixtures regardless of working directory).
    """
    result = MaterializationResult(out_root=out_root)
    plans, _group_counts = plan_suite(config, fixtures)
    header_corpus_root = str(corpus_root_resolved or config.corpus_root)

    # R01 (v0.2.2): every plan may now be skipped (no-op/clone guard), so the
    # output root can no longer rely on case writes to create directories.
    out_root.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    index_lines: list[dict[str, Any]] = []

    def _record(case_id: str, operator_name: str, status: str, detail: str) -> None:
        result.outcomes.append(
            MaterializationOutcome(
                case_id=case_id, operator_name=operator_name, status=status, detail=detail
            )
        )

    for plan in plans:
        if plan.case_id in seen_ids:
            result.skipped.append((plan.case_id, "duplicate case id"))
            _record(plan.case_id, plan.operator_name, "duplicate", "duplicate case id")
            continue
        try:
            stage = "resolve-operator"
            operator = get_operator(plan.operator_name)
            stage = "apply"
            rng = random.Random(plan.seed)
            mutated_text, parameters = operator.apply(plan.parent.report, rng)
            stage = "inspect"
            note = parameters.get("note") if isinstance(parameters, dict) else None
            if isinstance(note, str):
                result.skipped.append((plan.case_id, note))
                _record(plan.case_id, plan.operator_name, "no_op", note)
                continue
            if mutated_text == plan.parent.report.raw_text:
                # R01 (v0.2.2): a derived case must always differ from its parent;
                # never write an unmutated clone into the benchmark population.
                result.skipped.append((plan.case_id, "no textual change"))
                _record(plan.case_id, plan.operator_name, "no_op", "no textual change")
                continue
            stage = "safety-check"
            violations = validate_content_safety(mutated_text)
            if violations:
                result.safety_violations.extend(f"{plan.case_id}: {v}" for v in violations)
                # Ledger detail stays stable and minimal: matched text from the
                # violations never lands in a stored artifact.
                _record(
                    plan.case_id,
                    plan.operator_name,
                    "safety_blocked",
                    f"{len(violations)} violation(s) blocked",
                )
                continue
            stage = "write"
            case_dir = _write_derived_case(plan, mutated_text, parameters, out_root)
        except Exception as exc:  # noqa: BLE001 - per-plan isolation, recorded below
            # One plan's error never aborts its siblings: the loss is recorded
            # here and stays visible in the ledger instead of silent.
            _record(plan.case_id, plan.operator_name, "error", f"{type(exc).__name__} in {stage}")
            continue
        seen_ids.add(plan.case_id)
        index_lines.append(_index_line(plan, case_dir))
        result.cases_written += 1
        _record(plan.case_id, plan.operator_name, "written", "")

    if config.include_canonical_cases:
        for fixture in fixtures:
            index_lines.append(
                {
                    "record_type": "suite_case",
                    "case_id": fixture.fixture_id,
                    "kind": "canonical",
                    "parent_id": None,
                    "operator": None,
                    "expected_decision": fixture.manifest.expected_decision().value,
                    "report_class": fixture.manifest.report_class.value,
                    "manifest_path": None,
                }
            )

    index_lines.sort(key=lambda line: line["case_id"])
    header = {
        "record_type": "suite_header",
        "suite_name": config.name,
        "corpus_root": header_corpus_root,
        "base_seed": config.base_seed,
        "generator_version": __version__,
    }
    (out_root / SUITE_INDEX_NAME).write_text(
        json.dumps(header, sort_keys=True)
        + "\n"
        + "".join(json.dumps(line, sort_keys=True) + "\n" for line in index_lines),
        encoding="utf-8",
    )

    canonical_included = len(fixtures) if config.include_canonical_cases else 0
    tallies = _tally_outcomes(result.outcomes)
    ledger_header = {
        "record_type": "materialization_header",
        "suite_name": config.name,
        "base_seed": config.base_seed,
        "generator_version": __version__,
        # Production/mutation version identity: full-item-v1 step spans
        # (B1 fix); readers must not assume older span semantics.
        "span_model": "full-item-v1",
        "planned": len(result.outcomes),
        **tallies,
        "canonical_included": canonical_included,
        "selected_total": len(index_lines),
    }
    (out_root / LEDGER_FILE_NAME).write_text(
        json.dumps(ledger_header, sort_keys=True)
        + "\n"
        + "".join(
            json.dumps(
                {
                    "record_type": "materialization_outcome",
                    "case_id": outcome.case_id,
                    "operator": outcome.operator_name,
                    "status": outcome.status,
                    "detail": outcome.detail,
                },
                sort_keys=True,
            )
            + "\n"
            for outcome in result.outcomes
        ),
        encoding="utf-8",
    )
    return result


def read_materialization_ledger(out_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read and internally reconcile the materialization ledger.

    Validates: header present, one row per planned case
    (``planned == written + no_op + duplicate + safety_blocked + error``),
    known statuses only, tallies matching the header. Returns
    ``(header, rows)``; raises :class:`ValueError` on any mismatch, so a
    dropped or edited row cannot pass silently.
    """
    lines = (out_root / LEDGER_FILE_NAME).read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    if not rows or rows[0].get("record_type") != "materialization_header":
        raise ValueError(f"{out_root}: missing materialization header")
    header, outcomes = rows[0], rows[1:]
    for row in outcomes:
        if row.get("record_type") != "materialization_outcome":
            raise ValueError(f"{out_root}: malformed ledger row for {row.get('case_id')!r}")
        if row.get("status") not in MATERIALIZATION_STATUSES:
            raise ValueError(
                f"{out_root}: unknown ledger status {row.get('status')!r} "
                f"for {row.get('case_id')!r}"
            )
    tallies = dict.fromkeys(MATERIALIZATION_STATUSES, 0)
    for row in outcomes:
        tallies[row["status"]] += 1
    if len(outcomes) != header.get("planned"):
        raise ValueError(
            f"{out_root}: ledger rows {len(outcomes)} != planned {header.get('planned')}"
        )
    for status in MATERIALIZATION_STATUSES:
        if tallies[status] != header.get(status):
            raise ValueError(
                f"{out_root}: ledger {status} {tallies[status]} != header {header.get(status)}"
            )
    return header, outcomes


def check_materialization(out_root: Path) -> dict[str, Any]:
    """Reconcile the ledger against the published suite index.

    Every ``written`` row must have exactly one mutated index row, and the
    header's ``selected_total`` must equal the index row count
    (written mutated + included canonical). Returns the reconciled counts.
    """
    from sloplab.scoring.harness import read_suite_index

    header, outcomes = read_materialization_ledger(out_root)
    _, entries = read_suite_index(out_root / SUITE_INDEX_NAME)
    indexed_mutated = sorted(
        entry["case_id"] for entry in entries if entry.get("kind") == "mutated"
    )
    written = sorted(row["case_id"] for row in outcomes if row["status"] == "written")
    if indexed_mutated != written:
        raise ValueError(
            f"{out_root}: indexed mutated cases do not match written ledger rows "
            f"(index {len(indexed_mutated)}, ledger {len(written)})"
        )
    if len(entries) != header.get("selected_total"):
        raise ValueError(
            f"{out_root}: index rows {len(entries)} != selected {header.get('selected_total')}"
        )
    return {
        "planned": header["planned"],
        "written": header["written"],
        "selected": len(entries),
        "canonical_included": header["canonical_included"],
    }


def load_suite_config(path: Path) -> SuiteConfig:
    """Load and validate a suite YAML file with an actionable error message."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    from pydantic import ValidationError

    from sloplab.corpus.loader import format_validation_error

    try:
        return SuiteConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(
            f"{path}: suite configuration invalid\n{format_validation_error(exc)}"
        ) from exc
