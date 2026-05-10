"""akshare-based news and insider data — A-share native, US yfinance fallback."""
from datetime import datetime, timedelta
import pandas as pd
from .akshare_stock import _is_a_share, _add_a_share_suffix


def _format_news_items(df: pd.DataFrame, limit: int) -> str:
    """Format a news DataFrame into the project's standard news text format."""
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


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """Get ticker-specific news. A-share via akshare; US stocks fall back to yfinance."""
    try:
        if _is_a_share(ticker):
            import akshare as ak
            numeric = ticker[:6]
            df = ak.stock_news_em(symbol=numeric)
            if df is not None and not df.empty:
                if "发布时间" in df.columns:
                    df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
                    start_dt = pd.to_datetime(start_date)
                    end_dt = pd.to_datetime(end_date)
                    df = df[(df["发布时间"] >= start_dt) & (df["发布时间"] <= end_dt)]
                formatted = _format_news_items(df, 20)
                if formatted:
                    header = f"## {ticker.upper()} News, from {start_date} to {end_date}:\n\n"
                    return header + formatted
            return f"No news found for {ticker} in the specified date range."
        else:
            return _us_news_yfinance_fallback(ticker.upper(), start_date, end_date)
    except Exception as e:
        return f"Error retrieving news for {ticker}: {str(e)}"


def _us_news_yfinance_fallback(ticker: str, start_date: str, end_date: str) -> str:
    """Internal yfinance fallback for US stock ticker-specific news."""
    try:
        import yfinance as yf
        raw = yf.Ticker(ticker).news
        if not raw:
            return f"No news found for US stock '{ticker}' in the specified date range."
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
        header = f"## {ticker} News, from {start_date} to {end_date}:\n\n"
        return header + "\n---\n".join(items)
    except Exception:
        return f"Ticker-specific news not available for US stock '{ticker}'. Consider using get_global_news for general market news."


def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 50) -> str:
    """Get global financial news via akshare."""
    try:
        import akshare as ak
        df = ak.stock_info_global_em()
        if df is None or df.empty:
            return "No global news available at this time."

        if "发布时间" in df.columns:
            df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
            start_dt = pd.to_datetime(curr_date) - timedelta(days=look_back_days)
            df = df[df["发布时间"] >= start_dt]

        start_str = (pd.to_datetime(curr_date) - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
        formatted = _format_news_items(df, limit)
        header = f"## Global Market News, from {start_str} to {curr_date}:\n\n"
        return header + formatted if formatted else header + "No global news found in the specified date range."
    except Exception as e:
        return f"Error retrieving global news: {str(e)}"


def get_insider_transactions(symbol: str) -> str:
    """Get insider transactions. A-share via akshare; US stocks fall back to yfinance."""
    try:
        if _is_a_share(symbol):
            import akshare as ak
            numeric = symbol[:6]
            df = ak.stock_inner_trade_xq(symbol=numeric)
            if df is None or df.empty:
                return f"No insider transactions data found for symbol '{symbol}'"
            csv_str = df.to_csv()
            header = (
                f"# Insider Transactions data for {symbol.upper()}\n"
                f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            return header + csv_str
        else:
            return _us_insider_yfinance_fallback(symbol.upper())
    except Exception as e:
        return f"Error retrieving insider transactions for {symbol}: {str(e)}"


def _us_insider_yfinance_fallback(symbol: str) -> str:
    """Internal yfinance fallback for US stock insider transactions."""
    try:
        import yfinance as yf
        data = yf.Ticker(symbol).insider_transactions
        if data is None or data.empty:
            return f"No insider transactions data found for US stock '{symbol}'."
        csv_str = data.to_csv()
        header = (
            f"# Insider Transactions data for {symbol.upper()}\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + csv_str
    except Exception:
        return f"Insider transactions not available for US stock '{symbol}'."
