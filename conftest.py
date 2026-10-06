"""Pytest bootstrap.

Ensures the repository root is on ``sys.path`` so ``import workflow`` works no
matter how pytest is invoked (repo root, a subdirectory, or a CI runner). No
tests live in this file.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
