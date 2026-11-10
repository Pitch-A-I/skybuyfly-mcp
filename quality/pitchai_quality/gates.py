# Copyright (c) 2026 PitchAI. All rights reserved.
"""Expose the existing consumer gate registry to the portable ratchet."""

from .check import Gate
from .check import build_gates as gates

__all__ = ("Gate", "gates")

PYTHON_PATHS = (".", "quality")
