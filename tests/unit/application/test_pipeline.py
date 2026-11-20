"""AnalysisPipeline wired by hand: no bootstrap, no config, only injected collaborators."""

from __future__ import annotations

import pytest

from investor_lens.application.policy import GatingEvaluationPolicy
from investor_lens.domain.allocation import PortfolioAllocator
from investor_lens.domain.models import RuleResult, Verdict
from investor_lens.domain.rules import FilterRule
from support.builders import make_snapshot
from support.fakes import FakeGateway
from support.pipelines import FIXED_NOW, default_rules, make_pipeline


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway(
        {
            "CHEAP": make_snapshot("CHEAP", free_cash_flow=8e9),
            "PRICEY": make_snapshot("PRICEY", free_cash_flow=1e9),
            "LEVERED": make_snapshot("LEVERED", free_cash_flow=8e9, total_debt=9e9),
            "NODATA": make_snapshot("NODATA", eps=(), free_cash_flow=None),
        },
        failing=("BOOM",),
    )


def test_each_ticker_gets_the_verdict_its_data_deserves(gateway):
    report = make_pipeline(gateway).run(["CHEAP", "PRICEY", "LEVERED", "NODATA", "BOOM"])

    assert {e.ticker: e.verdict for e in report.evaluations} == {
        "CHEAP": Verdict.QUALIFIED,
        "PRICEY": Verdict.DISQUALIFIED,
        "LEVERED": Verdict.DISQUALIFIED,
        "NODATA": Verdict.INSUFFICIENT_DATA,
        "BOOM": Verdict.DATA_UNAVAILABLE,
    }
    assert report.portfolio.suggested_weights == {"CHEAP": pytest.approx(1.0)}


def test_report_carries_run_metadata(gateway):
    report = make_pipeline(gateway).run(["CHEAP"])
    assert report.generated_at == FIXED_NOW
    assert report.data_source == "fake"
    assert report.run_parameters.benchmark == "^GSPC"
    assert report.market.risk_free_rate == 0.04


def test_evaluations_keep_the_requested_order(gateway):
    report = make_pipeline(gateway).run(["PRICEY", "CHEAP", "LEVERED"])
    assert [e.ticker for e in report.evaluations] == ["PRICEY", "CHEAP", "LEVERED"]


def test_a_failed_fetch_is_recorded_not_raised(gateway):
    boom = make_pipeline(gateway).run(["BOOM"]).evaluations[0]
    assert boom.verdict == Verdict.DATA_UNAVAILABLE
    assert boom.snapshot is None
    assert boom.composite_score == 0.0
    assert "simulated outage" in boom.errors[0]


def test_market_data_failures_degrade_gracefully():
    gateway = FakeGateway(
        {"CHEAP": make_snapshot("CHEAP", free_cash_flow=8e9)}, risk_free_fails=True, benchmark_fails=True
    )
    report = make_pipeline(gateway).run(["CHEAP"])

    assert report.market.risk_free_source == "fallback_constant"
    assert report.market.benchmark_returns.empty
    assert report.evaluations[0].verdict in (Verdict.QUALIFIED, Verdict.INSUFFICIENT_DATA)


def test_rules_are_pluggable_without_touching_the_pipeline(gateway):
    class AlwaysRejects(FilterRule):
        name = "always_rejects"
        investor = "Skeptic"

        def _evaluate(self, ctx) -> RuleResult:
            return RuleResult(self.name, self.investor, self.gating, False, 0.0, "OK")

    report = make_pipeline(gateway, rules=[*default_rules(), AlwaysRejects(0.0)]).run(["CHEAP"])
    evaluation = report.evaluations[0]

    assert evaluation.verdict == Verdict.DISQUALIFIED
    assert [r.rule_name for r in evaluation.rule_results][-1] == "always_rejects"


def test_a_crashing_rule_degrades_to_insufficient_data(gateway):
    class Exploding(FilterRule):
        name = "exploding"
        investor = "Nobody"

        def _evaluate(self, ctx) -> RuleResult:
            raise RuntimeError("boom")

    report = make_pipeline(gateway, rules=[*default_rules(), Exploding(0.0)]).run(["CHEAP"])
    assert report.evaluations[0].verdict == Verdict.INSUFFICIENT_DATA


def test_a_crash_outside_the_rules_is_contained_per_ticker(gateway):
    class ExplodingPolicy(GatingEvaluationPolicy):
        def verdict(self, results):
            raise RuntimeError("policy bug")

    report = make_pipeline(gateway, policy=ExplodingPolicy(0.0)).run(["CHEAP", "PRICEY"])

    assert [e.verdict for e in report.evaluations] == [Verdict.INSUFFICIENT_DATA] * 2
    assert "policy bug" in report.evaluations[0].errors[0]
    assert report.evaluations[0].snapshot is not None  # the data we did get is kept


def test_a_failing_allocator_is_contained(gateway):
    class BrokenAllocator(PortfolioAllocator):
        def allocate(self, evaluations, returns):
            raise RuntimeError("alloc")

    report = make_pipeline(gateway, allocator=BrokenAllocator()).run(["CHEAP"])
    assert report.portfolio.method == "allocation failed"
    assert report.evaluations[0].verdict == Verdict.QUALIFIED
