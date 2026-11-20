from __future__ import annotations

import pytest

from investor_lens.domain.calculators.math_utils import clip


@pytest.mark.parametrize(
    ("value", "expected"),
    [(5, 5), (-1, 0), (11, 10), (0, 0), (10, 10)],
)
def test_clip_clamps_into_the_closed_interval(value, expected):
    assert clip(value, 0, 10) == expected
