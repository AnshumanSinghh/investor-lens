from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from enum import Enum

import numpy as np
import pandas as pd
import pytest

from investor_lens.infrastructure.reporting import to_jsonable


class Color(Enum):
    RED = "red"


@pytest.mark.parametrize("bad", [float("nan"), math.inf, -math.inf, np.float64("nan"), np.float32("inf")])
def test_non_finite_floats_become_null(bad):
    assert to_jsonable(bad) is None


def test_floats_are_rounded_to_six_places():
    assert to_jsonable(np.float64(1.23456789)) == 1.234568
    assert to_jsonable(0.1 + 0.2) == 0.3


def test_numpy_scalars_become_native_python_types():
    assert type(to_jsonable(np.int64(3))) is int
    assert to_jsonable(np.bool_(True)) is True
    assert type(to_jsonable(np.bool_(False))) is bool


def test_booleans_stay_booleans_not_integers():
    assert to_jsonable(True) is True


def test_datetimes_and_timestamps_become_iso_strings():
    assert to_jsonable(datetime(2026, 1, 1, tzinfo=UTC)) == "2026-01-01T00:00:00+00:00"
    assert to_jsonable(pd.Timestamp("2026-01-01")).startswith("2026-01-01")


def test_enums_use_their_value():
    assert to_jsonable(Color.RED) == "red"


def test_containers_are_converted_recursively_and_keys_stringified():
    cleaned = to_jsonable({1: (1, 2), "s": {"nan": float("nan")}, "set": {3}})
    assert cleaned == {"1": [1, 2], "s": {"nan": None}, "set": [3]}


def test_unknown_objects_fall_back_to_str():
    assert to_jsonable(object).startswith("<class")


def test_none_and_strings_pass_through():
    assert to_jsonable(None) is None
    assert to_jsonable("x") == "x"


def test_output_is_always_strictly_serialisable():
    payload = to_jsonable({"a": [float("nan"), np.float64(2.0), pd.Timestamp("2026-01-01"), Color.RED]})
    json.dumps(payload, allow_nan=False)
