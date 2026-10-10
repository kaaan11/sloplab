"""Atomic directory publication that NEVER replaces an existing destination.

Plain POSIX rename can replace an empty directory, even after an exists() check.
Use OS no-replace primitives instead; unsupported platforms/filesystems fail
closed. This guarantees atomic visibility, not durability across power loss.
"""

from __future__ import annotations

import ctypes
import errno
import os
import sys
from pathlib import Path


def publish_directory(source: Path, destination: Path) -> None:
    """Rename a same-filesystem directory without replacing any destination."""
    if os.name == "nt":
        # Unlike POSIX rename, Windows rename always refuses an existing target.
        os.rename(source, destination)
        return

    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux"):
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        # AT_FDCWD = -100; RENAME_NOREPLACE = 1 (Linux UAPI).
        status = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    elif sys.platform == "darwin":
        rename = getattr(libc, "renamex_np", None)
        if rename is None:
            raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        # RENAME_EXCL = 0x00000004 (Darwin).
        status = rename(os.fsencode(source), os.fsencode(destination), 4)
    else:
        raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable on this platform")
    if status != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))
