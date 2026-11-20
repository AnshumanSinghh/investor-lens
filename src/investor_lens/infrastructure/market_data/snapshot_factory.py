"""Maps raw yfinance payloads into the vendor-neutral ``AssetSnapshot`` (Factory)."""

from __future__ import annotations

from typing import Any, List, Mapping

import pandas as pd

from investor_lens.domain.calculators.math_utils import clip
from investor_lens.domain.constants import Statement
from investor_lens.domain.models import AssetSnapshot
from investor_lens.infrastructure.market_data.statement_parsing import extract_line_item, latest_value

_EQUITY_LABELS = ("Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest")
_SHARES_LABELS = ("Ordinary Shares Number", "Share Issued")

# canonical key -> (statement, vendor labels in order of preference)
_INCOME, _BALANCE, _CASHFLOW = "income", "balance", "cashflow"
_STATEMENT_LINES = {
    Statement.REVENUE: (_INCOME, ("Total Revenue", "Operating Revenue")),
    Statement.GROSS_PROFIT: (_INCOME, ("Gross Profit",)),
    Statement.EBIT: (_INCOME, ("EBIT", "Operating Income")),
    Statement.NET_INCOME: (_INCOME, ("Net Income", "Net Income Common Stockholders")),
    Statement.OPERATING_CASH_FLOW: (
        _CASHFLOW,
        ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities"),
    ),
    Statement.TOTAL_ASSETS: (_BALANCE, ("Total Assets",)),
    Statement.CURRENT_ASSETS: (_BALANCE, ("Current Assets",)),
    Statement.CURRENT_LIABILITIES: (_BALANCE, ("Current Liabilities",)),
    Statement.LONG_TERM_DEBT: (_BALANCE, ("Long Term Debt", "Long Term Debt And Capital Lease Obligation")),
    Statement.CURRENT_DEBT: (_BALANCE, ("Current Debt", "Current Debt And Capital Lease Obligation")),
    Statement.CASH: (
        _BALANCE,
        ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"),
    ),
    Statement.NET_PPE: (_BALANCE, ("Net PPE",)),
    Statement.SHARES: (_BALANCE, _SHARES_LABELS),
}


def build_asset_snapshot(
    *,
    ticker: str,
    close: pd.Series,
    adjusted: pd.Series,
    info: Mapping[str, Any],
    income: pd.DataFrame,
    balance: pd.DataFrame,
    cashflow: pd.DataFrame,
    default_tax_rate: float,
    notes: List[str],
) -> AssetSnapshot:
    eps = extract_line_item(income, ["Diluted EPS", "Basic EPS"])
    equity = extract_line_item(balance, _EQUITY_LABELS)
    shares = extract_line_item(balance, _SHARES_LABELS)
    debt = extract_line_item(balance, ["Total Debt"])
    interest = extract_line_item(income, ["Interest Expense"])
    tax = extract_line_item(income, ["Tax Rate For Calcs"])

    free_cash_flow = extract_line_item(cashflow, ["Free Cash Flow"])
    if free_cash_flow.empty:
        operating = extract_line_item(cashflow, ["Operating Cash Flow"])
        capex = extract_line_item(cashflow, ["Capital Expenditure"])
        if not operating.empty and not capex.empty:
            free_cash_flow = (operating - capex.abs()).dropna()
            notes.append("FCF derived as operating cash flow minus capex.")

    frames = {_INCOME: income, _BALANCE: balance, _CASHFLOW: cashflow}
    statements = {
        key: series
        for key, (frame_name, labels) in _STATEMENT_LINES.items()
        if not (series := extract_line_item(frames[frame_name], labels)).empty
    }

    price = float(close.iloc[-1])
    shares_outstanding = info.get("sharesOutstanding") or latest_value(shares)
    market_cap = info.get("marketCap") or (price * shares_outstanding if shares_outstanding else None)

    beta = info.get("beta")
    if beta is None:
        notes.append("Beta missing from vendor; default applied downstream.")

    total_debt = latest_value(debt)
    if total_debt is None and info.get("totalDebt") is not None:
        total_debt = float(info["totalDebt"])
        notes.append("Total debt taken from vendor info (latest balance sheet missing).")

    tax_rate = latest_value(tax)
    tax_rate = clip(tax_rate, 0.0, 0.40) if tax_rate is not None else default_tax_rate
    interest_expense = latest_value(interest)

    return AssetSnapshot(
        ticker=ticker,
        name=str(info.get("longName") or info.get("shortName") or ticker),
        sector=info.get("sector"),
        currency=info.get("currency"),
        current_price=price,
        price_close=close,
        price_adjusted=adjusted,
        beta=float(beta) if beta is not None else None,
        market_cap=float(market_cap) if market_cap else None,
        shares_outstanding=float(shares_outstanding) if shares_outstanding else None,
        total_debt=total_debt,
        total_equity=latest_value(equity),
        interest_expense=abs(interest_expense) if interest_expense is not None else None,
        tax_rate=tax_rate,
        free_cash_flow=latest_value(free_cash_flow),
        eps_history=eps,
        equity_history=equity,
        shares_history=shares,
        statements=statements,
        data_notes=notes,
    )
