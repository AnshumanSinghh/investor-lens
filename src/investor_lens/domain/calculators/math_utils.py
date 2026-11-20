"""Small numeric helpers shared across layers."""

from __future__ import annotations


def clip(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into ``[low, high]``."""
    return max(low, min(high, value))
