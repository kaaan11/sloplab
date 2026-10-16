"""Explicit metadata values take precedence over inferred provenance."""

from __future__ import annotations

import subprocess

import pytest
from pydantic import ValidationError

from sloplab.reporting.writers import default_run_metadata


@pytest.fixture(autouse=True)
def git_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "abc123\n")
    )


def test_explicit_falsy_values_override_defaults() -> None:
    metadata = default_run_metadata(
        git_commit=None, sloplab_version="", python_version="", suite_name="", base_seed=0
    )
    assert metadata.git_commit is None
    assert metadata.sloplab_version == ""
    assert metadata.python_version == ""
    assert metadata.suite_name == ""
    assert metadata.base_seed == 0


def test_omitted_value_keeps_inferred_commit() -> None:
    assert default_run_metadata().git_commit == "abc123"


@pytest.mark.parametrize("value", [None, "", False, 0])
def test_invalid_explicit_run_id_is_validated(value: object) -> None:
    with pytest.raises(ValidationError):
        default_run_metadata(run_id=value)


def test_unknown_override_names_allowed_fields() -> None:
    with pytest.raises(
        ValueError, match="unknown run metadata fields: typo; allowed fields:.*run_id"
    ):
        default_run_metadata(typo="value")
