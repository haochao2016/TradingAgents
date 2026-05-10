# akshare A 股优先数据源 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 集成 akshare 作为默认数据源，A 股优先，美股兼容，yfinance/Alpha Vantage 作为静默降级备选。

**Architecture:** 5 个新文件（akshare_stock / akshare_fundamentals / akshare_indicator / akshare_news / akshare 聚合模块）遵循 alpha_vantage 的模块划分模式，3 个文件修改（interface / default_config / pyproject.toml）。

**Tech Stack:** Python 3.13, akshare, pandas, stockstats, langchain

**环境:** conda 环境 `hollis-tradingagents-py313`

---

### Task 1: 安装 akshare 依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 添加 akshare 到 pyproject.toml 依赖列表**

```toml
# 在 dependencies 数组中添加
"akshare>=1.16.0",
```

在 `"yfinance>=0.2.63",` 的下一行插入：
```
    "akshare>=1.16.0",
```

- [ ] **Step 2: 安装 akshare**

```bash
conda run -n hollis-tradingagents-py313 pip install akshare
```

Expected: akshare 及其依赖成功安装，无报错。

- [ ] **Step 3: 提交**（跳过 — 用户手动操作）

---

### Task 2: 创建 akshare_stock.py — OHLCV K线数据

**Files:**
- Create: `tradingagents/dataflows/akshare_stock.py`

- [ ] **Step 1: 写入模块**

```python
"""akshare-based OHLCV stock data fetch — A-share first, US fallback."""
import re
from datetime import datetime
import pandas as pd
from .config import get_config


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

    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq",
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

    df = ak.stock_us_hist(
        symbol=symbol.upper(),
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq",
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
```

- [ ] **Step 2: 提交**（跳过 — 用户手动操作）

---

### Task 3: 创建 akshare_fundamentals.py — 基本面与三张报表

**Files:**
- Create: `tradingagents/dataflows/akshare_fundamentals.py`

- [ ] **Step 1: 写入模块**

```python
"""akshare-based fundamental data — A-share first, US fallback."""
from datetime import datetime
import pandas as pd
from .akshare_stock import _is_a_share, _add_a_share_suffix


# ── helpers ────────────────────────────────────────────────────────


def _get_a_share_company_info(symbol: str) -> dict:
    """Return key-value pairs for an A-share company."""
    import akshare as ak

    info = {}
    try:
        raw = ak.stock_individual_info_em(symbol=symbol)
        if raw is not None and not raw.empty:
            for _, row in raw.iterrows():
                key = str(row.get("item", ""))
                val = str(row.get("value", ""))
                if key and val and val.lower() != "none":
                    info[key] = val
    except Exception:
        pass

    try:
        indicators = ak.stock_financial_analysis_indicator(symbol=symbol)
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
        spot = ak.stock_us_spot_em()
        row = spot[spot["代码"] == symbol.upper()]
        if not row.empty:
            r = row.iloc[0]
            info["Market Cap"] = r.get("总市值")
            info["PE Ratio (TTM)"] = r.get("市盈率")
            info["Price"] = r.get("最新价")
    except Exception:
        pass

    try:
        basic = ak.stock_individual_basic_info_us_xq(symbol=symbol.upper())
        if basic is not None and not basic.empty:
            for _, r in basic.iterrows():
                k = str(r.get("item", ""))
                v = str(r.get("value", ""))
                if k and v and v.lower() != "none":
                    info[k] = v
    except Exception:
        pass

    try:
        fin = ak.stock_financial_us_analysis_indicator_em(symbol=symbol.upper(), indicator="年报")
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
            df = ak.stock_balance_sheet_by_report_em(symbol=api_sym)
        else:
            import akshare as ak
            df = ak.stock_financial_us_report_em(stock=ticker.upper(), symbol="资产负债表", indicator="年报")

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
            df = ak.stock_profit_sheet_by_report_em(symbol=api_sym)
        else:
            import akshare as ak
            df = ak.stock_financial_us_report_em(stock=ticker.upper(), symbol="综合损益表", indicator="年报")

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
            df = ak.stock_cash_flow_sheet_by_report_em(symbol=api_sym)
        else:
            import akshare as ak
            df = ak.stock_financial_us_report_em(stock=ticker.upper(), symbol="现金流量表", indicator="年报")

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
```

- [ ] **Step 2: 提交**（跳过 — 用户手动操作）

---

### Task 4: 创建 akshare_indicator.py — 技术指标

**Files:**
- Create: `tradingagents/dataflows/akshare_indicator.py`

- [ ] **Step 1: 写入模块**

```python
"""akshare-based technical indicators via stockstats — A-share first."""
import os
from datetime import datetime
import pandas as pd
from dateutil.relativedelta import relativedelta
from stockstats import wrap
from .config import get_config
from .akshare_stock import _is_a_share, _add_a_share_suffix, _fetch_ohlcv_a_share, _fetch_ohlcv_us


# ── indicator descriptions (shared with yfinance) ──────────────────

BEST_IND_PARAMS = {
    "close_50_sma": (
        "50 SMA: A medium-term trend indicator. "
        "Usage: Identify trend direction and serve as dynamic support/resistance. "
        "Tips: It lags price; combine with faster indicators for timely signals."
    ),
    "close_200_sma": (
        "200 SMA: A long-term trend benchmark. "
        "Usage: Confirm overall market trend and identify golden/death cross setups. "
        "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
    ),
    "close_10_ema": (
        "10 EMA: A responsive short-term average. "
        "Usage: Capture quick shifts in momentum and potential entry points. "
        "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
    ),
    "macd": (
        "MACD: Computes momentum via differences of EMAs. "
        "Usage: Look for crossovers and divergence as signals of trend changes. "
        "Tips: Confirm with other indicators in low-volatility or sideways markets."
    ),
    "macds": (
        "MACD Signal: An EMA smoothing of the MACD line. "
        "Usage: Use crossovers with the MACD line to trigger trades. "
        "Tips: Should be part of a broader strategy to avoid false positives."
    ),
    "macdh": (
        "MACD Histogram: Shows the gap between the MACD line and its signal. "
        "Usage: Visualize momentum strength and spot divergence early. "
        "Tips: Can be volatile; complement with additional filters in fast-moving markets."
    ),
    "rsi": (
        "RSI: Measures momentum to flag overbought/oversold conditions. "
        "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
        "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
    ),
    "boll": (
        "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
        "Usage: Acts as a dynamic benchmark for price movement. "
        "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
    ),
    "boll_ub": (
        "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
        "Usage: Signals potential overbought conditions and breakout zones. "
        "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
    ),
    "boll_lb": (
        "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
        "Usage: Indicates potential oversold conditions. "
        "Tips: Use additional analysis to avoid false reversal signals."
    ),
    "atr": (
        "ATR: Averages true range to measure volatility. "
        "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
        "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
    ),
    "vwma": (
        "VWMA: A moving average weighted by volume. "
        "Usage: Confirm trends by integrating price action with volume data. "
        "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
    ),
    "mfi": (
        "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
        "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
        "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
    ),
}


# ── data loading ───────────────────────────────────────────────────


def _load_ohlcv_akshare(symbol: str, curr_date: str) -> pd.DataFrame:
    """Fetch OHLCV from akshare with caching, filtered to prevent look-ahead bias."""
    config = get_config()
    curr_date_dt = pd.to_datetime(curr_date)

    today_date = pd.Timestamp.today()
    start_date = today_date - pd.DateOffset(years=5)
    start_str = start_date.strftime("%Y%m%d")
    end_str = today_date.strftime("%Y%m%d")

    os.makedirs(config["data_cache_dir"], exist_ok=True)
    data_file = os.path.join(
        config["data_cache_dir"],
        f"{symbol}-akshare-data-{start_str}-{end_str}.csv",
    )

    if os.path.exists(data_file):
        data = pd.read_csv(data_file, on_bad_lines="skip", encoding="utf-8")
    else:
        if _is_a_share(symbol):
            api_sym = _add_a_share_suffix(symbol)
            df = _fetch_ohlcv_a_share(api_sym, start_str, end_str)
        else:
            df = _fetch_ohlcv_us(symbol.upper(), start_str, end_str)
        data = df
        if data is not None and not data.empty:
            data.to_csv(data_file, index=False, encoding="utf-8")

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


# ── public function ────────────────────────────────────────────────


def get_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
    interval: str = "daily",
    time_period: int = 14,
    series_type: str = "close",
) -> str:
    """Get technical indicator values over a look-back window.

    Accepts extra keyword args for signature compatibility with the Alpha
    Vantage vendor; they are silently ignored.
    """
    if indicator not in BEST_IND_PARAMS:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(BEST_IND_PARAMS.keys())}"
        )

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    try:
        data = _load_ohlcv_akshare(symbol, curr_date)
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
    except Exception as e:
        return f"Error retrieving {indicator} data for {symbol}: {str(e)}"
```

- [ ] **Step 2: 提交**（跳过 — 用户手动操作）

---

### Task 5: 创建 akshare_news.py — 新闻与内幕交易

**Files:**
- Create: `tradingagents/dataflows/akshare_news.py`

- [ ] **Step 1: 写入模块**

```python
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
```

- [ ] **Step 2: 提交**（跳过 — 用户手动操作）

---

### Task 6: 创建 akshare.py — 聚合重导出

**Files:**
- Create: `tradingagents/dataflows/akshare.py`

- [ ] **Step 1: 写入模块**

```python
"""akshare data vendor — A-share first, US stock compatible."""
from .akshare_stock import get_stock
from .akshare_indicator import get_indicator
from .akshare_fundamentals import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
from .akshare_news import get_news, get_global_news, get_insider_transactions

__all__ = [
    "get_stock",
    "get_indicator",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_news",
    "get_global_news",
    "get_insider_transactions",
]
```

- [ ] **Step 2: 提交**（跳过 — 用户手动操作）

---

### Task 7: 修改 interface.py — 注册 akshare vendor

**Files:**
- Modify: `tradingagents/dataflows/interface.py`

- [ ] **Step 1: 添加 akshare 导入**

在第 25 行（Alpha Vantage 导入块之后，AlphaVantageRateLimitError 导入之前）添加：

```python
from .akshare import (
    get_stock as get_akshare_stock,
    get_indicator as get_akshare_indicator,
    get_fundamentals as get_akshare_fundamentals,
    get_balance_sheet as get_akshare_balance_sheet,
    get_cashflow as get_akshare_cashflow,
    get_income_statement as get_akshare_income_statement,
    get_insider_transactions as get_akshare_insider_transactions,
    get_news as get_akshare_news,
    get_global_news as get_akshare_global_news,
)
```

- [ ] **Step 2: 添加 "akshare" 到 VENDOR_LIST**

把：
```python
VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
]
```

改为：
```python
VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "akshare",
]
```

- [ ] **Step 3: 在每个 VENDOR_METHODS 条目中添加 akshare 映射**

把 `VENDOR_METHODS` 字典中 9 个条目全部添加 `"akshare"` key：

```python
VENDOR_METHODS = {
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "akshare": get_akshare_stock,
    },
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "akshare": get_akshare_indicator,
    },
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
        "akshare": get_akshare_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
        "akshare": get_akshare_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
        "akshare": get_akshare_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
        "akshare": get_akshare_income_statement,
    },
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
        "akshare": get_akshare_news,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
        "akshare": get_akshare_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
        "akshare": get_akshare_insider_transactions,
    },
}
```

- [ ] **Step 4: 提交**（跳过 — 用户手动操作）

---

### Task 8: 修改 default_config.py — akshare 设为默认

**Files:**
- Modify: `tradingagents/default_config.py`

- [ ] **Step 1: 更新默认值**

把：
```python
"data_vendors": {
    "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
    "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
    "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
    "news_data": "yfinance",             # Options: alpha_vantage, yfinance
},
```

改为：
```python
"data_vendors": {
    "core_stock_apis": "akshare",       # Options: akshare, yfinance, alpha_vantage
    "technical_indicators": "akshare",  # Options: akshare, yfinance, alpha_vantage
    "fundamental_data": "akshare",      # Options: akshare, yfinance, alpha_vantage
    "news_data": "akshare",             # Options: akshare, yfinance, alpha_vantage
},
```

- [ ] **Step 2: 提交**（跳过 — 用户手动操作）

---

### Task 9: 验证 — A 股 K 线数据

- [ ] **Step 1: 测试 A 股 K 线获取**

```bash
conda run -n hollis-tradingagents-py313 python -c "from tradingagents.dataflows.akshare_stock import get_stock; result = get_stock('000001', '2026-03-01', '2026-05-01'); print(result[:300])"
```

Expected: 输出包含 `# Stock data for 000001` 头部的 CSV 格式 K 线数据，Date/Open/High/Low/Close/Adj Close/Volume 列。

- [ ] **Step 2: 测试美股 K 线获取**

```bash
conda run -n hollis-tradingagents-py313 python -c "from tradingagents.dataflows.akshare_stock import get_stock; result = get_stock('AAPL', '2026-03-01', '2026-05-01'); print(result[:300])"
```

Expected: 输出包含 `# Stock data for AAPL` 头部的 CSV 格式 K 线数据。

---

### Task 10: 验证 — 基本面与技术指标

- [ ] **Step 1: 测试基本面**

```bash
conda run -n hollis-tradingagents-py313 python -c "from tradingagents.dataflows.akshare_fundamentals import get_fundamentals; result = get_fundamentals('600519'); print(result[:500])"
```

Expected: 输出包含 `# Company Fundamentals for 600519` 和字段列表。

- [ ] **Step 2: 测试技术指标**

```bash
conda run -n hollis-tradingagents-py313 python -c "from tradingagents.dataflows.akshare_indicator import get_indicator; result = get_indicator('000001', 'rsi', '2026-05-08', 30); print(result[:500])"
```

Expected: 输出包含 `## rsi values from` 和日期-数值列表 + 指标说明。

- [ ] **Step 3: 测试新闻**

```bash
conda run -n hollis-tradingagents-py313 python -c "from tradingagents.dataflows.akshare_news import get_global_news; result = get_global_news('2026-05-08'); print(result[:500])"
```

Expected: 输出包含 `## Global Market News` 和新闻条目。

- [ ] **Step 4: 验证 route_to_vendor 路由**

```bash
conda run -n hollis-tradingagents-py313 python -c "from tradingagents.dataflows.interface import route_to_vendor; result = route_to_vendor('get_stock_data', '000001', '2026-03-01', '2026-05-01'); print(result[:200])"
```

Expected: 因为 default_config 已设为 akshare，应走 akshare 路径，输出 A 股 K 线数据。

---

### Task 11: 最终验证 — 端到端 CLI 运行

- [ ] **Step 1: 运行完整分析**

```bash
cd d:/Workspace/PythonCommunity/TradingAgents && conda run -n hollis-tradingagents-py313 python -m cli.main
```

Expected: CLI 启动无 import 报错，可以正常进入分析流程。选择一个 A 股代码（如 000001）进行验证。
