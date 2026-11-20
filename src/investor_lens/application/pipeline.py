"""Orchestrates fetch -> rule evaluation -> verdict -> portfolio allocation."""

from __future__ import annotations

import dataclasses
import logging
from datetime import UTC, datetime
from typing import Callable, Dict, Optional, Sequence, Tuple

import pandas as pd

from investor_lens.application.market_context import MarketContextLoader
from investor_lens.application.policy import EvaluationPolicy
from investor_lens.application.ports import MarketDataGateway, NewsGateway
from investor_lens.domain.allocation import PortfolioAllocator
from investor_lens.domain.models import (
    AssetEvaluation,
    AssetSnapshot,
    EvaluationContext,
    MarketContext,
    PipelineReport,
    PortfolioSummary,
    RunParameters,
    Verdict,
)
from investor_lens.domain.rules import FilterRule

LOGGER = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AnalysisPipeline:
    """All collaborators are injected, so the pipeline never changes when rules,
    vendors, policies or allocators are added or swapped (Open/Closed, DIP)."""

    def __init__(
        self,
        *,
        gateway: MarketDataGateway,
        rules: Sequence[FilterRule],
        allocator: PortfolioAllocator,
        policy: EvaluationPolicy,
        context_loader: MarketContextLoader,
        run_parameters: RunParameters,
        fallback_score: float,
        news_gateway: Optional[NewsGateway] = None,
        news_limit: int = 10,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._gateway = gateway
        self._rules = list(rules)
        self._allocator = allocator
        self._policy = policy
        self._context_loader = context_loader
        self._run_parameters = run_parameters
        self._fallback_score = fallback_score
        self._news_gateway = news_gateway
        self._news_limit = news_limit
        self._clock = clock

    def run(self, tickers: Sequence[str]) -> PipelineReport:
        market = self._context_loader.load()
        evaluations: list[AssetEvaluation] = []
        returns: Dict[str, pd.Series] = {}

        for index, ticker in enumerate(tickers, start=1):
            LOGGER.info("Processing %s (%d/%d)", ticker, index, len(tickers))
            evaluation, asset_returns = self._evaluate_ticker(ticker, market)
            evaluations.append(evaluation)
            if asset_returns is not None:
                returns[ticker] = asset_returns

        return PipelineReport(
            generated_at=self._clock(),
            data_source=self._gateway.name,
            run_parameters=self._run_parameters,
            market=market,
            evaluations=evaluations,
            portfolio=self._allocate(evaluations, returns),
        )

    def _allocate(
        self, evaluations: list[AssetEvaluation], returns: Dict[str, pd.Series]
    ) -> PortfolioSummary:
        try:
            return self._allocator.allocate(evaluations, returns)
        except Exception:
            LOGGER.exception("Allocator failed; returning report without weights.")
            return PortfolioSummary(method="allocation failed")

    def _with_news(self, snapshot: AssetSnapshot) -> AssetSnapshot:
        """Attach headlines. News is best-effort: a failure is noted, never fatal."""
        if self._news_gateway is None:
            return snapshot
        try:
            news = self._news_gateway.fetch_news(snapshot.ticker, self._news_limit)
        except Exception as exc:
            LOGGER.warning("[%s] news unavailable: %r", snapshot.ticker, exc)
            return dataclasses.replace(
                snapshot, data_notes=[*snapshot.data_notes, f"News unavailable: {exc!r}"]
            )
        return dataclasses.replace(snapshot, news=list(news))

    def _evaluate_ticker(
        self, ticker: str, market: MarketContext
    ) -> Tuple[AssetEvaluation, Optional[pd.Series]]:
        try:
            snapshot = self._gateway.fetch_asset(ticker)
        except Exception as exc:
            LOGGER.error("[%s] data unavailable: %r", ticker, exc)
            evaluation = AssetEvaluation(
                ticker, Verdict.DATA_UNAVAILABLE, self._fallback_score, errors=[f"Fetch failed: {exc!r}"]
            )
            return evaluation, None

        snapshot = self._with_news(snapshot)
        try:
            context = EvaluationContext(snapshot, market)
            results = [rule.evaluate(context) for rule in self._rules]
            verdict = self._policy.verdict(results)
            score = self._policy.composite_score(results)
            LOGGER.info("[%s] %s (score %.2f)", ticker, verdict.value, score)
            return AssetEvaluation(ticker, verdict, score, snapshot, results), snapshot.log_returns()
        except Exception as exc:
            LOGGER.exception("[%s] evaluation crashed", ticker)
            evaluation = AssetEvaluation(
                ticker,
                Verdict.INSUFFICIENT_DATA,
                self._fallback_score,
                snapshot,
                errors=[f"Evaluation failed: {exc!r}"],
            )
            return evaluation, None
