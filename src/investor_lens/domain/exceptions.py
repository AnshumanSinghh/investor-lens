"""Domain-level exception hierarchy."""

from __future__ import annotations


class InvestorLensError(Exception):
    """Base class for all application errors."""


class DataFetchError(InvestorLensError):
    """A data vendor call failed; the operation may be retried."""


class DataUnavailableError(DataFetchError):
    """The vendor definitively has no data; retrying is pointless."""
