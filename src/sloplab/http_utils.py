"""Shared HTTP response conventions for evaluator transports."""

from __future__ import annotations

import math
from datetime import UTC
from email.utils import parsedate_to_datetime


def retry_after_seconds(raw: str | None, *, now: float) -> float | None:
    """Parse seconds or an HTTP date, interpreting obsolete naive dates as UTC."""
    if raw is None:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        try:
            target = parsedate_to_datetime(raw)
            if target.tzinfo is None:
                target = target.replace(tzinfo=UTC)
            seconds = target.timestamp() - now
        except (TypeError, ValueError, OverflowError, OSError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None
