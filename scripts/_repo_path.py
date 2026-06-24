"""Ensure repo root is on sys.path when running scripts directly."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_root = str(_REPO_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)
