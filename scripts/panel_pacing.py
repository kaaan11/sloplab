"""One shared request-start pacer for the three threads in a panel process."""

from __future__ import annotations

import threading
import time

MIN_INTERVAL_SECONDS = 3.1  # fewer than 20 starts in any rolling minute
_lock = threading.Lock()
_last_start: float | None = None


def pace_request() -> None:
    global _last_start
    with _lock:
        now = time.monotonic()
        if _last_start is not None:
            wait = MIN_INTERVAL_SECONDS - (now - _last_start)
            if wait > 0:
                time.sleep(wait)
        _last_start = time.monotonic()
