"""Use case: screen the tickers and persist the payload."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Tuple

from investor_lens.application.pipeline import AnalysisPipeline
from investor_lens.application.ports import ReportWriter
from investor_lens.domain.models import PipelineReport, Verdict

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerationResult:
    path: Path
    qualified_tickers: Tuple[str, ...]
    report: PipelineReport


class GenerateMarketIntelligence:
    def __init__(self, pipeline: AnalysisPipeline, writer: ReportWriter) -> None:
        self._pipeline = pipeline
        self._writer = writer

    def execute(self, tickers: Sequence[str], destination: Path) -> GenerationResult:
        report = self._pipeline.run(tickers)
        path = self._writer.write(report, destination)
        qualified = tuple(e.ticker for e in report.evaluations if e.verdict == Verdict.QUALIFIED)
        LOGGER.info("Wrote %s | qualified: %s", path, ", ".join(qualified) or "none")
        return GenerationResult(path=path, qualified_tickers=qualified, report=report)
