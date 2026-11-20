"""Strict-JSON-safe conversion."""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

FLOAT_PRECISION = 6


def to_jsonable(obj: Any) -> Any:
    """Recursively convert to JSON-safe types (NaN/inf become ``null``)."""
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        return round(value, FLOAT_PRECISION) if math.isfinite(value) else None
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)
