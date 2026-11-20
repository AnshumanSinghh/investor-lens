"""News adapters implementing ``NewsGateway``."""

from investor_lens.infrastructure.news.file_news import FileNewsGateway
from investor_lens.infrastructure.news.resilient import ResilientNewsGateway
from investor_lens.infrastructure.news.yfinance_news import YFinanceNewsGateway

__all__ = ["FileNewsGateway", "ResilientNewsGateway", "YFinanceNewsGateway"]
