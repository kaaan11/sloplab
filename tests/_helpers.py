"""Fixture factory helpers shared across test modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def write_canonical_fixture(
    root: Path,
    short_name: str,
    *,
    fixture_id: str,
    title: str,
    report_class: str = "valid",
    pair_id: str | None = None,
    pair_role: str | None = None,
    required_evidence: list[str] | None = None,
    report_body: str | None = None,
    expected_dimensions: dict[str, float] | None = None,
) -> Path:
    """Create one canonical fixture directory under ``root/canonical/<short_name>``."""
    fixture_dir = root / "canonical" / short_name
    fixture_dir.mkdir(parents=True, exist_ok=True)
    body = (
        report_body
        if report_body is not None
        else f"""\
# {title}

## Summary

The lookup endpoint returns another tenant's object when requested directly.

## Affected Component

DemoVault object lookup endpoint at https://demo.example.org.

## Affected Versions

DemoVault 2.3.0 through 2.4.1 (demo builds only).

## Preconditions

Valid low-privilege account on the demo instance.

## Reproduction Steps

1. Sign in as user A (tenant 1).
2. Send `GET /objects/42` with tenant 2 context.
3. Observe the response body.

## Observed Result

The object of tenant 2 is returned without an authorization check.

## Expected Security Boundary

Cross-tenant object reads must require tenant-scoped authorization.

## Impact

Medium confidentiality impact on demo data only.
"""
    )
    (fixture_dir / "report.md").write_text(body, encoding="utf-8")
    manifest: dict[str, Any] = {
        "id": fixture_id,
        "title": title,
        "report_class": report_class,
        "ground_truth": {
            "reproducible": True,
            "impact_class": "medium",
            "required_evidence": required_evidence
            if required_evidence is not None
            else [
                "affected_component",
                "affected_versions",
                "preconditions",
                "reproduction_steps",
                "observed_result",
                "expected_security_boundary",
            ],
            "expected_dimensions": expected_dimensions
            if expected_dimensions is not None
            else {"reproducibility": 0.9},
        },
        "report": {"path": f"canonical/{short_name}/report.md"},
    }
    if pair_id is not None:
        manifest["pair_id"] = pair_id
        manifest["pair_role"] = pair_role or "plain"
    (fixture_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    return fixture_dir
