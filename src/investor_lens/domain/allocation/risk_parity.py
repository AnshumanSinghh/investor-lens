"""Dalio-style risk-parity allocation with Sharpe/correlation penalties."""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Mapping, Optional, cast

import numpy as np
import pandas as pd

from investor_lens.domain.allocation.base import PortfolioAllocator
from investor_lens.domain.calculators.risk import correlation_matrix
from investor_lens.domain.constants import Metric, RuleName
from investor_lens.domain.models import AssetEvaluation, PortfolioSummary, Verdict
from investor_lens.domain.parameters import DalioParameters

LOGGER = logging.getLogger(__name__)


class RiskParityAllocator(PortfolioAllocator):
    """Inverse-volatility weights, scaled down for low Sharpe or high correlation."""

    METHOD = (
        "inverse 90d annualized volatility x penalty scalars "
        "(low Sharpe, high benchmark correlation, high avg correlation to other "
        "qualified assets), normalized to 1"
    )

    def __init__(self, parameters: DalioParameters) -> None:
        self._p = parameters

    def allocate(
        self, evaluations: List[AssetEvaluation], returns: Mapping[str, pd.Series]
    ) -> PortfolioSummary:
        summary = PortfolioSummary(method=self.METHOD)
        qualified = [e for e in evaluations if e.verdict == Verdict.QUALIFIED]
        summary.qualified_tickers = [e.ticker for e in qualified]
        if not qualified:
            LOGGER.warning("No qualified assets; portfolio allocation skipped.")
            return summary

        corr = self._safe_correlation_matrix(qualified, returns)
        summary.correlation_matrix = {
            str(row_name): {str(col): (None if pd.isna(v) else float(v)) for col, v in row.items()}
            for row_name, row in corr.iterrows()
        }

        inverse_vols = self._inverse_volatilities(qualified)
        default_inverse = float(np.median(list(inverse_vols.values()))) if inverse_vols else 1.0

        raw_weights: Dict[str, float] = {}
        for evaluation in qualified:
            avg_corr = self._average_correlation(corr, evaluation.ticker)
            evaluation.avg_portfolio_correlation = avg_corr
            scalar = self._penalty_scalar(evaluation, avg_corr)
            raw_weights[evaluation.ticker] = inverse_vols.get(evaluation.ticker, default_inverse) * scalar

        total = sum(raw_weights.values())
        for evaluation in qualified:
            weight = raw_weights[evaluation.ticker] / total if total > 0 else 1.0 / len(qualified)
            evaluation.suggested_weight = weight
            summary.suggested_weights[evaluation.ticker] = weight
        return summary

    def _safe_correlation_matrix(
        self, qualified: List[AssetEvaluation], returns: Mapping[str, pd.Series]
    ) -> pd.DataFrame:
        try:
            subset = {e.ticker: returns[e.ticker] for e in qualified if e.ticker in returns}
            return correlation_matrix(subset, self._p.corr_lookback, self._p.min_corr_obs)
        except Exception:
            LOGGER.exception("Correlation matrix failed; continuing without it.")
            return pd.DataFrame()

    @staticmethod
    def _inverse_volatilities(qualified: List[AssetEvaluation]) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for evaluation in qualified:
            sigma = evaluation.metric(RuleName.DALIO, Metric.VOLATILITY)
            if sigma and math.isfinite(sigma) and sigma > 0:
                result[evaluation.ticker] = 1.0 / sigma
        return result

    def _penalty_scalar(self, evaluation: AssetEvaluation, avg_corr: Optional[float]) -> float:
        p = self._p
        scalar = 1.0

        sharpe = evaluation.metric(RuleName.DALIO, Metric.SHARPE_RATIO)
        if sharpe is not None and sharpe < p.min_sharpe:
            factor = max(p.sharpe_weight_floor, max(sharpe, 0.0) / p.min_sharpe)
            scalar *= factor
            evaluation.weight_adjustments.append(f"Sharpe {sharpe:.2f} < {p.min_sharpe}: x{factor:.2f}")

        market_corr = evaluation.metric(RuleName.DALIO, Metric.BENCHMARK_CORRELATION)
        if market_corr is not None and market_corr > p.max_market_corr:
            scalar *= p.corr_penalty
            evaluation.weight_adjustments.append(
                f"Benchmark correlation {market_corr:.2f} > {p.max_market_corr}: x{p.corr_penalty:.2f}"
            )

        if avg_corr is not None and avg_corr > p.max_portfolio_corr:
            scalar *= p.corr_penalty
            evaluation.weight_adjustments.append(
                f"Avg correlation to other qualified assets {avg_corr:.2f} > "
                f"{p.max_portfolio_corr}: x{p.corr_penalty:.2f}"
            )
        return scalar

    @staticmethod
    def _average_correlation(corr: pd.DataFrame, ticker: str) -> Optional[float]:
        if corr.empty or ticker not in corr.index or len(corr) < 2:
            return None
        others = cast(pd.Series, corr.loc[ticker]).drop(labels=[ticker]).dropna()
        return float(others.mean()) if not others.empty else None
