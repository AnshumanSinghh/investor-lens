from __future__ import annotations

import pandas as pd

from investor_lens.infrastructure.market_data.statement_parsing import (
    extract_line_item,
    latest_value,
    normalize_price_series,
)
from support.yfinance_fakes import statement


class TestNormalizePriceSeries:
    def test_drops_timezone_and_keeps_the_last_duplicate_day(self):
        index = pd.DatetimeIndex(["2024-01-02 16:00", "2024-01-02 20:00", "2024-01-03 16:00"]).tz_localize(
            "UTC"
        )
        result = normalize_price_series(pd.Series([1.0, 2.0, 3.0], index=index))
        assert result.index.tz is None
        assert list(result.values) == [2.0, 3.0]
        assert list(result.index) == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]

    def test_sorts_ascending_and_drops_non_numeric_values(self):
        index = pd.to_datetime(["2024-01-03", "2024-01-01", "2024-01-02"])
        result = normalize_price_series(pd.Series([3.0, "n/a", None], index=index))
        assert list(result.index) == [pd.Timestamp("2024-01-03")]
        assert list(result.values) == [3.0]


class TestExtractLineItem:
    def test_sorts_oldest_first_and_falls_back_to_the_next_label(self):
        frame = statement(**{"Basic EPS": [3.0, 2.0, 1.0]})
        series = extract_line_item(frame, ["Diluted EPS", "Basic EPS"])
        assert list(series.values) == [1.0, 2.0, 3.0]

    def test_first_available_label_wins(self):
        frame = statement(**{"Diluted EPS": [3.0, 2.0, 1.0], "Basic EPS": [9.0, 9.0, 9.0]})
        assert latest_value(extract_line_item(frame, ["Diluted EPS", "Basic EPS"])) == 3.0

    def test_skips_a_label_whose_values_are_all_missing(self):
        frame = statement(**{"Diluted EPS": [None, None, None], "Basic EPS": [3.0, 2.0, 1.0]})
        assert latest_value(extract_line_item(frame, ["Diluted EPS", "Basic EPS"])) == 3.0

    def test_duplicate_row_labels_use_the_first_row(self):
        frame = pd.concat(
            [statement(**{"Basic EPS": [3.0, 2.0, 1.0]}), statement(**{"Basic EPS": [9.0, 9.0, 9.0]})]
        )
        assert latest_value(extract_line_item(frame, ["Basic EPS"])) == 3.0

    def test_missing_label_or_frame_yields_an_empty_series(self):
        frame = statement(**{"Basic EPS": [3.0, 2.0, 1.0]})
        assert extract_line_item(frame, ["Missing"]).empty
        assert extract_line_item(pd.DataFrame(), ["Basic EPS"]).empty
        assert extract_line_item(None, ["Basic EPS"]).empty


class TestLatestValue:
    def test_returns_the_last_element_as_float(self):
        assert latest_value(pd.Series([1, 2, 3])) == 3.0

    def test_none_for_an_empty_series(self):
        assert latest_value(pd.Series(dtype=float)) is None
