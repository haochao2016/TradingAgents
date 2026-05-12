"""Base data source class and shared market detection utilities."""
import re


def is_a_share(symbol: str) -> bool:
    """Return True when *symbol* looks like an A-share code (with or without suffix)."""
    raw = symbol.split(".")[0]
    return bool(re.fullmatch(r"\d{6}", raw))


def add_a_share_suffix(symbol: str) -> str:
    """Append exchange suffix to a 6-digit A-share code."""
    code = symbol.split(".")[0][:6]
    prefix = code[0]
    if prefix in ("0", "3"):
        return f"{code}.SZ"
    elif prefix == "6":
        return f"{code}.SH"
    elif prefix in ("4", "8"):
        return f"{code}.BJ"
    raise ValueError(f"Cannot determine exchange for A-share code: {symbol}")


class BaseDataSource:
    """Abstract base for financial data vendors."""

    def get_stock(self, symbol: str, start_date: str, end_date: str) -> str:
        """OHLCV stock data, returns CSV string."""
        raise NotImplementedError

    def get_indicator(self, symbol: str, indicator: str, curr_date: str,
                      look_back_days: int, interval: str = "daily",
                      time_period: int = 14, series_type: str = "close") -> str:
        """Technical indicator values over a look-back window."""
        raise NotImplementedError

    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        """Company fundamentals overview."""
        raise NotImplementedError

    def get_balance_sheet(self, ticker: str, freq: str = "quarterly",
                          curr_date: str = None) -> str:
        """Balance sheet data."""
        raise NotImplementedError

    def get_cashflow(self, ticker: str, freq: str = "quarterly",
                     curr_date: str = None) -> str:
        """Cash flow data."""
        raise NotImplementedError

    def get_income_statement(self, ticker: str, freq: str = "quarterly",
                             curr_date: str = None) -> str:
        """Income statement data."""
        raise NotImplementedError

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        """Ticker-specific news."""
        raise NotImplementedError

    def get_global_news(self, curr_date: str, look_back_days: int = 7,
                        limit: int = 50) -> str:
        """Global financial news."""
        raise NotImplementedError

    def get_insider_transactions(self, symbol: str) -> str:
        """Insider transactions data."""
        raise NotImplementedError
