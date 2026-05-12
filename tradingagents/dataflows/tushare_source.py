"""Tushare data source — A-share only."""
from datetime import datetime
import pandas as pd
import tushare as ts
from dateutil.relativedelta import relativedelta
from stockstats import wrap

from .base import BaseDataSource, is_a_share, add_a_share_suffix
from .config import get_config
from .cache import DataCache
from .retry import with_retry
from .akshare_indicator import BEST_IND_PARAMS


class TushareSource(BaseDataSource):
    """Tushare Pro data vendor. Covers A-share K-line + financials.
    US stock requests raise NotImplementedError, triggering fallback in route_to_vendor.
    Other failures raise exceptions directly for route_to_vendor to catch and fall back."""

    def __init__(self, cache_db: str = "data/tushare_cache/tushare.db"):
        self.cache = DataCache(cache_db)

    def _pro_api(self):
        config = get_config()
        token = config.get("tushare_token", "")
        ts.set_token(token)
        return ts.pro_api()

    # ── Stock (OHLCV) ─────────────────────────────────────────

    def get_stock(self, symbol: str, start_date: str, end_date: str) -> str:
        if not is_a_share(symbol):
            raise NotImplementedError(f"Tushare only supports A-shares, got: {symbol}")
        api_sym = add_a_share_suffix(symbol)
        df = self._fetch_ohlcv(api_sym, start_date, end_date)
        return self._format_ohlcv(df, symbol, start_date, end_date)

    def _fetch_ohlcv(self, api_sym: str, start_date: str, end_date: str) -> pd.DataFrame:
        start_fmt = start_date.replace("-", "")
        end_fmt = end_date.replace("-", "")

        # Check cache first
        cached = self.cache.load_ohlcv(api_sym, start_date, end_date)
        if not cached.empty:
            return cached

        pro = self._pro_api()
        df = with_retry(
            lambda: pro.daily(ts_code=api_sym, start_date=start_fmt, end_date=end_fmt),
            name=f"pro.daily({api_sym})",
        )
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(columns={
            "trade_date": "Date", "open": "Open", "high": "High",
            "low": "Low", "close": "Close", "vol": "Volume", "amount": "Amount",
        })
        if "Close" in df.columns:
            df["Adj Close"] = df["Close"]

        self.cache.save_ohlcv(api_sym, df)
        return df

    def _format_ohlcv(self, df: pd.DataFrame, symbol: str, start_date: str, end_date: str) -> str:
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

    # ── Fundamentals ──────────────────────────────────────────

    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        if not is_a_share(ticker):
            raise NotImplementedError(f"Tushare only supports A-shares, got: {ticker}")
        pro = self._pro_api()
        api_sym = add_a_share_suffix(ticker)
        basic = with_retry(lambda: pro.daily_basic(ts_code=api_sym), name="pro.daily_basic")
        fina = with_retry(lambda: pro.fina_indicator(ts_code=api_sym), name="pro.fina_indicator")
        lines = []
        for df in [basic, fina]:
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                for col in df.columns:
                    v = latest[col]
                    if pd.notna(v):
                        lines.append(f"{col}: {v}")
        if not lines:
            return f"No fundamentals data found for symbol '{ticker}'"
        header = f"# Company Fundamentals for {ticker.upper()}\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + "\n".join(lines)

    def get_balance_sheet(self, ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
        if not is_a_share(ticker):
            raise NotImplementedError(f"Tushare only supports A-shares, got: {ticker}")
        pro = self._pro_api()
        api_sym = add_a_share_suffix(ticker)
        df = with_retry(lambda: pro.balancesheet(ts_code=api_sym), name="pro.balancesheet")
        if df is None or df.empty:
            return f"No balance sheet data found for symbol '{ticker}'"
        header = f"# Balance Sheet data for {ticker.upper()} ({freq})\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + df.to_csv()

    def get_income_statement(self, ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
        if not is_a_share(ticker):
            raise NotImplementedError(f"Tushare only supports A-shares, got: {ticker}")
        pro = self._pro_api()
        api_sym = add_a_share_suffix(ticker)
        df = with_retry(lambda: pro.income(ts_code=api_sym), name="pro.income")
        if df is None or df.empty:
            return f"No income statement data found for symbol '{ticker}'"
        header = f"# Income Statement data for {ticker.upper()} ({freq})\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + df.to_csv()

    def get_cashflow(self, ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
        if not is_a_share(ticker):
            raise NotImplementedError(f"Tushare only supports A-shares, got: {ticker}")
        pro = self._pro_api()
        api_sym = add_a_share_suffix(ticker)
        df = with_retry(lambda: pro.cashflow(ts_code=api_sym), name="pro.cashflow")
        if df is None or df.empty:
            return f"No cash flow data found for symbol '{ticker}'"
        header = f"# Cash Flow data for {ticker.upper()} ({freq})\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + df.to_csv()

    # ── Indicators ────────────────────────────────────────────

    def get_indicator(self, symbol: str, indicator: str, curr_date: str,
                      look_back_days: int, interval: str = "daily",
                      time_period: int = 14, series_type: str = "close") -> str:
        if not is_a_share(symbol):
            raise NotImplementedError(f"Tushare only supports A-shares, got: {symbol}")
        if indicator not in BEST_IND_PARAMS:
            raise ValueError(f"Indicator {indicator} not supported. Choose from: {list(BEST_IND_PARAMS.keys())}")
        curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        before = curr_date_dt - relativedelta(days=look_back_days)
        api_sym = add_a_share_suffix(symbol)
        df = self._fetch_ohlcv(api_sym, before.strftime("%Y-%m-%d"), curr_date)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date", "Close"])
        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["Close"]).ffill().bfill()
        df = df[df["Date"] <= curr_date_dt]
        stock = wrap(df)
        stock["Date"] = stock["Date"].dt.strftime("%Y-%m-%d")
        stock[indicator]
        lines = []
        cursor = curr_date_dt
        while cursor >= before:
            ds = cursor.strftime("%Y-%m-%d")
            match = stock[stock["Date"] == ds]
            if not match.empty:
                v = match[indicator].values[0]
                val = f"{v:.4f}" if pd.notna(v) else "N/A"
            else:
                val = "N/A: Not a trading day (weekend or holiday)"
            lines.append(f"{ds}: {val}")
            cursor -= relativedelta(days=1)
        desc = BEST_IND_PARAMS.get(indicator, "")
        return f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n" + "\n".join(lines) + "\n\n" + desc
