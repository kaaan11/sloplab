"""Portable provenance path rendering (#60).

Committed result bundles must not carry machine-specific absolute paths.
Provenance locations (corpus root, suite-config path, run.jsonl suite config)
are therefore rendered relative to the current working directory whenever they
lie under it, and keep their absolute form otherwise (open provenance, never
hashed into any identity).
"""

from __future__ import annotations

import os
from pathlib import Path


def portable_path_str(path: Path) -> str:
    """Render ``path`` cwd-relative when it lies under the cwd, else absolute.

    A Windows cross-drive ``os.path.relpath`` failure (path on a different
    drive than the cwd) falls back to the absolute path.
    """
    absolute = Path(path).absolute()
    try:
        relative = os.path.relpath(absolute, Path.cwd())
    except ValueError:  # platform-specific: different drive roots
        return str(absolute)
    if relative.startswith(os.pardir):
        return str(absolute)
    return relative
