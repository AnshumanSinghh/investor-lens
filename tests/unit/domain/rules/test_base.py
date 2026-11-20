"""The FilterRule template method and the CheckCollector builder."""

from __future__ import annotations

import logging

import pytest

from investor_lens.domain.models import EvaluationContext, RuleResult
from investor_lens.domain.rules import CheckCollector, FilterRule, combine_checks
from support.builders import make_snapshot


class _AlwaysPasses(FilterRule):
    name = "always_passes"
    investor = "Test Investor"

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        collector = CheckCollector()
        collector.record("only_check", True, 0.8)
        return self._finalize(collector)


class _Exploding(FilterRule):
    name = "exploding"
    investor = "Nobody"
    gating = False

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        raise RuntimeError("boom")


@pytest.mark.parametrize(
    ("checks", "expected"),
    [
        ({"a": True, "b": None, "c": False}, False),  # a failure always wins
        ({"a": True, "b": None}, None),  # unknown beats pass
        ({"a": True, "b": True}, True),
    ],
)
def test_combine_checks(checks, expected):
    assert combine_checks(checks) is expected


class TestFilterRuleTemplate:
    def test_finalize_stamps_rule_identity_and_records_checks(self, make_context):
        result = _AlwaysPasses(fallback_score=0.0).evaluate(make_context(make_snapshot()))
        assert (result.rule_name, result.investor, result.gating) == ("always_passes", "Test Investor", True)
        assert result.passed is True
        assert result.score == pytest.approx(0.8)
        assert result.status == "OK"
        assert result.metrics["checks"] == {"only_check": True}

    def test_exception_becomes_a_fallback_result(self, make_context):
        result = _Exploding(fallback_score=0.25).evaluate(make_context(make_snapshot()))
        assert result.status == "FALLBACK"
        assert result.passed is None
        assert result.score == 0.25
        assert result.gating is False  # identity is preserved on failure
        assert "boom" in result.reasons[0]

    def test_exception_is_logged_with_the_ticker(self, make_context, caplog):
        with caplog.at_level(logging.ERROR):
            _Exploding(fallback_score=0.0).evaluate(make_context(make_snapshot("ACME")))
        assert any("ACME" in r.getMessage() and "exploding" in r.getMessage() for r in caplog.records)


class TestCheckCollector:
    def test_collects_scores_and_reasons(self):
        collector = CheckCollector()
        collector.record("a", True, 1.0)
        collector.record("b", False, 0.0, "b failed")
        collector.skip("c", "c unknown")
        assert collector.passed is False
        assert collector.score(fallback=-1) == pytest.approx(0.5)
        assert collector.reasons == ["b failed", "c unknown"]

    def test_fail_is_a_hard_failure_without_a_score(self):
        collector = CheckCollector()
        collector.fail("a", "no equity")
        assert collector.passed is False
        assert collector.has_scores is False

    def test_fallback_score_when_nothing_was_computed(self):
        collector = CheckCollector()
        collector.skip("a", "unknown")
        assert collector.has_scores is False
        assert collector.score(fallback=0.3) == 0.3

    def test_checks_property_returns_a_copy(self):
        collector = CheckCollector()
        collector.record("a", True, 1.0)
        collector.checks["a"] = False
        assert collector.passed is True
