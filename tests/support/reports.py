"""Ready-made domain reports for reporting and end-to-end tests."""

from __future__ import annotations

import json
import re
from typing import Any

from investor_lens.domain.models import PipelineReport
from support.builders import make_snapshot
from support.fakes import FakeGateway
from support.pipelines import make_pipeline


def sample_gateway(**kwargs: Any) -> FakeGateway:
    snapshots = {
        "CHEAP": make_snapshot("CHEAP", free_cash_flow=8e9),
        "PRICEY": make_snapshot("PRICEY", free_cash_flow=1e9),
        "LEVERED": make_snapshot("LEVERED", free_cash_flow=8e9, total_debt=9e9),
        "NODATA": make_snapshot("NODATA", eps=(), free_cash_flow=None),
    }
    return FakeGateway(snapshots, failing=("BOOM",), **kwargs)


SAMPLE_TICKERS = ["CHEAP", "PRICEY", "LEVERED", "NODATA", "BOOM"]


def sample_report() -> PipelineReport:
    """One ticker per verdict, with deterministic time and data."""
    return make_pipeline(sample_gateway()).run(SAMPLE_TICKERS)


def strict_json_loads(text: str) -> Any:
    """Parse JSON the way a strict consumer would: NaN/Infinity are errors."""

    def reject(constant: str) -> None:
        raise AssertionError(f"non-strict JSON constant {constant}")

    return json.loads(text, parse_constant=reject)


def extract_json_block(markdown: str) -> Any:
    match = re.search(r"```json\n(.*)\n```", markdown, re.S)
    assert match, "no fenced json block found"
    return strict_json_loads(match.group(1))
