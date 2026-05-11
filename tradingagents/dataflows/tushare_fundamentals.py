"""tushare-based fundamental data — A-share only."""
from datetime import datetime
import pandas as pd
from .akshare_stock import _is_a_share, _add_a_share_suffix
from .tushare_stock import _get_pro_api
from .retry import with_retry


# ── public functions ───────────────────────────────────────────────


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Get company fundamentals overview via tushare."""
    if not _is_a_share(ticker):
        raise ValueError(f"Tushare only supports A-shares, got: {ticker}")

    try:
        pro = _get_pro_api()
        api_sym = _add_a_share_suffix(ticker)

        basic = with_retry(
            lambda: pro.daily_basic(ts_code=api_sym),
            name="pro.daily_basic",
        )
        fina = with_retry(
            lambda: pro.fina_indicator(ts_code=api_sym),
            name="pro.fina_indicator",
        )

        lines = []
        if basic is not None and not basic.empty:
            latest = basic.iloc[-1]
            for col in basic.columns:
                v = latest[col]
                if pd.notna(v):
                    lines.append(f"{col}: {v}")
        if fina is not None and not fina.empty:
            latest = fina.iloc[-1]
            for col in fina.columns:
                v = latest[col]
                if pd.notna(v):
                    lines.append(f"{col}: {v}")

        if not lines:
            return f"No fundamentals data found for symbol '{ticker}'"

        header = (
            f"# Company Fundamentals for {ticker.upper()}\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + "\n".join(lines)
    except ValueError:
        raise
    except Exception as e:
        return f"Error retrieving fundamentals for {ticker}: {str(e)}"


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Get balance sheet data via tushare."""
    if not _is_a_share(ticker):
        raise ValueError(f"Tushare only supports A-shares, got: {ticker}")

    try:
        pro = _get_pro_api()
        api_sym = _add_a_share_suffix(ticker)
        df = with_retry(lambda: pro.balancesheet(ts_code=api_sym), name="pro.balancesheet")

        if df is None or df.empty:
            return f"No balance sheet data found for symbol '{ticker}'"

        csv_str = df.to_csv()
        header = (
            f"# Balance Sheet data for {ticker.upper()} ({freq})\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + csv_str
    except ValueError:
        raise
    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Get income statement data via tushare."""
    if not _is_a_share(ticker):
        raise ValueError(f"Tushare only supports A-shares, got: {ticker}")

    try:
        pro = _get_pro_api()
        api_sym = _add_a_share_suffix(ticker)
        df = with_retry(lambda: pro.income(ts_code=api_sym), name="pro.income")

        if df is None or df.empty:
            return f"No income statement data found for symbol '{ticker}'"

        csv_str = df.to_csv()
        header = (
            f"# Income Statement data for {ticker.upper()} ({freq})\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + csv_str
    except ValueError:
        raise
    except Exception as e:
        return f"Error retrieving income statement for {ticker}: {str(e)}"


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Get cash flow data via tushare."""
    if not _is_a_share(ticker):
        raise ValueError(f"Tushare only supports A-shares, got: {ticker}")

    try:
        pro = _get_pro_api()
        api_sym = _add_a_share_suffix(ticker)
        df = with_retry(lambda: pro.cashflow(ts_code=api_sym), name="pro.cashflow")

        if df is None or df.empty:
            return f"No cash flow data found for symbol '{ticker}'"

        csv_str = df.to_csv()
        header = (
            f"# Cash Flow data for {ticker.upper()} ({freq})\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + csv_str
    except ValueError:
        raise
    except Exception as e:
        return f"Error retrieving cash flow for {ticker}: {str(e)}"
