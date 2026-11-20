"""How individual rule results combine into a verdict and composite score (Strategy)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

import numpy as np

from investor_lens.domain.models import RuleResult, Verdict


class EvaluationPolicy(ABC):
    @abstractmethod
    def verdict(self, results: Sequence[RuleResult]) -> Verdict: ...

    @abstractmethod
    def composite_score(self, results: Sequence[RuleResult]) -> float: ...


class GatingEvaluationPolicy(EvaluationPolicy):
    """Gating rules decide the verdict; every rule contributes to the score.

    * any gating rule failed        -> DISQUALIFIED
    * any gating rule inconclusive  -> INSUFFICIENT_DATA
    * otherwise                     -> QUALIFIED
    """

    def __init__(self, fallback_score: float) -> None:
        self._fallback_score = fallback_score

    def verdict(self, results: Sequence[RuleResult]) -> Verdict:
        gating = [r for r in results if r.gating]
        if any(r.passed is False for r in gating):
            return Verdict.DISQUALIFIED
        if not gating or any(r.passed is None for r in gating):
            return Verdict.INSUFFICIENT_DATA
        return Verdict.QUALIFIED

    def composite_score(self, results: Sequence[RuleResult]) -> float:
        if not results:
            return self._fallback_score
        return float(np.mean([r.score for r in results]))
