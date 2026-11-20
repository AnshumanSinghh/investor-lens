"""Allocator abstraction (Strategy)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Mapping

import pandas as pd

from investor_lens.domain.models import AssetEvaluation, PortfolioSummary


class PortfolioAllocator(ABC):
    """Turns qualified evaluations into suggested portfolio weights."""

    @abstractmethod
    def allocate(
        self, evaluations: List[AssetEvaluation], returns: Mapping[str, pd.Series]
    ) -> PortfolioSummary:
        """Return the portfolio summary.

        Implementations annotate each qualified ``AssetEvaluation`` in place with
        ``suggested_weight``, ``avg_portfolio_correlation`` and ``weight_adjustments``.
        """
