from __future__ import annotations

import pytest

from investor_lens.application.policy import GatingEvaluationPolicy
from investor_lens.domain.models import RuleResult, Verdict

policy = GatingEvaluationPolicy(fallback_score=0.0)


def result(passed, gating=True, score=0.5) -> RuleResult:
    return RuleResult("r", "i", gating, passed, score, "OK")


class TestVerdict:
    def test_all_gating_rules_passing_qualifies(self):
        assert policy.verdict([result(True), result(True)]) == Verdict.QUALIFIED

    def test_any_gating_failure_disqualifies_even_if_others_are_unknown(self):
        assert policy.verdict([result(None), result(False), result(True)]) == Verdict.DISQUALIFIED

    def test_inconclusive_gating_rule_is_insufficient_data(self):
        assert policy.verdict([result(True), result(None)]) == Verdict.INSUFFICIENT_DATA

    def test_non_gating_failures_do_not_disqualify(self):
        assert policy.verdict([result(True), result(False, gating=False)]) == Verdict.QUALIFIED

    def test_non_gating_unknowns_do_not_block_qualification(self):
        assert policy.verdict([result(True), result(None, gating=False)]) == Verdict.QUALIFIED

    @pytest.mark.parametrize("results", [[], [result(True, gating=False)]])
    def test_without_any_gating_rule_nothing_can_qualify(self, results):
        assert policy.verdict(results) == Verdict.INSUFFICIENT_DATA


class TestCompositeScore:
    def test_is_the_mean_of_all_rules_gating_or_not(self):
        results = [result(True, score=1.0), result(True, gating=False, score=0.5)]
        assert policy.composite_score(results) == pytest.approx(0.75)

    def test_empty_uses_the_fallback(self):
        assert GatingEvaluationPolicy(fallback_score=0.3).composite_score([]) == 0.3
