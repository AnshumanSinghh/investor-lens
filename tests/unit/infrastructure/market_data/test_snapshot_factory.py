from __future__ import annotations

import pandas as pd
import pytest

from investor_lens.infrastructure.market_data.snapshot_factory import build_asset_snapshot
from investor_lens.infrastructure.market_data.statement_parsing import normalize_price_series
from support.yfinance_fakes import price_history, statement

EMPTY = pd.DataFrame()


def build(info=None, income=EMPTY, balance=EMPTY, cashflow=EMPTY, notes=None, ticker="AAA"):
    close = normalize_price_series(price_history()["Close"])  # last close = 120.0
    return build_asset_snapshot(
        ticker=ticker,
        close=close,
        adjusted=close,
        info=info or {},
        income=income,
        balance=balance,
        cashflow=cashflow,
        default_tax_rate=0.21,
        notes=[] if notes is None else notes,
    )


def test_maps_statements_into_the_vendor_neutral_snapshot():
    snapshot = build(
        info={
            "longName": "Alpha Inc",
            "sector": "Tech",
            "currency": "USD",
            "sharesOutstanding": 1e9,
            "beta": 1.2,
        },
        income=statement(
            **{
                "Diluted EPS": [3.0, 2.0, 1.0],
                "Interest Expense": [-1e8, -1e8, -1e8],
                "Tax Rate For Calcs": [0.9, 0.2, 0.2],
            }
        ),
        balance=statement(**{"Total Debt": [2e9, 2e9, 2e9], "Stockholders Equity": [1e10, 9e9, 8e9]}),
        cashflow=statement(**{"Free Cash Flow": [70.0, 60.0, 50.0]}),
    )
    assert (snapshot.name, snapshot.sector, snapshot.currency, snapshot.beta) == (
        "Alpha Inc",
        "Tech",
        "USD",
        1.2,
    )
    assert snapshot.current_price == pytest.approx(120.0)
    assert snapshot.total_debt == 2e9
    assert snapshot.total_equity == 1e10
    assert snapshot.free_cash_flow == 70.0
    assert snapshot.interest_expense == 1e8  # sign normalised
    assert snapshot.tax_rate == 0.40  # clamped: the latest reported rate is 0.9
    assert list(snapshot.eps_history.values) == [1.0, 2.0, 3.0]  # oldest first
    assert snapshot.market_cap == pytest.approx(120.0 * 1e9)  # derived from price x shares


class TestFreeCashFlow:
    def test_is_derived_from_operating_cash_flow_and_capex_when_not_reported(self):
        notes: list[str] = []
        snapshot = build(
            cashflow=statement(
                **{"Operating Cash Flow": [100.0, 90.0, 80.0], "Capital Expenditure": [-30.0] * 3}
            ),
            notes=notes,
        )
        assert snapshot.free_cash_flow == 70.0
        assert "FCF derived as operating cash flow minus capex." in snapshot.data_notes

    def test_reported_value_is_preferred_over_the_derivation(self):
        snapshot = build(
            cashflow=statement(
                **{
                    "Free Cash Flow": [70.0, 60.0, 50.0],
                    "Operating Cash Flow": [999.0] * 3,
                    "Capital Expenditure": [-1.0] * 3,
                }
            )
        )
        assert snapshot.free_cash_flow == 70.0
        assert not any("FCF derived" in note for note in snapshot.data_notes)

    def test_is_none_when_nothing_is_available(self):
        assert build().free_cash_flow is None


class TestFallbacks:
    def test_defaults_apply_when_statements_are_missing(self):
        snapshot = build(info={"totalDebt": 5e9})
        assert snapshot.tax_rate == 0.21
        assert snapshot.total_debt == 5e9  # taken from vendor info
        assert snapshot.beta is None
        assert snapshot.total_equity is None
        assert any("Beta missing" in note for note in snapshot.data_notes)
        assert any("Total debt taken from vendor info" in note for note in snapshot.data_notes)

    @pytest.mark.parametrize(
        ("info", "expected"),
        [
            ({"longName": "Long", "shortName": "Short"}, "Long"),
            ({"shortName": "Short"}, "Short"),
            ({}, "AAA"),
        ],
    )
    def test_name_falls_back_to_short_name_then_ticker(self, info, expected):
        assert build(info=info).name == expected

    def test_share_count_falls_back_to_the_balance_sheet(self):
        snapshot = build(balance=statement(**{"Ordinary Shares Number": [1e9, 9e8, 8e8]}))
        assert snapshot.shares_outstanding == 1e9
        assert snapshot.market_cap == pytest.approx(120.0 * 1e9)

    def test_reported_market_cap_is_preferred_over_the_derived_one(self):
        snapshot = build(info={"marketCap": 5e11, "sharesOutstanding": 1e9})
        assert snapshot.market_cap == 5e11

    def test_balance_sheet_debt_is_preferred_over_vendor_info(self):
        snapshot = build(info={"totalDebt": 5e9}, balance=statement(**{"Total Debt": [2e9, 2e9, 2e9]}))
        assert snapshot.total_debt == 2e9


class TestStatements:
    def test_canonical_lines_are_extracted_oldest_first(self):
        snapshot = build(
            income=statement(**{"Total Revenue": [300.0, 200.0, 100.0], "EBIT": [30.0, 20.0, 10.0]}),
            balance=statement(**{"Total Assets": [3e3, 2e3, 1e3], "Net PPE": [30.0, 20.0, 10.0]}),
            cashflow=statement(**{"Operating Cash Flow": [9.0, 8.0, 7.0]}),
        )

        assert list(snapshot.statements["revenue"].values) == [100.0, 200.0, 300.0]
        assert list(snapshot.statements["ebit"].values) == [10.0, 20.0, 30.0]
        assert snapshot.statements["net_ppe"].iloc[-1] == 30.0
        assert snapshot.statements["operating_cash_flow"].iloc[-1] == 9.0

    def test_label_fallbacks_are_used(self):
        snapshot = build(income=statement(**{"Operating Income": [30.0, 20.0, 10.0]}))
        assert snapshot.statements["ebit"].iloc[-1] == 30.0

    def test_lines_the_vendor_lacks_are_simply_absent(self):
        assert build().statements == {}
