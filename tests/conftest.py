"""Shared pytest fixtures for SlopLab tests."""

from __future__ import annotations

from typing import Any

import pytest

from tests._helpers import write_canonical_fixture


@pytest.fixture(name="make_fixture")
def fixture_factory() -> Any:
    """Factory fixture wrapping :func:`write_canonical_fixture`."""
    return write_canonical_fixture
