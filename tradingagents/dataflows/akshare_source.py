"""akshare data source — A-share first, US fallback."""
from datetime import datetime, timedelta
import pandas as pd
from dateutil.relativedelta import relativedelta
from stockstats import wrap

from .base import BaseDataSource, is_a_share, add_a_share_suffix
from .config import get_config
from .cache import DataCache
from .retry import with_retry
from .akshare_indicator import BEST_IND_PARAMS


class AKShareSource(BaseDataSource):
    """akshare data vendor — web-scraped, free, covers A-shares + US stocks + news."""

    def __init__(self, cache_db: str = "data/akshare_cache/akshare.db"):
        self.cache = DataCache(cache_db)

    # ── helpers ───────────────────────────────────────────────

    def _fetch_ohlcv_a(self, api_sym: str, start_date: str, end_date: str) -> pd.DataFrame:
        import akshare as ak
        return with_retry(
            lambda: ak.stock_zh_a_hist(symbol=api_sym, period="daily", start_date=start_date, end_date=end_date, adjust="qfq"),
            name="stock_zh_a_hist",
        ).rename(columns={"日期": "Date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount"})

    def _fetch_ohlcv_us(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        import akshare as ak
        return with_retry(
            lambda: ak.stock_us_hist(symbol=symbol.upper(), period="daily", start_date=start_date, end_date=end_date, adjust="qfq"),
            name="stock_us_hist",
        ).rename(columns={"日期": "Date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount"})

    def _format_ohlcv(self, df: pd.DataFrame, symbol: str, start_date: str, end_date: str) -> str:
        if df.empty:
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"
        cols = ["Date", "open", "high", "low", "close", "volume"]
        available = [c for c in cols if c in df.columns]
        out = df[available].copy()
        if "Date" in out.columns:
            out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")
        out = out.sort_values("Date")
        if "close" in out.columns:
            out["adj_close"] = out["close"]
        for c in ["open", "high", "low", "close", "adj_close"]:
            if c in out.columns:
                out[c] = out[c].round(2)
        header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n# Total records: {len(out)}\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + out.to_csv(index=False)

    # ── Stock (OHLCV) ─────────────────────────────────────────

    def get_stock(self, symbol: str, start_date: str, end_date: str) -> str:
        try:
            start_fmt = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d")
            end_fmt = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y%m%d")
            if is_a_share(symbol):
                api_sym = add_a_share_suffix(symbol)
                df = self._fetch_ohlcv_a(api_sym, start_fmt, end_fmt)
            else:
                df = self._fetch_ohlcv_us(symbol.upper(), start_fmt, end_fmt)
            if not df.empty and "close" in df.columns:
                self.cache.save_ohlcv(symbol, df)
            return self._format_ohlcv(df, symbol, start_date, end_date)
        except Exception as e:
            return f"Error retrieving stock data for {symbol}: {str(e)}"

    # ── Fundamentals ──────────────────────────────────────────

    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        try:
            info = self._get_company_info(ticker)
            if not info:
                return f"No fundamentals data found for symbol '{ticker}'"
            header = f"# Company Fundamentals for {ticker.upper()}\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            return header + "\n".join(f"{k}: {v}" for k, v in info.items())
        except Exception as e:
            return f"Error retrieving fundamentals for {ticker}: {str(e)}"

    def _get_company_info(self, ticker: str) -> dict:
        import akshare as ak
        info = {}
        if is_a_share(ticker):
            api_sym = add_a_share_suffix(ticker)
            try:
                raw = with_retry(lambda: ak.stock_individual_info_em(symbol=api_sym), name="stock_individual_info_em")
                if raw is not None and not raw.empty:
                    for _, row in raw.iterrows():
                        k, v = str(row.get("item", "")), str(row.get("value", ""))
                        if k and v and v.lower() != "none":
                            info[k] = v
            except Exception:
                pass
            try:
                ind = with_retry(lambda: ak.stock_financial_analysis_indicator(symbol=api_sym), name="stock_financial_analysis_indicator")
                if ind is not None and not ind.empty:
                    latest = ind.iloc[-1]
                    for col in ind.columns:
                        v = latest[col]
                        if pd.notna(v):
                            info[col] = v
            except Exception:
                pass
        else:
            try:
                spot = with_retry(lambda: ak.stock_us_spot_em(), name="stock_us_spot_em")
                row = spot[spot["代码"] == ticker.upper()]
                if not row.empty:
                    r = row.iloc[0]
                    for k in ["总市值", "市盈率", "最新价"]:
                        if pd.notna(r.get(k)):
                            info[k] = r.get(k)
            except Exception:
                pass
            try:
                basic = with_retry(lambda: ak.stock_individual_basic_info_us_xq(symbol=ticker.upper()), name="stock_individual_basic_info_us_xq")
                if basic is not None and not basic.empty:
                    for _, r in basic.iterrows():
                        k, v = str(r.get("item", "")), str(r.get("value", ""))
                        if k and v and v.lower() != "none":
                            info[k] = v
            except Exception:
                pass
            try:
                fin = with_retry(lambda: ak.stock_financial_us_analysis_indicator_em(symbol=ticker.upper(), indicator="年报"), name="stock_financial_us_analysis_indicator_em")
                if fin is not None and not fin.empty:
                    latest = fin.iloc[-1]
                    for col in fin.columns:
                        v = latest[col]
                        if pd.notna(v):
                            info[col] = v
            except Exception:
                pass
        return info

    def get_balance_sheet(self, ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
        try:
            import akshare as ak
            if is_a_share(ticker):
                df = with_retry(lambda: ak.stock_balance_sheet_by_report_em(symbol=add_a_share_suffix(ticker)), name="stock_balance_sheet_by_report_em")
            else:
                df = with_retry(lambda: ak.stock_financial_us_report_em(stock=ticker.upper(), symbol="资产负债表", indicator="年报"), name="stock_financial_us_report_em(bs)")
            if df is None or df.empty:
                return f"No balance sheet data found for symbol '{ticker}'"
            header = f"# Balance Sheet data for {ticker.upper()} ({freq})\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            return header + df.to_csv()
        except Exception as e:
            return f"Error retrieving balance sheet for {ticker}: {str(e)}"

    def get_income_statement(self, ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
        try:
            import akshare as ak
            if is_a_share(ticker):
                df = with_retry(lambda: ak.stock_profit_sheet_by_report_em(symbol=add_a_share_suffix(ticker)), name="stock_profit_sheet_by_report_em")
            else:
                df = with_retry(lambda: ak.stock_financial_us_report_em(stock=ticker.upper(), symbol="综合损益表", indicator="年报"), name="stock_financial_us_report_em(is)")
            if df is None or df.empty:
                return f"No income statement data found for symbol '{ticker}'"
            header = f"# Income Statement data for {ticker.upper()} ({freq})\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            return header + df.to_csv()
        except Exception as e:
            return f"Error retrieving income statement for {ticker}: {str(e)}"

    def get_cashflow(self, ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
        try:
            import akshare as ak
            if is_a_share(ticker):
                df = with_retry(lambda: ak.stock_cash_flow_sheet_by_report_em(symbol=add_a_share_suffix(ticker)), name="stock_cash_flow_sheet_by_report_em")
            else:
                df = with_retry(lambda: ak.stock_financial_us_report_em(stock=ticker.upper(), symbol="现金流量表", indicator="年报"), name="stock_financial_us_report_em(cf)")
            if df is None or df.empty:
                return f"No cash flow data found for symbol '{ticker}'"
            header = f"# Cash Flow data for {ticker.upper()} ({freq})\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            return header + df.to_csv()
        except Exception as e:
            return f"Error retrieving cash flow for {ticker}: {str(e)}"

    # ── Indicators ────────────────────────────────────────────

    def get_indicator(self, symbol: str, indicator: str, curr_date: str,
                      look_back_days: int, interval: str = "daily",
                      time_period: int = 14, series_type: str = "close") -> str:
        if indicator not in BEST_IND_PARAMS:
            raise ValueError(f"Indicator {indicator} not supported. Choose from: {list(BEST_IND_PARAMS.keys())}")
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        before = curr_dt - relativedelta(days=look_back_days + 60)
        try:
            start_fmt = before.strftime("%Y%m%d")
            end_fmt = curr_dt.strftime("%Y%m%d")
            if is_a_share(symbol):
                df = self._fetch_ohlcv_a(add_a_share_suffix(symbol), start_fmt, end_fmt)
            else:
                df = self._fetch_ohlcv_us(symbol.upper(), start_fmt, end_fmt)
            if df is None or df.empty:
                return f"Error retrieving indicator data: no OHLCV for {symbol}"
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date", "close"])
            for c in ["open", "high", "low", "close", "volume"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna(subset=["close"]).ffill().bfill()
            df = df[df["Date"] <= curr_dt]
            stock = wrap(df)
            stock["Date"] = stock["Date"].dt.strftime("%Y-%m-%d")
            stock[indicator]
            lines = []
            cursor = curr_dt
            lookback_start = curr_dt - relativedelta(days=look_back_days)
            while cursor >= lookback_start:
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
            return f"## {indicator} values from {lookback_start.strftime('%Y-%m-%d')} to {curr_date}:\n\n" + "\n".join(lines) + "\n\n" + desc
        except Exception as e:
            return f"Error retrieving {indicator} data for {symbol}: {str(e)}"

    # ── News ──────────────────────────────────────────────────

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        try:
            if is_a_share(ticker):
                import akshare as ak
                numeric = ticker.split(".")[0][:6]
                df = with_retry(lambda: ak.stock_news_em(symbol=numeric), name="stock_news_em")
                if df is not None and not df.empty:
                    if "发布时间" in df.columns:
                        df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
                        df = df[(df["发布时间"] >= pd.to_datetime(start_date)) & (df["发布时间"] <= pd.to_datetime(end_date))]
                    formatted = self._fmt_news(df, 20)
                    if formatted:
                        return f"## {ticker.upper()} News, from {start_date} to {end_date}:\n\n" + formatted
                return f"No news found for {ticker} in the specified date range."
            else:
                return self._us_news_fallback(ticker.upper(), start_date, end_date)
        except Exception as e:
            return f"Error retrieving news for {ticker}: {str(e)}"

    def _us_news_fallback(self, ticker: str, start_date: str, end_date: str) -> str:
        try:
            import yfinance as yf
            raw = yf.Ticker(ticker).news
            if not raw:
                return f"No news found for US stock '{ticker}'."
            items = []
            for entry in raw[:20]:
                title = entry.get("title", "")
                source = entry.get("publisher", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                parts = [f"### {title} (source: {source})" if source else f"### {title}"]
                if summary:
                    parts.append(summary[:500])
                if link:
                    parts.append(f"Link: {link}")
                items.append("\n".join(parts))
            return f"## {ticker} News, from {start_date} to {end_date}:\n\n" + "\n---\n".join(items)
        except Exception:
            return f"Ticker-specific news not available for US stock '{ticker}'."

    def get_global_news(self, curr_date: str, look_back_days: int = 7, limit: int = 50) -> str:
        try:
            import akshare as ak
            df = with_retry(lambda: ak.stock_info_global_em(), name="stock_info_global_em")
            if df is None or df.empty:
                return "No global news available at this time."
            if "发布时间" in df.columns:
                df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
                df = df[df["发布时间"] >= pd.to_datetime(curr_date) - timedelta(days=look_back_days)]
            formatted = self._fmt_news(df, limit)
            start_str = (pd.to_datetime(curr_date) - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
            header = f"## Global Market News, from {start_str} to {curr_date}:\n\n"
            return header + formatted if formatted else header + "No global news found."
        except Exception as e:
            return f"Error retrieving global news: {str(e)}"

    def get_insider_transactions(self, symbol: str) -> str:
        try:
            if is_a_share(symbol):
                import akshare as ak
                numeric = symbol.split(".")[0][:6]
                df = with_retry(lambda: ak.stock_inner_trade_xq(), name="stock_inner_trade_xq")
                if df is not None and not df.empty and "股票代码" in df.columns:
                    df = df[df["股票代码"] == numeric]
                if df is None or df.empty:
                    return f"No insider transactions data found for symbol '{symbol}'"
                header = f"# Insider Transactions data for {symbol.upper()}\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                return header + df.to_csv()
            else:
                return self._us_insider_fallback(symbol.upper())
        except Exception as e:
            return f"Error retrieving insider transactions for {symbol}: {str(e)}"

    def _us_insider_fallback(self, symbol: str) -> str:
        try:
            import yfinance as yf
            data = yf.Ticker(symbol).insider_transactions
            if data is None or data.empty:
                return f"No insider transactions data found for US stock '{symbol}'."
            header = f"# Insider Transactions data for {symbol.upper()}\n# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            return header + data.to_csv()
        except Exception:
            return f"Insider transactions not available for US stock '{symbol}'."

    @staticmethod
    def _fmt_news(df: pd.DataFrame, limit: int) -> str:
        if df is None or df.empty:
            return ""
        items = []
        for _, row in df.head(limit).iterrows():
            title = row.get("标题", row.get("title", ""))
            source = row.get("来源", row.get("source", ""))
            content = row.get("内容", row.get("summary", row.get("content", "")))
            link = row.get("链接", row.get("url", row.get("link", "")))
            if not title:
                continue
            parts = [f"### {title} (source: {source})" if source else f"### {title}"]
            if content:
                parts.append(str(content)[:500])
            if link:
                parts.append(f"Link: {link}")
            items.append("\n".join(parts))
        return "\n---\n".join(items)
