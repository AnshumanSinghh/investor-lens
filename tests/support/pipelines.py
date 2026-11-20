"""Hand-wiring of the pipeline for tests: no bootstrap, no config, only injected collaborators."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional, Sequence

from investor_lens.application.market_context import MarketContextLoader
from investor_lens.application.pipeline import AnalysisPipeline
from investor_lens.application.policy import EvaluationPolicy, GatingEvaluationPolicy
from investor_lens.domain.allocation import PortfolioAllocator, RiskParityAllocator
from investor_lens.domain.models import RunParameters
from investor_lens.domain.parameters import BuffettParameters, DalioParameters, MarksParameters
from investor_lens.domain.rules import BuffettRule, DalioRule, FilterRule, MarksRule
from support.fakes import FakeGateway

FIXED_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def default_rules() -> list[FilterRule]:
    return [
        BuffettRule(BuffettParameters(), 0.0),
        MarksRule(MarksParameters(), 0.0),
        DalioRule(DalioParameters(), 0.0),
    ]


def make_pipeline(
    gateway: FakeGateway,
    rules: Optional[Sequence[FilterRule]] = None,
    allocator: Optional[PortfolioAllocator] = None,
    policy: Optional[EvaluationPolicy] = None,
) -> AnalysisPipeline:
    return AnalysisPipeline(
        gateway=gateway,
        rules=default_rules() if rules is None else rules,
        allocator=allocator or RiskParityAllocator(DalioParameters()),
        policy=policy or GatingEvaluationPolicy(0.0),
        context_loader=MarketContextLoader(gateway, risk_free_fallback=0.04),
        run_parameters=RunParameters(benchmark="^GSPC", thresholds={"k": 1}),
        fallback_score=0.0,
        clock=lambda: FIXED_NOW,
    )
