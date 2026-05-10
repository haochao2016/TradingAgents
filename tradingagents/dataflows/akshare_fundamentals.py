"""akshare-based fundamental data — A-share first, US fallback."""
from datetime import datetime
import pandas as pd
from .akshare_stock import _is_a_share, _add_a_share_suffix
from .retry import with_retry


# ── helpers ────────────────────────────────────────────────────────


def _get_a_share_company_info(symbol: str) -> dict:
    """Return key-value pairs for an A-share company."""
    import akshare as ak

    info = {}
    try:
        raw = with_retry(lambda: ak.stock_individual_info_em(symbol=symbol), name="stock_individual_info_em")
        if raw is not None and not raw.empty:
            for _, row in raw.iterrows():
                key = str(row.get("item", ""))
                val = str(row.get("value", ""))
                if key and val and val.lower() != "none":
                    info[key] = val
    except Exception:
        pass

    try:
        indicators = with_retry(lambda: ak.stock_financial_analysis_indicator(symbol=symbol), name="stock_financial_analysis_indicator")
        if indicators is not None and not indicators.empty:
            latest = indicators.iloc[-1]
            for col in indicators.columns:
                v = latest[col]
                if pd.notna(v) and str(v).lower() != "none":
                    info[col] = v
    except Exception:
        pass

    return info


def _get_us_company_info(symbol: str) -> dict:
    """Return key-value pairs for a US stock company."""
    import akshare as ak

    info = {}
    try:
        spot = with_retry(lambda: ak.stock_us_spot_em(), name="stock_us_spot_em")
        row = spot[spot["代码"] == symbol.upper()]
        if not row.empty:
            r = row.iloc[0]
            info["Market Cap"] = r.get("总市值")
            info["PE Ratio (TTM)"] = r.get("市盈率")
            info["Price"] = r.get("最新价")
    except Exception:
        pass

    try:
        basic = with_retry(lambda: ak.stock_individual_basic_info_us_xq(symbol=symbol.upper()), name="stock_individual_basic_info_us_xq")
        if basic is not None and not basic.empty:
            for _, r in basic.iterrows():
                k = str(r.get("item", ""))
                v = str(r.get("value", ""))
                if k and v and v.lower() != "none":
                    info[k] = v
    except Exception:
        pass

    try:
        fin = with_retry(lambda: ak.stock_financial_us_analysis_indicator_em(symbol=symbol.upper(), indicator="年报"), name="stock_financial_us_analysis_indicator_em")
        if fin is not None and not fin.empty:
            latest = fin.iloc[-1]
            for col in fin.columns:
                v = latest[col]
                if pd.notna(v) and str(v).lower() != "none":
                    info[col] = v
    except Exception:
        pass

    return info


def _filter_columns_by_date(df: pd.DataFrame, curr_date: str) -> pd.DataFrame:
    """Drop columns whose name (a date string) is after *curr_date*."""
    if not curr_date or df.empty:
        return df
    cutoff = pd.Timestamp(curr_date)
    mask = pd.to_datetime(df.columns, errors="coerce") <= cutoff
    return df.loc[:, mask]


# ── public functions ───────────────────────────────────────────────


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Get company fundamentals overview."""
    try:
        if _is_a_share(ticker):
            api_sym = _add_a_share_suffix(ticker)
            info = _get_a_share_company_info(api_sym)
        else:
            info = _get_us_company_info(ticker.upper())

        if not info:
            return f"No fundamentals data found for symbol '{ticker}'"

        lines = [f"{k}: {v}" for k, v in info.items()]

        header = (
            f"# Company Fundamentals for {ticker.upper()}\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + "\n".join(lines)
    except Exception as e:
        return f"Error retrieving fundamentals for {ticker}: {str(e)}"


def get_balance_sheet(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str = None,
) -> str:
    """Get balance sheet data."""
    try:
        if _is_a_share(ticker):
            api_sym = _add_a_share_suffix(ticker)
            import akshare as ak
            df = with_retry(lambda: ak.stock_balance_sheet_by_report_em(symbol=api_sym), name="stock_balance_sheet_by_report_em")
        else:
            import akshare as ak
            df = with_retry(lambda: ak.stock_financial_us_report_em(stock=ticker.upper(), symbol="资产负债表", indicator="年报"), name="stock_financial_us_report_em(bs)")

        if df is None or df.empty:
            return f"No balance sheet data found for symbol '{ticker}'"

        df = _filter_columns_by_date(df, curr_date)
        csv_str = df.to_csv()
        header = (
            f"# Balance Sheet data for {ticker.upper()} ({freq})\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + csv_str
    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


def get_income_statement(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str = None,
) -> str:
    """Get income statement data."""
    try:
        if _is_a_share(ticker):
            api_sym = _add_a_share_suffix(ticker)
            import akshare as ak
            df = with_retry(lambda: ak.stock_profit_sheet_by_report_em(symbol=api_sym), name="stock_profit_sheet_by_report_em")
        else:
            import akshare as ak
            df = with_retry(lambda: ak.stock_financial_us_report_em(stock=ticker.upper(), symbol="综合损益表", indicator="年报"), name="stock_financial_us_report_em(is)")

        if df is None or df.empty:
            return f"No income statement data found for symbol '{ticker}'"

        df = _filter_columns_by_date(df, curr_date)
        csv_str = df.to_csv()
        header = (
            f"# Income Statement data for {ticker.upper()} ({freq})\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + csv_str
    except Exception as e:
        return f"Error retrieving income statement for {ticker}: {str(e)}"


def get_cashflow(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str = None,
) -> str:
    """Get cash flow data."""
    try:
        if _is_a_share(ticker):
            api_sym = _add_a_share_suffix(ticker)
            import akshare as ak
            df = with_retry(lambda: ak.stock_cash_flow_sheet_by_report_em(symbol=api_sym), name="stock_cash_flow_sheet_by_report_em")
        else:
            import akshare as ak
            df = with_retry(lambda: ak.stock_financial_us_report_em(stock=ticker.upper(), symbol="现金流量表", indicator="年报"), name="stock_financial_us_report_em(cf)")

        if df is None or df.empty:
            return f"No cash flow data found for symbol '{ticker}'"

        df = _filter_columns_by_date(df, curr_date)
        csv_str = df.to_csv()
        header = (
            f"# Cash Flow data for {ticker.upper()} ({freq})\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + csv_str
    except Exception as e:
        return f"Error retrieving cash flow for {ticker}: {str(e)}"
