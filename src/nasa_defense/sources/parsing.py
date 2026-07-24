"""Shared defensive conversions for external API payloads."""

from __future__ import annotations

import math
from typing import Any


def finite_float(value: Any) -> float | None:
    """Return a finite float, or ``None`` for missing, malformed, NaN, or infinite input."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    return number if math.isfinite(number) else None
