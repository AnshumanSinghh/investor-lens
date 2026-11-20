from __future__ import annotations

import json

import pytest

from investor_lens.application.ports import MarketDataGateway
from investor_lens.config.settings import IngestionSettings
from investor_lens.domain.exceptions import DataUnavailableError
from investor_lens.infrastructure.market_data import FileGateway
from support.builders import oscillating_prices
from support.data_dir import FUNDAMENTALS, make_data_dir, write_prices


@pytest.fixture
def directory(tmp_path):
    return make_data_dir(tmp_path / "data", tickers=("AAA", "BRK-B"))


@pytest.fixture
def gateway(directory) -> FileGateway:
    return FileGateway(directory, IngestionSettings())


def test_is_a_market_data_gateway_and_names_its_source(gateway, directory):
    assert isinstance(gateway, MarketDataGateway)
    assert gateway.name == f"files:{directory}"


class TestFetchAsset:
    def test_maps_files_to_a_snapshot(self, gateway):
        snapshot = gateway.fetch_asset("AAA")

        assert (snapshot.name, snapshot.sector, snapshot.currency) == ("Alpha Corp", "Tech", "USD")
        assert snapshot.current_price == pytest.approx(float(oscillating_prices().iloc[-1]))
        assert snapshot.total_equity == 1e10
        assert snapshot.tax_rate == 0.2
        assert list(snapshot.eps_history.values) == [2.0, 2.2, 2.4, 2.6, 2.9]
        assert snapshot.eps_history.index.is_monotonic_increasing

    def test_market_cap_is_derived_from_price_and_shares(self, gateway):
        snapshot = gateway.fetch_asset("AAA")
        assert snapshot.market_cap == pytest.approx(snapshot.current_price * 1e9)

    def test_adjusted_close_is_used_when_the_file_has_one(self, directory):
        prices = oscillating_prices()
        write_prices(directory / "ADJ.prices.csv", prices, adjusted=prices * 0.9)
        snapshot = FileGateway(directory, IngestionSettings()).fetch_asset("ADJ")

        assert snapshot.price_close.iloc[-1] == pytest.approx(float(prices.iloc[-1]))
        assert snapshot.price_adjusted.iloc[-1] == pytest.approx(float(prices.iloc[-1]) * 0.9)

    def test_prices_without_fundamentals_still_work_with_a_note(self, directory):
        write_prices(directory / "PX.prices.csv", oscillating_prices())
        snapshot = FileGateway(directory, IngestionSettings()).fetch_asset("PX")

        assert snapshot.name == "PX"
        assert snapshot.total_debt is None and snapshot.eps_history.empty
        assert any("No fundamentals file" in note for note in snapshot.data_notes)

    def test_missing_optional_fields_default_sensibly(self, directory):
        (directory / "AAA.json").write_text(json.dumps({"eps_history": FUNDAMENTALS["eps_history"]}))
        snapshot = FileGateway(directory, IngestionSettings(default_tax_rate=0.25)).fetch_asset("AAA")

        assert snapshot.tax_rate == 0.25
        assert snapshot.beta is None
        assert any("Beta missing" in note for note in snapshot.data_notes)

    def test_tickers_with_dashes_are_supported(self, gateway):
        assert gateway.fetch_asset("BRK-B").ticker == "BRK-B"

    @pytest.mark.parametrize("bad_value", ["n/a", None, "abc"])
    def test_unparseable_numbers_are_treated_as_missing(self, directory, bad_value):
        (directory / "AAA.json").write_text(json.dumps({**FUNDAMENTALS, "total_debt": bad_value}))
        assert FileGateway(directory, IngestionSettings()).fetch_asset("AAA").total_debt is None


class TestUnavailableData:
    def test_unknown_ticker(self, gateway):
        with pytest.raises(DataUnavailableError, match="No price file"):
            gateway.fetch_asset("NOPE")

    def test_price_file_without_required_columns(self, directory, gateway):
        (directory / "BAD.prices.csv").write_text("day,value\n2024-01-01,1\n")
        with pytest.raises(DataUnavailableError, match="Malformed price file"):
            gateway.fetch_asset("BAD")

    def test_price_file_without_usable_rows(self, directory, gateway):
        (directory / "EMPTY.prices.csv").write_text("date,close\n")
        with pytest.raises(DataUnavailableError):
            gateway.fetch_asset("EMPTY")

    def test_corrupt_fundamentals_json(self, directory, gateway):
        (directory / "AAA.json").write_text("{not json")
        with pytest.raises(DataUnavailableError, match="Unreadable JSON"):
            gateway.fetch_asset("AAA")

    def test_fundamentals_json_must_be_an_object(self, directory, gateway):
        (directory / "AAA.json").write_text("[1, 2]")
        with pytest.raises(DataUnavailableError, match="JSON object"):
            gateway.fetch_asset("AAA")


class TestBenchmarkAndRiskFree:
    def test_benchmark_comes_from_the_configured_ticker_file(self, gateway):
        assert len(gateway.fetch_benchmark_prices()) == 800

    def test_missing_benchmark_is_unavailable(self, tmp_path):
        with pytest.raises(DataUnavailableError):
            FileGateway(tmp_path, IngestionSettings()).fetch_benchmark_prices()

    def test_risk_free_rate_is_read_as_a_decimal(self, gateway):
        assert gateway.fetch_risk_free_rate() == pytest.approx(0.043)

    @pytest.mark.parametrize("value", [4.3, 0, -0.01, None, "x"])
    def test_implausible_or_missing_rate_is_unavailable(self, directory, gateway, value):
        (directory / "_market.json").write_text(json.dumps({"risk_free_rate": value}))
        with pytest.raises(DataUnavailableError):
            gateway.fetch_risk_free_rate()

    def test_missing_market_file_is_unavailable(self, tmp_path):
        with pytest.raises(DataUnavailableError, match="Missing file"):
            FileGateway(tmp_path, IngestionSettings()).fetch_risk_free_rate()


class TestStatementsFromFiles:
    def test_statements_are_parsed_into_ascending_series(self, directory):
        payload = {
            **FUNDAMENTALS,
            "statements": {
                "ebit": {"2025-12-31": 30.0, "2024-12-31": 20.0},
                "empty": {},
                "junk": {"2025-12-31": "n/a"},
            },
        }
        (directory / "AAA.json").write_text(json.dumps(payload))
        statements = FileGateway(directory, IngestionSettings()).fetch_asset("AAA").statements

        assert list(statements["ebit"].values) == [20.0, 30.0]
        assert set(statements) == {"ebit"}  # empty and non-numeric lines are dropped

    @pytest.mark.parametrize("raw", [None, [], "x"])
    def test_a_non_object_statements_value_is_ignored(self, directory, raw):
        (directory / "AAA.json").write_text(json.dumps({**FUNDAMENTALS, "statements": raw}))
        assert FileGateway(directory, IngestionSettings()).fetch_asset("AAA").statements == {}
