"""Aggregate result of one pipeline run."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Mapping

from investor_lens.domain.models.evaluation import AssetEvaluation
from investor_lens.domain.models.market import MarketContext
from investor_lens.domain.models.portfolio import PortfolioSummary


@dataclass(frozen=True)
class RunParameters:
    """Descriptive run metadata echoed into the report for the LLM consumer."""

    benchmark: str
    thresholds: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class PipelineReport:
    generated_at: datetime
    data_source: str
    run_parameters: RunParameters
    market: MarketContext
    evaluations: List[AssetEvaluation]
    portfolio: PortfolioSummary
