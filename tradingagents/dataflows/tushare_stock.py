"""tushare-based A-share OHLCV stock data fetch."""
from datetime import datetime
import pandas as pd
import tushare as ts

from .akshare_stock import _is_a_share, _add_a_share_suffix
from .config import get_config
from .retry import with_retry


def _get_pro_api():
    """Initialize tushare pro API from config / env token."""
    config = get_config()
    token = config.get("tushare_token", "")
    ts.set_token(token)
    return ts.pro_api()


def _fetch_ohlcv(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch A-share daily OHLCV via tushare pro."""
    pro = _get_pro_api()

    ts_code = symbol  # already "688271.SH" format from _add_a_share_suffix

    def _call():
        return pro.daily(
            ts_code=ts_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )

    df = with_retry(_call, name=f"pro.daily({ts_code})")
    if df is None or df.empty:
        return pd.DataFrame()

    return df.rename(
        columns={
            "ts_code": "ts_code",
            "trade_date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "vol": "Volume",
            "amount": "Amount",
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


def get_stock(symbol: str, start_date: str, end_date: str) -> str:
    """Get OHLCV stock data for *symbol* between *start_date* and *end_date*.

    Returns a CSV string. Only supports A-shares; US stock symbols raise
    ValueError so that ``route_to_vendor`` can fall back to the next vendor.
    """
    if not _is_a_share(symbol):
        raise ValueError(f"Tushare only supports A-shares, got: {symbol}")

    try:
        api_symbol = _add_a_share_suffix(symbol)
        df = _fetch_ohlcv(api_symbol, start_date, end_date)
        return _format_ohlcv_response(df, symbol, start_date, end_date)
    except ValueError:
        raise
    except Exception as e:
        return f"Error retrieving stock data for {symbol}: {str(e)}"
