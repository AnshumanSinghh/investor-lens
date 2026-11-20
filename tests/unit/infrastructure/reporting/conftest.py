from __future__ import annotations

import pytest

from investor_lens.domain.models import PipelineReport
from support.reports import sample_report


@pytest.fixture(scope="module")
def report() -> PipelineReport:
    return sample_report()
