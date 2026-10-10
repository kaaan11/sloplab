"""Discover installed evaluator metadata; only explicitly selected targets are loaded."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from importlib import metadata

from sloplab.evaluators.base import list_evaluators
from sloplab.evaluators.external import ExternalEvaluatorError

ENTRY_POINT_GROUP = "sloplab.evaluators"


def _entries() -> list[metadata.EntryPoint]:
    try:
        return list(metadata.entry_points(group=ENTRY_POINT_GROUP))
    except Exception as exc:
        raise ExternalEvaluatorError(
            f"Cannot read installed evaluator metadata ({type(exc).__name__})."
        ) from exc


def list_plugins() -> list[dict[str, str | bool | None]]:
    """Read package metadata without importing any evaluator entry-point target."""
    entries = _entries()
    counts = Counter(entry.name for entry in entries)
    reserved = set(list_evaluators())
    rows: list[dict[str, str | bool | None]] = []
    for entry in entries:
        try:
            distribution = entry.dist
            package = distribution.metadata["Name"] if distribution else None
            version = distribution.version if distribution else None
            rows.append(
                {
                    "name": entry.name,
                    "target": entry.value,
                    "distribution": package,
                    "distribution_version": version,
                    "name_conflict": counts[entry.name] > 1 or entry.name in reserved,
                }
            )
        except Exception as exc:
            raise ExternalEvaluatorError(
                f"Cannot inspect evaluator package metadata ({type(exc).__name__})."
            ) from exc
    return sorted(
        rows,
        key=lambda r: tuple(
            str(r[k] or "") for k in ("name", "distribution", "distribution_version", "target")
        ),
    )


def resolve_plugin_specs(names: Sequence[str]) -> list[tuple[str, str]]:
    """Reject unknown/duplicate/reserved selections before importing selected targets."""
    if len(set(names)) != len(names):
        raise ExternalEvaluatorError("Duplicate evaluator plugin selection.")
    entries = _entries()
    reserved = set(list_evaluators())
    specs = []
    for name in names:
        if not name.strip() or name != name.strip():
            raise ExternalEvaluatorError("Evaluator plugin name must be non-empty and unpadded.")
        matches = [entry for entry in entries if entry.name == name]
        if not matches:
            raise ExternalEvaluatorError(
                f"Evaluator plugin '{name}' is not installed; "
                "use 'sloplab evaluators' to list plugins."
            )
        if len(matches) != 1:
            raise ExternalEvaluatorError(f"Multiple installed packages advertise plugin '{name}'.")
        if name in reserved:
            raise ExternalEvaluatorError(f"Evaluator plugin name collides with a built-in: {name}")
        entry = matches[0]
        try:
            module, attr = entry.module, entry.attr
        except Exception as exc:
            raise ExternalEvaluatorError("Invalid evaluator entry-point target metadata.") from exc
        if (
            not module
            or not attr
            or not all(part.isidentifier() for part in module.split("."))
            or not all(part.isidentifier() for part in attr.split("."))
        ):
            raise ExternalEvaluatorError("Evaluator entry-point target must be MODULE:ATTR.")
        specs.append((name, f"{module}:{attr}"))
    return specs
