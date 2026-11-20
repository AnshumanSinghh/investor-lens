"""News rule: an advisory keyword screen over headlines."""

from __future__ import annotations

import pytest

from investor_lens.domain.models import NewsItem
from investor_lens.domain.parameters import NewsParameters
from investor_lens.domain.rules import NewsRule
from support.builders import make_snapshot

RULE = NewsRule(NewsParameters(), fallback_score=0.0)


def evaluate(make_context, *titles, summary=None, rule=RULE):
    news = [NewsItem(title=t, summary=summary) for t in titles]
    return rule.evaluate(make_context(make_snapshot(news=news)))


def test_is_advisory():
    assert RULE.gating is False


def test_calm_headlines_pass(make_context):
    result = evaluate(make_context, "Company opens new plant", "Quarterly results in line")

    assert result.passed is True
    assert result.metrics["headline_count"] == 2
    assert result.metrics["risk_headline_count"] == 0


def test_two_risky_headlines_raise_the_flag(make_context):
    result = evaluate(
        make_context, "Regulator opens probe into firm", "Analyst downgrade after lawsuit", "Fine"
    )

    assert result.passed is False
    assert result.metrics["risk_headline_count"] == 2
    terms = {t for h in result.metrics["risk_headlines"] for t in h["terms"]}
    assert {"probe", "downgrade", "lawsuit"} <= terms
    assert any("read them" in reason for reason in result.reasons)


def test_a_single_risky_headline_is_tolerated_by_default(make_context):
    assert evaluate(make_context, "CEO faces lawsuit", "Steady quarter").passed is True


def test_threshold_is_configurable(make_context):
    strict = NewsRule(NewsParameters(max_risk_headlines=0), 0.0)
    assert evaluate(make_context, "CEO faces lawsuit", rule=strict).passed is False


def test_matching_respects_word_boundaries_and_case(make_context):
    result = evaluate(make_context, "Banking sector rallies", "Urban renewal approved")

    assert result.metrics["risk_headline_count"] == 0  # "ban" is not in "banking"
    assert evaluate(make_context, "BANKRUPTCY filing expected").metrics["risk_headline_count"] == 1


def test_multi_word_terms_match(make_context):
    result = evaluate(make_context, "Firm issues profit warning")
    assert result.metrics["risk_headlines"][0]["terms"] == ["profit warning"]


def test_summaries_are_searched_too(make_context):
    result = evaluate(make_context, "Company update", summary="Facing a fraud investigation")
    assert result.metrics["risk_headline_count"] == 1


def test_positive_headlines_are_counted_but_never_offset_risk(make_context):
    result = evaluate(make_context, "Analyst upgrade", "Record profit", "Probe opens", "Lawsuit filed")

    assert result.metrics["positive_headline_count"] == 2
    assert result.passed is False


def test_no_headlines_is_inconclusive_not_a_pass(make_context):
    result = evaluate(make_context)

    assert result.passed is None
    assert result.status == "FALLBACK"
    assert any("No headlines" in reason for reason in result.reasons)


@pytest.mark.parametrize("risk,positive", [((), ("upgrade",)), (("fraud",), ()), ((), ())])
def test_empty_term_lists_are_supported(make_context, risk, positive):
    rule = NewsRule(NewsParameters(risk_terms=risk, positive_terms=positive), 0.0)
    assert evaluate(make_context, "Fraud upgrade", rule=rule).passed in (True, False)
