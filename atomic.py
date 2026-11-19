"""Atomic text writes so an interrupted stage leaves the last-good file."""

from __future__ import annotations

import os
from pathlib import Path


def write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
