"""Tests for GitHub Actions CI/CD configuration integrity (Phase 10)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ci_workflow_valid_and_complete() -> None:
    ci_file = REPO_ROOT / ".github/workflows/ci.yml"
    assert ci_file.is_file(), "CI workflow file .github/workflows/ci.yml must exist"

    content = ci_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert data["name"] == "CI"
    on_triggers = data.get("on") or data.get(True) or {}
    assert "push" in on_triggers
    assert "pull_request" in on_triggers

    jobs = data.get("jobs", {})
    assert "test" in jobs

    test_job = jobs["test"]
    matrix = test_job.get("strategy", {}).get("matrix", {})
    python_versions = matrix.get("python-version", [])
    assert "3.11" in python_versions
    assert "3.12" in python_versions
    assert "3.13" in python_versions

    step_names = [s.get("name", "") for s in test_job.get("steps", [])]
    assert any("pytest" in name.lower() for name in step_names)
    assert any("ruff" in name.lower() for name in step_names)
    assert any("mypy" in name.lower() for name in step_names)
    assert any("validate" in name.lower() for name in step_names)
