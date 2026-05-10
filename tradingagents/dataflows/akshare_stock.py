"""akshare-based OHLCV stock data fetch — A-share first, US fallback."""
import re
from datetime import datetime
import pandas as pd
from .retry import with_retry


def _is_a_share(symbol: str) -> bool:
    """Return True when ``symbol`` looks like a 6-digit A-share code."""
    return bool(re.fullmatch(r"\d{6}", symbol))


def _add_a_share_suffix(symbol: str) -> str:
    """Append exchange suffix to a 6-digit A-share code."""
    code = symbol[:6]
    prefix = code[0]
    if prefix in ("0", "3"):
        return f"{code}.SZ"
    elif prefix == "6":
        return f"{code}.SH"
    elif prefix in ("4", "8"):
        return f"{code}.BJ"
    raise ValueError(f"Cannot determine exchange for A-share code: {symbol}")


def _fetch_ohlcv_a_share(
    symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    """Fetch A-share daily OHLCV via akshare."""
    import akshare as ak

    df = with_retry(
        lambda: ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        ),
        name="stock_zh_a_hist",
    )
    if df is None or df.empty:
        return pd.DataFrame()
    return df.rename(
        columns={
            "日期": "Date",
            "开盘": "Open",
            "收盘": "Close",
            "最高": "High",
            "最低": "Low",
            "成交量": "Volume",
            "成交额": "Amount",
            "振幅": "Amplitude",
            "涨跌幅": "ChangePct",
            "涨跌额": "Change",
            "换手率": "Turnover",
        }
    )


def _fetch_ohlcv_us(
    symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    """Fetch US stock daily OHLCV via akshare."""
    import akshare as ak

    df = with_retry(
        lambda: ak.stock_us_hist(
            symbol=symbol.upper(),
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        ),
        name="stock_us_hist",
    )
    if df is None or df.empty:
        return pd.DataFrame()
    return df.rename(
        columns={
            "日期": "Date",
            "开盘": "Open",
            "收盘": "Close",
            "最高": "High",
            "最低": "Low",
            "成交量": "Volume",
            "成交额": "Amount",
            "振幅": "Amplitude",
            "涨跌幅": "ChangePct",
            "涨跌额": "Change",
            "换手率": "Turnover",
        }
    )


def _format_ohlcv_response(df: pd.DataFrame, symbol: str, start_date: str, end_date: str) -> str:
    """Convert a dataframe of OHLCV data to a CSV string with header."""
    if df.empty:
        return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

    cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
    available = [c for c in cols if c in df.columns]
    out = df[available].copy()

    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")
    out = out.sort_values("Date")

    if "Close" in out.columns:
        out["Adj Close"] = out["Close"]

    for c in ["Open", "High", "Low", "Close", "Adj Close"]:
        if c in out.columns:
            out[c] = out[c].round(2)

    header = (
        f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
        f"# Total records: {len(out)}\n"
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + out.to_csv(index=False)


def get_stock(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    """Get OHLCV stock data for *symbol* between *start_date* and *end_date*.

    Returns a CSV string with header comment lines, matching the format of
    ``get_YFin_data_online`` so downstream consumers see the same shape.
    """
    try:
        start_fmt = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d")
        end_fmt = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y%m%d")

        if _is_a_share(symbol):
            api_symbol = _add_a_share_suffix(symbol)
            df = _fetch_ohlcv_a_share(api_symbol, start_fmt, end_fmt)
        else:
            df = _fetch_ohlcv_us(symbol.upper(), start_fmt, end_fmt)

        return _format_ohlcv_response(df, symbol, start_date, end_date)
    except Exception as e:
        return f"Error retrieving stock data for {symbol}: {str(e)}"
