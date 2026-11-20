# Investor Lens

Screens equities through quantitative interpretations of seven investing philosophies plus a news flag and writes an
LLM-ready report, `market_intelligence_payload.md`:

| Investor | What the code checks | Gate? |
|---|---|---|
| **Warren Buffett** | Two-stage DCF intrinsic value; price/IV <= 0.80 (a 20% margin of safety); debt/equity <= 0.50 | yes |
| **Howard Marks** | Valuation z-score (P/E and P/B vs. own history) <= +1.5; price <= 1.25 x SMA200 | yes |
| **Ray Dalio** | 90-day annualised volatility; Sharpe >= 1.0 vs. the risk-free rate; 12-month correlation to the S&P 500 and across the qualified set | no: flags and scales weights (risk parity) |
| **Benjamin Graham** | P/E <= 15 on 3-year average EPS; P/B <= 1.5 (or P/E x P/B <= 22.5); no loss years; EPS CAGR >= 3% | no: advisory |
| **Peter Lynch** | PEG <= 1; EPS growth within 10-50%; debt/equity <= 0.80 | no: advisory |
| **Joel Greenblatt** | Magic Formula: earnings yield (EBIT/EV) >= 8% and return on capital >= 25%; financials and utilities skipped | no: advisory |
| **Joseph Piotroski** | F-score >= 7 of 9 financial-strength signals; unknown signals keep the result inconclusive | no: advisory |
| **News flow** | Recent headlines scanned for risk terms (lawsuit, probe, downgrade, ...); the headlines themselves are included for you or Claude to read | no: advisory flag |

The extra lenses are advisory by default (they never change the verdict) because absolute caps exclude
most large caps and keyword/ratio screens are blunt. To make one disqualifying, set `gating = True` on its
rule class. Greenblatt's book ranks a whole universe; here absolute cut-offs are used instead.

Every threshold is echoed into the output so a downstream LLM can interpret the verdicts without
guessing. This is a **screening tool, not investment advice**: it is only as good as Yahoo Finance's
free data and the simplifications listed under [Limitations](#limitations).

## Try it in 30 seconds (offline, no Yahoo needed)

```bash
pip install -e ".[dev]"
investor-lens --source files --data-dir examples/data --tickers DEMOA,DEMOB --output demo.md
```
The sample data is synthetic (invented companies); it exercises every lens, including news.

## Quick start

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"              # runtime only: pip install -e .

investor-lens                        # screens the default tickers
# or
python -m investor_lens --tickers AAPL,MSFT,KO --output out/payload.md
```

The run is deliberately slow: there is a 2-second pause between Yahoo requests to avoid HTTP 429
throttling, so 8 tickers take roughly 30-60 seconds.

### Options

| Flag | Meaning |
|---|---|
| `--tickers` | Comma-separated symbols (overrides `LENS_TICKERS`) |
| `--output` | Output path (overrides `LENS_OUTPUT_PATH`) |
| `--source` | `yfinance` or `files` (overrides `LENS_DATA_SOURCE`) |
| `--data-dir` | Folder for the `files` source (overrides `LENS_DATA_DIR`) |
| `--benchmark` | Benchmark index ticker (overrides `LENS_BENCHMARK_TICKER`) |
| `--risk-free-ticker` | Risk-free yield ticker, or `none` (overrides `LENS_RISK_FREE_TICKER`) |
| `--log-level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Exit codes: `0` success, `1` run failed, `2` a dependency (yfinance) is missing.

### Configuration

Environment variables, all optional (see `.env.example`). The app does not read `.env` itself; load it
in your shell with `set -a; source .env; set +a`.

| Variable | Default |
|---|---|
| `LENS_TICKERS` | `AAPL,MSFT,BRK-B,KO,JNJ,PG,JPM,XOM` |
| `LENS_OUTPUT_PATH` | `market_intelligence_payload.md` |
| `LENS_LOG_LEVEL` / `LENS_LOG_FILE` | `INFO` / none |
| `LENS_DATA_SOURCE` | `yfinance` (or `files`, see below) |
| `LENS_DATA_DIR` | `data` (folder read by the `files` source) |
| `LENS_BENCHMARK_TICKER` | `^GSPC` (S&P 500). Nifty 50: `^NSEI` |
| `LENS_RISK_FREE_TICKER` | `^TNX` (US 10-year). `none` = always use `LENS_RISK_FREE_FALLBACK` |
| `LENS_RISK_FREE_QUOTE_IN_PERCENT` | `true` (`^TNX` quotes 4.25 for 4.25%) |
| `LENS_NEWS_ENABLED` / `LENS_NEWS_MAX_ITEMS` | `true` / `10` |
| `LENS_FETCH_DELAY_SECONDS` | `2` |
| `LENS_MAX_RETRIES` | `3` (exponential backoff) |
| `LENS_RISK_FREE_FALLBACK` | `0.04` (used if `^TNX` is unavailable) |
| `LENS_EQUITY_RISK_PREMIUM`, `LENS_TERMINAL_GROWTH_CAP`, `LENS_DCF_YEARS`, `LENS_GROWTH_CAP`, `LENS_GROWTH_FLOOR` | DCF assumptions |

The pass/fail thresholds (0.80, 0.50, 1.5, 1.25, 1.0, ...) live in `domain/parameters.py` and are
changed in code; they are not environment-configurable.

## Reading the output

`market_intelligence_payload.md` contains a reading guide, a summary table, and one fenced JSON block
(strict JSON: no NaN or Infinity) with `metadata`, `portfolio` and `assets`.

Verdicts: `QUALIFIED` (passed every gating rule), `DISQUALIFIED` (failed at least one),
`INSUFFICIENT_DATA` (a gating check could not be computed), `DATA_UNAVAILABLE` (the fetch failed).
A check with `passed: null` means *could not be computed*, not *passed*; a fallback score is applied
and recorded.

## Failure behaviour

One bad ticker never aborts a run. Fetch failures are retried with backoff; if data stays
unavailable the asset is reported as `DATA_UNAVAILABLE` with its error. A failing risk-free or
benchmark fetch falls back to a constant and is noted in `metadata.market_data_notes`. A crashing
rule or allocator is contained and recorded.

## Architecture

Clean Architecture; dependencies point inward only, and a test enforces it
(`tests/architecture/`). See [docs/architecture.md](docs/architecture.md).

```
domain  <-  application  <-  infrastructure / config  <-  bootstrap / cli
```

## Development

```bash
ruff check src tests && ruff format --check src tests
mypy                          # strict, src only
pytest --cov                  # coverage gate: 95%
pre-commit install            # optional: run the above on every commit
```

Live smoke test against real Yahoo Finance (off by default):
`LENS_RUN_LIVE=1 pytest -m live`.

### Adding a new investor rule

1. Subclass `FilterRule` in `domain/rules/` and implement `_evaluate` (see `graham.py` for a compact example).
2. Register it in `bootstrap.build_rules`.

Nothing else changes: the pipeline, policy, allocator and report iterate over whatever rules exist.

### Indian stocks (NSE/BSE)

```bash
export LENS_BENCHMARK_TICKER='^NSEI'          # Nifty 50
export LENS_RISK_FREE_TICKER=none             # no reliable Yahoo ticker for the Indian 10-year yield
export LENS_RISK_FREE_FALLBACK=0.067          # set to the current 10-year G-Sec yield
investor-lens --tickers RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS
```
Yahoo suffixes: `.NS` (NSE), `.BO` (BSE). This has not been tested against live Yahoo from the build
environment, and Yahoo's fundamentals coverage for Indian companies can be patchy; gaps show up as
`INSUFFICIENT_DATA` or notes, not silent passes. Financial companies (banks, NBFCs) are skipped by the
Greenblatt rule.

### News

Each ticker's recent headlines are attached under `assets[].news`, and the `News flow` rule flags risk
keywords. Keywords miss context and negation, so treat the flag as "read these", and hand the report to
Claude to judge the headlines. News costs one extra Yahoo request per ticker (about double the run time).
Disable with `LENS_NEWS_ENABLED=false`. Yahoo's news schema has changed over time and the parser accepts
both layouts, but it is untested against live Yahoo. With `--source files`, put headlines in
`<TICKER>.news.json`.

### Data sources

- `yfinance` (default): live Yahoo Finance data, throttled and retried.
- `files`: offline, reproducible runs from a folder, e.g. `investor-lens --source files --data-dir data`.
  Layout: `<TICKER>.prices.csv` (`date,close[,adj_close]`), optional `<TICKER>.json` fundamentals,
  `_GSPC.prices.csv` for the benchmark (`^` becomes `_`), and `_market.json` with `{"risk_free_rate": 0.043}`.
  This is also the bridge for any vendor that can export CSV/JSON (Bloomberg, Refinitiv, your broker).
  The exact format is documented at the top of `infrastructure/market_data/file_gateway.py`.
- Another vendor: implement `MarketDataGateway` (`application/ports.py`) and add one line to
  `GATEWAY_FACTORIES` in `bootstrap.py`; select it with `LENS_DATA_SOURCE`.

## Limitations

- Yahoo Finance provides roughly 4-5 years of annual fundamentals, so valuation z-scores use few
  observations (the count is reported in the payload).
- Intrinsic value uses current free cash flow and clamped trailing EPS growth; net debt is not
  subtracted. Treat it as a screening estimate, not a price target.
- Free data can be wrong, stale or missing; the tool reports gaps rather than hiding them.
- Yahoo's unofficial API can change or rate-limit without notice.
