"""Maps the domain report to a plain, JSON-safe dictionary (Builder)."""

from __future__ import annotations

from typing import Any, Dict, List, cast

from investor_lens import __version__
from investor_lens.domain.models import (
    AssetEvaluation,
    NewsItem,
    PipelineReport,
    PortfolioSummary,
    RuleResult,
    Verdict,
)
from investor_lens.infrastructure.reporting.serializer import to_jsonable

LIMITATIONS: List[str] = [
    "Yahoo Finance supplies ~4-5 years of annual fundamentals; P/E and P/B z-scores use all "
    "available point-in-time observations within the 10Y price window (see *_observations).",
    "Intrinsic value uses FCF0 and trailing EPS growth (clamped); net debt is not subtracted. "
    "Treat it as a screening estimate, not a price target.",
    "passed=null means a check could not be computed (fallback score applied), not that it passed.",
]


class PayloadBuilder:
    def build(self, report: PipelineReport) -> Dict[str, Any]:
        counts = {verdict.value: 0 for verdict in Verdict}
        for evaluation in report.evaluations:
            counts[evaluation.verdict.value] += 1
        market = report.market
        payload = {
            "metadata": {
                "generated_at_utc": report.generated_at,
                "tool_version": __version__,
                "data_source": report.data_source,
                "tickers_requested": [e.ticker for e in report.evaluations],
                "verdict_counts": counts,
                "risk_free_rate": market.risk_free_rate,
                "risk_free_source": market.risk_free_source,
                "benchmark": report.run_parameters.benchmark,
                "market_data_notes": market.notes,
                "thresholds": dict(report.run_parameters.thresholds),
                "limitations": LIMITATIONS,
            },
            "portfolio": self._portfolio(report.portfolio),
            "assets": [self._asset(e) for e in report.evaluations],
        }
        return cast(Dict[str, Any], to_jsonable(payload))

    @staticmethod
    def _portfolio(portfolio: PortfolioSummary) -> Dict[str, Any]:
        return {
            "method": portfolio.method,
            "qualified_tickers": portfolio.qualified_tickers,
            "correlation_matrix": portfolio.correlation_matrix,
            "suggested_weights": portfolio.suggested_weights,
        }

    @staticmethod
    def _rule(result: RuleResult) -> Dict[str, Any]:
        return {
            "rule": result.rule_name,
            "investor": result.investor,
            "gating": result.gating,
            "passed": result.passed,
            "score": result.score,
            "status": result.status,
            "metrics": result.metrics,
            "reasons": result.reasons,
        }

    @staticmethod
    def _news(item: NewsItem) -> Dict[str, Any]:
        return {
            "title": item.title,
            "publisher": item.publisher,
            "published_at": item.published_at,
            "url": item.url,
            "summary": item.summary,
        }

    def _asset(self, evaluation: AssetEvaluation) -> Dict[str, Any]:
        snapshot = evaluation.snapshot
        return {
            "ticker": evaluation.ticker,
            "name": snapshot.name if snapshot else None,
            "sector": snapshot.sector if snapshot else None,
            "currency": snapshot.currency if snapshot else None,
            "current_price": snapshot.current_price if snapshot else None,
            "verdict": evaluation.verdict.value,
            "composite_score": evaluation.composite_score,
            "suggested_weight": evaluation.suggested_weight,
            "avg_correlation_to_portfolio": evaluation.avg_portfolio_correlation,
            "weight_adjustments": evaluation.weight_adjustments,
            "rules": [self._rule(r) for r in evaluation.rule_results],
            "news": [self._news(item) for item in (snapshot.news if snapshot else [])],
            "data_quality_notes": (snapshot.data_notes if snapshot else []) + evaluation.errors,
        }
