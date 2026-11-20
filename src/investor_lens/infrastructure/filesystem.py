"""Filesystem helpers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(destination: Path, content: str, encoding: str = "utf-8") -> Path:
    """Write via a temp file then ``os.replace`` so readers never see a partial file."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(destination.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
        os.replace(tmp_name, destination)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return destination
