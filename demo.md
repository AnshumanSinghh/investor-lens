# Market Intelligence Payload

Generated (UTC): 2026-11-20 08:56 | Risk-free: 4.30% (live)

## Reading guide
- `verdict`: QUALIFIED (passed every gating rule), DISQUALIFIED (failed >= 1), INSUFFICIENT_DATA (a gating check could not run), DATA_UNAVAILABLE (fetch failed).
- Buffett and Marks rules gate. Dalio, Graham and Lynch are advisory: they never change the verdict (Dalio also scales `suggested_weight`); read their `passed` flags and metrics as supporting evidence.
- `assets[].news` holds recent headlines. The `News flow` rule only flags risk keywords; read the headlines themselves and judge their meaning, since keywords miss context and negation.
- `score` is 0-1 (higher is better); fallback scores mean the calculation did not run.
- `metadata.thresholds` lists every cut-off used. `metadata.limitations` lists known data caveats.

## Summary

| Ticker | Verdict | Score | Price | Intrinsic Value | Price/IV | Z (valuation) | Price/SMA200 | Sharpe | Weight |
|---|---|---|---|---|---|---|---|---|---|
| DEMOA | QUALIFIED | 0.60 | 37.98 | 85.71 | 0.44 | -0.57 | 0.92 | -0.44 | 100.0% |
| DEMOB | DISQUALIFIED | 0.62 | 69.64 | 63.76 | 1.09 | -1.70 | 0.96 | -0.31 | n/a |

## Data (JSON)

```json
{
  "metadata": {
    "generated_at_utc": "2026-11-20T08:56:38.927233+00:00",
    "tool_version": "1.2.0",
    "data_source": "files:examples\\data",
    "tickers_requested": [
      "DEMOA",
      "DEMOB"
    ],
    "verdict_counts": {
      "QUALIFIED": 1,
      "DISQUALIFIED": 1,
      "INSUFFICIENT_DATA": 0,
      "DATA_UNAVAILABLE": 0
    },
    "risk_free_rate": 0.043,
    "risk_free_source": "live",
    "benchmark": "^GSPC",
    "market_data_notes": [],
    "thresholds": {
      "max_price_to_intrinsic_value": 0.8,
      "max_leverage_debt_to_equity": 0.5,
      "max_valuation_z_score": 1.5,
      "max_price_to_sma200": 1.25,
      "min_sharpe_ratio": 1.0,
      "max_correlation_to_benchmark": 0.8,
      "max_avg_portfolio_correlation": 0.7,
      "equity_risk_premium": 0.05,
      "terminal_growth_cap": 0.025,
      "dcf_explicit_years": 10,
      "growth_clamp": [
        -0.1,
        0.15
      ],
      "volatility_window_days": 90,
      "correlation_lookback_days": 252,
      "valuation_window_years": 10,
      "fundamentals_reporting_lag_days": 90,
      "graham_max_pe": 15.0,
      "graham_max_pb": 1.5,
      "graham_max_pe_times_pb": 22.5,
      "lynch_max_peg": 1.0,
      "lynch_growth_band": [
        0.1,
        0.5
      ],
      "lynch_max_debt_to_equity": 0.8,
      "greenblatt_min_earnings_yield": 0.08,
      "greenblatt_min_return_on_capital": 0.25,
      "piotroski_min_f_score": 7,
      "news_max_risk_headlines": 1,
      "news_headlines_per_ticker": 10
    },
    "limitations": [
      "Yahoo Finance supplies ~4-5 years of annual fundamentals; P/E and P/B z-scores use all available point-in-time observations within the 10Y price window (see *_observations).",
      "Intrinsic value uses FCF0 and trailing EPS growth (clamped); net debt is not subtracted. Treat it as a screening estimate, not a price target.",
      "passed=null means a check could not be computed (fallback score applied), not that it passed."
    ]
  },
  "portfolio": {
    "method": "inverse 90d annualized volatility x penalty scalars (low Sharpe, high benchmark correlation, high avg correlation to other qualified assets), normalized to 1",
    "qualified_tickers": [
      "DEMOA"
    ],
    "correlation_matrix": {
      "DEMOA": {
        "DEMOA": null
      }
    },
    "suggested_weights": {
      "DEMOA": 1.0
    }
  },
  "assets": [
    {
      "ticker": "DEMOA",
      "name": "Demo Industrial Co (synthetic)",
      "sector": "Industrials",
      "currency": "USD",
      "current_price": 37.98,
      "verdict": "QUALIFIED",
      "composite_score": 0.599467,
      "suggested_weight": 1.0,
      "avg_correlation_to_portfolio": null,
      "weight_adjustments": [
        "Sharpe -0.44 < 1.0: x0.25"
      ],
      "rules": [
        {
          "rule": "buffett_margin_of_safety_and_leverage",
          "investor": "Warren Buffett",
          "gating": true,
          "passed": true,
          "score": 0.94,
          "status": "OK",
          "metrics": {
            "leverage_ratio": 0.06,
            "eps_growth_trailing_raw": 0.057371,
            "free_cash_flow_0": 4000000000.0,
            "growth_used": 0.057371,
            "beta_used": 0.9,
            "risk_free_rate": 0.043,
            "cost_of_equity_capm": 0.088,
            "wacc_unfloored": 0.086257,
            "wacc_used": 0.086257,
            "terminal_growth": 0.025,
            "wacc_components": {
              "capital_structure": "levered",
              "cost_of_equity": 0.088,
              "pre_tax_cost_of_debt": 0.053333,
              "after_tax_cost_of_debt": 0.042133,
              "equity_weight": 0.962006,
              "debt_weight": 0.037994
            },
            "pv_explicit_total": 34592490853.60143,
            "pv_terminal_total": 51117952892.690346,
            "intrinsic_value_per_share": 85.710444,
            "margin_of_safety": 0.55688,
            "price_to_intrinsic_value": 0.44312,
            "checks": {
              "leverage": true,
              "margin_of_safety": true
            }
          },
          "reasons": []
        },
        {
          "rule": "marks_cycle_position",
          "investor": "Howard Marks",
          "gating": true,
          "passed": true,
          "score": 0.845307,
          "status": "OK",
          "metrics": {
            "current_pe": 15.192,
            "mean_pe_history": 16.046907,
            "std_pe_history": 1.495008,
            "pe_observations": 36,
            "current_pb": null,
            "mean_pb_history": null,
            "std_pb_history": null,
            "pb_observations": 0,
            "z_pe": -0.571841,
            "z_pb": null,
            "z_valuation": -0.571841,
            "z_valuation_basis": "P/E",
            "sma_200": 41.4478,
            "price_to_sma200": 0.916333,
            "checks": {
              "valuation_z": true,
              "sma_extension": true
            }
          },
          "reasons": []
        },
        {
          "rule": "dalio_risk_adjusted_allocation",
          "investor": "Ray Dalio",
          "gating": false,
          "passed": false,
          "score": 0.495364,
          "status": "OK",
          "metrics": {
            "annualized_return_12m": -0.043566,
            "risk_free_rate": 0.043,
            "observations_12m": 252,
            "annualized_volatility_90d": 0.194867,
            "sharpe_ratio": -0.444231,
            "correlation_observations": 252,
            "correlation_to_benchmark": 0.009271,
            "flags": [
              "LOW_SHARPE"
            ],
            "checks": {
              "sharpe": false,
              "benchmark_correlation": true
            }
          },
          "reasons": [
            "Sharpe -0.44 < 1.00."
          ]
        },
        {
          "rule": "graham_defensive_value",
          "investor": "Benjamin Graham",
          "gating": false,
          "passed": false,
          "score": 0.608243,
          "status": "OK",
          "metrics": {
            "average_eps": 2.35,
            "pe_3y_average": 16.161702,
            "book_value_per_share": 25.0,
            "price_to_book": 1.5192,
            "pe_times_pb": 24.552858,
            "graham_number": 36.357599,
            "price_to_graham_number": 1.044623,
            "loss_years": 0,
            "eps_years_observed": 5,
            "eps_cagr": 0.057371,
            "checks": {
              "earnings_multiple": false,
              "asset_multiple": false,
              "earnings_stability": true,
              "earnings_growth": true
            }
          },
          "reasons": [
            "P/E 16.2 (3y average EPS) exceeds 15.0.",
            "P/B 1.52 > 1.50 and P/E x P/B above 22.5."
          ]
        },
        {
          "rule": "lynch_growth_at_reasonable_price",
          "investor": "Peter Lynch",
          "gating": false,
          "passed": false,
          "score": 0.308333,
          "status": "OK",
          "metrics": {
            "eps_growth": 0.057371,
            "pe": 15.192,
            "peg": 2.648016,
            "debt_to_equity": 0.06,
            "checks": {
              "growth_band": false,
              "peg": false,
              "leverage": true
            }
          },
          "reasons": [
            "EPS growth 5.7% outside 10%-50%.",
            "PEG 2.65 exceeds 1.00."
          ]
        },
        {
          "rule": "greenblatt_magic_formula",
          "investor": "Joel Greenblatt",
          "gating": false,
          "passed": true,
          "score": 0.598492,
          "status": "OK",
          "metrics": {
            "ebit": 3800000000.0,
            "enterprise_value": 36980000000.0,
            "earnings_yield": 0.102758,
            "net_working_capital": 2200000000.0,
            "invested_capital": 13700000000.0,
            "return_on_capital": 0.277372,
            "checks": {
              "earnings_yield": true,
              "return_on_capital": true
            }
          },
          "reasons": []
        },
        {
          "rule": "piotroski_f_score",
          "investor": "Joseph Piotroski",
          "gating": false,
          "passed": true,
          "score": 1.0,
          "status": "OK",
          "metrics": {
            "f_score": 9,
            "unknown_signals": 0,
            "best_possible_f_score": 9,
            "signals": {
              "roa_positive": true,
              "operating_cash_flow_positive": true,
              "roa_improving": true,
              "cash_flow_exceeds_net_income": true,
              "leverage_falling": true,
              "current_ratio_improving": true,
              "no_new_shares": true,
              "gross_margin_improving": true,
              "asset_turnover_improving": true
            },
            "checks": {
              "f_score": true
            }
          },
          "reasons": []
        },
        {
          "rule": "news_red_flags",
          "investor": "News flow",
          "gating": false,
          "passed": null,
          "score": 0.0,
          "status": "FALLBACK",
          "metrics": {
            "headline_count": 0,
            "checks": {
              "red_flag_headlines": null
            }
          },
          "reasons": [
            "No headlines available; news not assessed."
          ]
        }
      ],
      "news": [],
      "data_quality_notes": []
    },
    {
      "ticker": "DEMOB",
      "name": "Demo Software Co (synthetic)",
      "sector": "Technology",
      "currency": "USD",
      "current_price": 69.64,
      "verdict": "DISQUALIFIED",
      "composite_score": 0.619899,
      "suggested_weight": null,
      "avg_correlation_to_portfolio": null,
      "weight_adjustments": [],
      "rules": [
        {
          "rule": "buffett_margin_of_safety_and_leverage",
          "investor": "Warren Buffett",
          "gating": true,
          "passed": false,
          "score": 0.333333,
          "status": "OK",
          "metrics": {
            "leverage_ratio": 0.166667,
            "eps_growth_trailing_raw": 0.257433,
            "free_cash_flow_0": 1100000000.0,
            "growth_used": 0.15,
            "beta_used": 1.4,
            "risk_free_rate": 0.043,
            "cost_of_equity_capm": 0.113,
            "wacc_unfloored": 0.11099,
            "wacc_used": 0.11099,
            "terminal_growth": 0.025,
            "wacc_components": {
              "capital_structure": "levered",
              "cost_of_equity": 0.113,
              "pre_tax_cost_of_debt": 0.05,
              "after_tax_cost_of_debt": 0.041,
              "equity_weight": 0.972083,
              "debt_weight": 0.027917
            },
            "pv_explicit_total": 13364617770.402025,
            "pv_terminal_total": 18515948174.96095,
            "intrinsic_value_per_share": 63.761132,
            "margin_of_safety": -0.092201,
            "price_to_intrinsic_value": 1.092201,
            "checks": {
              "leverage": true,
              "margin_of_safety": false
            }
          },
          "reasons": [
            "Price/IV 1.09 > 0.80: margin of safety below 20%."
          ]
        },
        {
          "rule": "marks_cycle_position",
          "investor": "Howard Marks",
          "gating": true,
          "passed": true,
          "score": 1.0,
          "status": "OK",
          "metrics": {
            "current_pe": 27.856,
            "mean_pe_history": 33.724812,
            "std_pe_history": 3.460038,
            "pe_observations": 36,
            "current_pb": null,
            "mean_pb_history": null,
            "std_pb_history": null,
            "pb_observations": 0,
            "z_pe": -1.69617,
            "z_pb": null,
            "z_valuation": -1.69617,
            "z_valuation_basis": "P/E",
            "sma_200": 72.2964,
            "price_to_sma200": 0.963257,
            "checks": {
              "valuation_z": true,
              "sma_extension": true
            }
          },
          "reasons": []
        },
        {
          "rule": "dalio_risk_adjusted_allocation",
          "investor": "Ray Dalio",
          "gating": false,
          "passed": false,
          "score": 0.48059,
          "status": "OK",
          "metrics": {
            "annualized_return_12m": -0.052775,
            "risk_free_rate": 0.043,
            "observations_12m": 252,
            "annualized_volatility_90d": 0.310769,
            "sharpe_ratio": -0.308187,
            "correlation_observations": 252,
            "correlation_to_benchmark": 0.03882,
            "flags": [
              "LOW_SHARPE"
            ],
            "checks": {
              "sharpe": false,
              "benchmark_correlation": true
            }
          },
          "reasons": [
            "Sharpe -0.31 < 1.00."
          ]
        },
        {
          "rule": "graham_defensive_value",
          "investor": "Benjamin Graham",
          "gating": false,
          "passed": false,
          "score": 0.5,
          "status": "OK",
          "metrics": {
            "average_eps": 2.033333,
            "pe_3y_average": 34.24918,
            "book_value_per_share": 12.0,
            "price_to_book": 5.803333,
            "pe_times_pb": 198.75941,
            "graham_number": 23.430749,
            "price_to_graham_number": 2.972163,
            "loss_years": 0,
            "eps_years_observed": 5,
            "eps_cagr": 0.257433,
            "checks": {
              "earnings_multiple": false,
              "asset_multiple": false,
              "earnings_stability": true,
              "earnings_growth": true
            }
          },
          "reasons": [
            "P/E 34.2 (3y average EPS) exceeds 15.0.",
            "P/B 5.80 > 1.50 and P/E x P/B above 22.5."
          ]
        },
        {
          "rule": "lynch_growth_at_reasonable_price",
          "investor": "Peter Lynch",
          "gating": false,
          "passed": false,
          "score": 0.730263,
          "status": "OK",
          "metrics": {
            "eps_growth": 0.257433,
            "pe": 27.856,
            "peg": 1.082066,
            "debt_to_equity": 0.166667,
            "checks": {
              "growth_band": true,
              "peg": false,
              "leverage": true
            }
          },
          "reasons": [
            "PEG 1.08 exceeds 1.00."
          ]
        },
        {
          "rule": "greenblatt_magic_formula",
          "investor": "Joel Greenblatt",
          "gating": false,
          "passed": false,
          "score": 0.692782,
          "status": "OK",
          "metrics": {
            "ebit": 2000000000.0,
            "enterprise_value": 32420000000.0,
            "earnings_yield": 0.06169,
            "net_working_capital": 200000000.0,
            "invested_capital": 800000000.0,
            "return_on_capital": 2.5,
            "checks": {
              "earnings_yield": false,
              "return_on_capital": true
            }
          },
          "reasons": [
            "Earnings yield 6.2% below 8.0%."
          ]
        },
        {
          "rule": "piotroski_f_score",
          "investor": "Joseph Piotroski",
          "gating": false,
          "passed": true,
          "score": 0.888889,
          "status": "OK",
          "metrics": {
            "f_score": 8,
            "unknown_signals": 0,
            "best_possible_f_score": 8,
            "signals": {
              "roa_positive": true,
              "operating_cash_flow_positive": true,
              "roa_improving": true,
              "cash_flow_exceeds_net_income": true,
              "leverage_falling": true,
              "current_ratio_improving": true,
              "no_new_shares": false,
              "gross_margin_improving": true,
              "asset_turnover_improving": true
            },
            "checks": {
              "f_score": true
            }
          },
          "reasons": []
        },
        {
          "rule": "news_red_flags",
          "investor": "News flow",
          "gating": false,
          "passed": false,
          "score": 0.333333,
          "status": "OK",
          "metrics": {
            "headline_count": 3,
            "risk_headline_count": 2,
            "positive_headline_count": 0,
            "risk_headlines": [
              {
                "title": "Analyst downgrade after weak guidance",
                "terms": [
                  "downgrade"
                ]
              },
              {
                "title": "Regulator opens probe into Demo Software pricing",
                "terms": [
                  "probe"
                ]
              }
            ],
            "positive_headlines": [],
            "checks": {
              "red_flag_headlines": false
            }
          },
          "reasons": [
            "2 of 3 recent headlines contain risk terms; read them."
          ]
        }
      ],
      "news": [
        {
          "title": "Analyst downgrade after weak guidance",
          "publisher": "Sample Daily",
          "published_at": "2026-11-18T15:00:00+00:00",
          "url": null,
          "summary": null
        },
        {
          "title": "Regulator opens probe into Demo Software pricing",
          "publisher": "Sample Wire",
          "published_at": "2026-11-18T08:30:00+00:00",
          "url": null,
          "summary": null
        },
        {
          "title": "Demo Software wins major contract",
          "publisher": "Sample Wire",
          "published_at": "2026-11-17T10:00:00+00:00",
          "url": null,
          "summary": "Multi-year deal announced."
        }
      ],
      "data_quality_notes": []
    }
  ]
}
```
