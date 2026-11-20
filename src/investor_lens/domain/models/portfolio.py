"""Portfolio-level allocation output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PortfolioSummary:
    method: str
    qualified_tickers: List[str] = field(default_factory=list)
    correlation_matrix: Dict[str, Dict[str, Optional[float]]] = field(default_factory=dict)
    suggested_weights: Dict[str, float] = field(default_factory=dict)
