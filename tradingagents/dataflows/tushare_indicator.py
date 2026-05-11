"""tushare-based technical indicators via stockstats — A-share only."""
import os
from datetime import datetime
import pandas as pd
from dateutil.relativedelta import relativedelta
from stockstats import wrap
from .config import get_config
from .akshare_stock import _is_a_share, _add_a_share_suffix
from .tushare_stock import _get_pro_api, _fetch_ohlcv
from .akshare_indicator import BEST_IND_PARAMS


def _load_ohlcv_tushare(symbol: str, curr_date: str) -> pd.DataFrame:
    """Fetch OHLCV from tushare, filtered to prevent look-ahead bias."""
    config = get_config()
    curr_date_dt = pd.to_datetime(curr_date)

    today_date = pd.Timestamp.today()
    start_date = today_date - pd.DateOffset(years=5)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = today_date.strftime("%Y-%m-%d")

    if _is_a_share(symbol):
        api_sym = _add_a_share_suffix(symbol)
        data = _fetch_ohlcv(api_sym, start_str, end_str)
    else:
        raise ValueError(f"Tushare only supports A-shares, got: {symbol}")

    if data is None or data.empty:
        raise ValueError(f"No OHLCV data for {symbol}")

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])
    price_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]
    data[price_cols] = data[price_cols].apply(pd.to_numeric, errors="coerce")
    data = data.dropna(subset=["Close"])
    data[price_cols] = data[price_cols].ffill().bfill()

    data = data[data["Date"] <= curr_date_dt]
    return data


def get_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
    interval: str = "daily",
    time_period: int = 14,
    series_type: str = "close",
) -> str:
    """Get technical indicator values over a look-back window."""
    if indicator not in BEST_IND_PARAMS:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(BEST_IND_PARAMS.keys())}"
        )

    if not _is_a_share(symbol):
        raise ValueError(f"Tushare only supports A-shares, got: {symbol}")

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    try:
        data = _load_ohlcv_tushare(symbol, curr_date)
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        df[indicator]

        lines = []
        cursor = curr_date_dt
        while cursor >= before:
            date_str = cursor.strftime("%Y-%m-%d")
            matching = df[df["Date"] == date_str]
            if not matching.empty:
                v = matching[indicator].values[0]
                val = f"{v:.4f}" if pd.notna(v) else "N/A: Not a trading day (weekend or holiday)"
            else:
                val = "N/A: Not a trading day (weekend or holiday)"
            lines.append(f"{date_str}: {val}")
            cursor = cursor - relativedelta(days=1)

        desc = BEST_IND_PARAMS.get(indicator, "")
        result = (
            f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            + "\n".join(lines)
            + "\n\n"
            + desc
        )
        return result
    except ValueError:
        raise
    except Exception as e:
        return f"Error retrieving {indicator} data for {symbol}: {str(e)}"
