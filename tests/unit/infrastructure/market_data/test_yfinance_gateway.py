from __future__ import annotations

import importlib

import pandas as pd
import pytest

from investor_lens.config.settings import IngestionSettings
from investor_lens.domain.exceptions import DataFetchError, DataUnavailableError
from investor_lens.infrastructure.market_data import YFinanceGateway
from support.yfinance_fakes import FakeClient, FakeTicker, price_history, statement


def make_gateway(**tickers: FakeTicker) -> YFinanceGateway:
    return YFinanceGateway(IngestionSettings(), client=FakeClient(tickers))


def healthy_ticker(**overrides) -> FakeTicker:
    fields = {"info": {"shortName": "Alpha", "sharesOutstanding": 1e9}} | overrides
    return FakeTicker(price_history(), **fields)


def test_name_identifies_the_vendor():
    assert make_gateway().name == "yfinance"


class TestFetchAsset:
    def test_builds_a_snapshot_from_the_vendor_payload(self):
        snapshot = make_gateway(AAA=healthy_ticker()).fetch_asset("AAA")
        assert snapshot.ticker == "AAA"
        assert snapshot.price_close.index.tz is None
        assert snapshot.current_price == pytest.approx(120.0)

    def test_total_return_series_comes_from_adjusted_close(self):
        snapshot = make_gateway(AAA=healthy_ticker()).fetch_asset("AAA")
        assert snapshot.price_close.iloc[-1] == pytest.approx(120.0)
        assert snapshot.price_adjusted.iloc[-1] == pytest.approx(120.0 * 0.98)

    def test_requests_unadjusted_history_covering_the_configured_window(self):
        ticker = healthy_ticker()
        make_gateway(AAA=ticker).fetch_asset("AAA")

        (call,) = ticker.history_calls
        assert call["auto_adjust"] is False  # both Close and Adj Close are needed
        assert call["actions"] is False
        years_back = (pd.Timestamp.today() - pd.Timestamp(call["start"])).days / 365.25
        assert years_back == pytest.approx(IngestionSettings().history_years, abs=0.1)

    def test_without_prices_the_asset_is_unavailable(self):
        with pytest.raises(DataUnavailableError):
            make_gateway(AAA=FakeTicker(pd.DataFrame())).fetch_asset("AAA")

    def test_missing_adjusted_close_falls_back_to_close(self):
        ticker = FakeTicker(price_history().drop(columns="Adj Close"), info={"shortName": "Alpha"})
        snapshot = make_gateway(AAA=ticker).fetch_asset("AAA")
        assert snapshot.price_adjusted.iloc[-1] == pytest.approx(120.0)

    def test_all_missing_closes_are_unavailable(self):
        history = price_history()
        history["Close"] = float("nan")
        with pytest.raises(DataUnavailableError, match="Empty price series"):
            make_gateway(AAA=FakeTicker(history)).fetch_asset("AAA")

    def test_with_no_fundamentals_at_all_the_failure_is_retryable(self):
        with pytest.raises(DataFetchError) as excinfo:
            make_gateway(AAA=FakeTicker(price_history())).fetch_asset("AAA")
        assert not isinstance(excinfo.value, DataUnavailableError)  # likely throttling, so retry

    def test_one_failing_statement_degrades_to_a_note_instead_of_failing_the_asset(self):
        ticker = healthy_ticker(
            income=RuntimeError("income down"),
            balance=statement(**{"Total Debt": [2e9, 2e9, 2e9], "Stockholders Equity": [1e10, 9e9, 8e9]}),
        )
        snapshot = make_gateway(AAA=ticker).fetch_asset("AAA")

        assert snapshot.total_equity == 1e10
        assert snapshot.eps_history.empty
        assert any(
            "income_stmt unavailable" in note and "income down" in note for note in snapshot.data_notes
        )

    def test_failing_info_is_tolerated_when_statements_exist(self):
        ticker = healthy_ticker(
            info=RuntimeError("info down"), balance=statement(**{"Total Debt": [1.0, 1.0, 1.0]})
        )
        snapshot = make_gateway(AAA=ticker).fetch_asset("AAA")
        assert snapshot.name == "AAA"  # no vendor name available
        assert any("info unavailable" in note for note in snapshot.data_notes)


class TestFetchRiskFreeRate:
    def test_is_converted_from_percent_to_a_decimal(self):
        quote = pd.DataFrame({"Close": [4.1, 4.25]})
        assert make_gateway(**{"^TNX": FakeTicker(quote)}).fetch_risk_free_rate() == pytest.approx(0.0425)

    def test_uses_the_latest_non_missing_quote(self):
        quote = pd.DataFrame({"Close": [4.1, 4.25, None]})
        assert make_gateway(**{"^TNX": FakeTicker(quote)}).fetch_risk_free_rate() == pytest.approx(0.0425)

    @pytest.mark.parametrize("quote", [400.0, 0.0, -1.0])
    def test_implausible_rates_are_rejected(self, quote):
        with pytest.raises(DataUnavailableError, match="Implausible"):
            make_gateway(**{"^TNX": FakeTicker(pd.DataFrame({"Close": [quote]}))}).fetch_risk_free_rate()

    def test_missing_quote_is_unavailable(self):
        with pytest.raises(DataUnavailableError):
            make_gateway(**{"^TNX": FakeTicker(pd.DataFrame())}).fetch_risk_free_rate()


class TestConfigurableReferenceTickers:
    def test_the_configured_benchmark_ticker_is_requested(self):
        gateway = YFinanceGateway(
            IngestionSettings(benchmark_ticker="^NSEI"),
            client=FakeClient({"^NSEI": FakeTicker(price_history())}),
        )
        assert gateway.fetch_benchmark_prices().iloc[-1] == pytest.approx(120.0 * 0.98)

    def test_a_quote_already_in_decimal_form_is_not_rescaled(self):
        settings = IngestionSettings(risk_free_ticker="IN10Y", risk_free_quote_in_percent=False)
        client = FakeClient({"IN10Y": FakeTicker(pd.DataFrame({"Close": [0.067]}))})
        assert YFinanceGateway(settings, client=client).fetch_risk_free_rate() == pytest.approx(0.067)

    def test_no_ticker_means_unavailable_so_the_fallback_applies(self):
        gateway = YFinanceGateway(IngestionSettings(risk_free_ticker=""), client=FakeClient({}))
        with pytest.raises(DataUnavailableError, match="No risk-free ticker"):
            gateway.fetch_risk_free_rate()

    def test_a_quote_of_only_missing_values_is_unavailable(self):
        quote = pd.DataFrame({"Close": [None, None]})
        with pytest.raises(DataUnavailableError):
            make_gateway(**{"^TNX": FakeTicker(quote)}).fetch_risk_free_rate()


class TestFetchBenchmarkPrices:
    def test_prefers_adjusted_close(self):
        prices = make_gateway(**{"^GSPC": FakeTicker(price_history())}).fetch_benchmark_prices()
        assert prices.iloc[-1] == pytest.approx(120.0 * 0.98)

    def test_falls_back_to_close_when_there_is_no_adjusted_column(self):
        history = price_history().drop(columns="Adj Close")
        prices = make_gateway(**{"^GSPC": FakeTicker(history)}).fetch_benchmark_prices()
        assert prices.iloc[-1] == pytest.approx(120.0)

    def test_missing_history_is_unavailable(self):
        with pytest.raises(DataUnavailableError):
            make_gateway(**{"^GSPC": FakeTicker(pd.DataFrame())}).fetch_benchmark_prices()


def test_a_missing_yfinance_install_surfaces_as_import_error(monkeypatch):
    """The CLI relies on this to print an install hint and exit with a distinct code."""

    def fake_import(name, *args, **kwargs):
        raise ImportError(f"No module named {name!r}")

    monkeypatch.setattr(importlib, "import_module", fake_import)
    with pytest.raises(ImportError):
        YFinanceGateway(IngestionSettings())
