"""Output writers: JSONL run logs, CSV tables, and Markdown summaries."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sloplab.models.run import CaseRecord, RunMetadata
from sloplab.scoring.metrics import MetricBundle


def write_run_jsonl(out_path: Path, metadata: RunMetadata, records: list[CaseRecord]) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(metadata.model_dump_json() + "\n")
        for record in records:
            handle.write(record.model_dump_json() + "\n")
    return out_path


def read_run_jsonl(path: Path) -> tuple[RunMetadata | None, list[CaseRecord]]:
    metadata: RunMetadata | None = None
    records: list[CaseRecord] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if payload.get("record_type") == "run_metadata":
            metadata = RunMetadata.model_validate(payload)
        elif payload.get("record_type") == "case":
            records.append(CaseRecord.model_validate(payload))
        else:
            raise ValueError(f"{path}: unknown record_type {payload.get('record_type')!r}")
    return metadata, records


def default_run_metadata(**overrides: Any) -> RunMetadata:
    import platform
    import subprocess

    from sloplab import __version__

    git_commit: str | None = None
    try:
        git_commit = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
            or None
        )
    except (OSError, subprocess.SubprocessError):
        git_commit = None

    fields: dict[str, Any] = {
        "run_id": f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}",
        "sloplab_version": __version__,
        "python_version": platform.python_version(),
        "git_commit": git_commit,
        "suite_name": overrides.get("suite_name", "unnamed"),
        "suite_hash": overrides.get("suite_hash", ""),
        "suite_config": overrides.get("suite_config", {}),
        "base_seed": overrides.get("base_seed", 0),
        "evaluators": overrides.get("evaluators", []),
    }
    fields.update({k: v for k, v in overrides.items() if k not in fields or v})
    return RunMetadata.model_validate(fields)


CSV_COLUMNS: list[str] = [
    "case_id",
    "case_kind",
    "parent_id",
    "operator",
    "report_class",
    "expected_decision",
    "evaluator_name",
    "decision",
    "correct",
    "confidence",
]


def write_records_csv(out_path: Path, records: list[CaseRecord]) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dimension_names = sorted({d for r in records for d in r.dimensions}) if records else []
    columns = CSV_COLUMNS[:9] + [f"dim_{d}" for d in dimension_names] + ["confidence"]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            row: dict[str, Any] = {
                "case_id": record.case_id,
                "case_kind": record.case_kind,
                "parent_id": record.parent_id or "",
                "operator": record.operator or "",
                "report_class": record.report_class,
                "expected_decision": record.expected_decision.value
                if record.expected_decision
                else "",
                "evaluator_name": record.evaluator_name,
                "decision": record.decision.value,
                "correct": int(record.correct),
                "confidence": record.confidence,
            }
            for dim in dimension_names:
                row[f"dim_{dim}"] = record.dimensions.get(dim, "")
            writer.writerow(row)
    return out_path


def metrics_to_dict(bundle: MetricBundle) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(bundle)


def write_markdown_report(out_path: Path, bundles: list[MetricBundle], title: str) -> Path:
    lines: list[str] = [f"# {title}", ""]
    for bundle in bundles:
        lines.extend([f"## Evaluator: `{bundle.evaluator_name}`", ""])
        lines.append(f"- Cases scored: {bundle.total_cases}")
        lines.append(f"- Decision accuracy: {bundle.decision_accuracy:.3f}")
        if bundle.false_reassurance_rate is not None:
            lines.append(
                f"- False reassurance rate: {bundle.false_reassurance_rate:.3f} "
                f"({bundle.false_reassurance_count} cases)"
            )
        if bundle.over_rejection_rate is not None:
            lines.append(
                f"- Over-rejection rate: {bundle.over_rejection_rate:.3f} "
                f"({bundle.over_rejection_count} cases)"
            )
        if bundle.mutation_detection_rate is not None:
            lines.append(
                f"- Mutation detection rate: {bundle.mutation_detection_rate:.3f} "
                f"(of {bundle.mutation_detection_total} degrading mutations)"
            )
        if bundle.robustness_delta is not None:
            lines.append(
                f"- Robustness delta (canonical - mutated): {bundle.robustness_delta:+.3f}"
            )
        if bundle.presentation_susceptibility is not None:
            lines.append(
                f"- Presentation susceptibility: {bundle.presentation_susceptibility:+.3f}"
            )
        if bundle.calibration_error is not None:
            lines.append(f"- Calibration error (ECE): {bundle.calibration_error:.3f}")
        if bundle.dimension_mae:
            lines.append("- Dimension MAE:")
            for dim, err in bundle.dimension_mae.items():
                lines.append(f"  - {dim}: {err:.3f}")
        if bundle.per_class_accuracy:
            lines.append("- Accuracy by report class:")
            for cls, acc in bundle.per_class_accuracy.items():
                lines.append(f"  - {cls}: {acc:.3f}")
        if bundle.robustness_score is not None:
            lines.append(f"- Auxiliary Robustness Score: {bundle.robustness_score:.4f}")
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
