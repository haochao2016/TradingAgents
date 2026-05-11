# Tushare Vendor + SQLite 缓存 + 降级机制

**日期**: 2026-05-11
**状态**: draft

## 1. 数据源分层

| 类别 | 主 vendor | 降级 vendor |
|------|-----------|------------|
| `core_stock_apis` | **tushare** | akshare |
| `technical_indicators` | **tushare** | akshare |
| `fundamental_data` | **tushare** | akshare |
| `news_data` | **akshare**（无降级） | — |

Tushare 仅覆盖 A 股。美股请求 → `raise ValueError("Tushare only supports A-shares")` → 触发降级到 akshare。

## 2. 新增/修改文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `tradingagents/dataflows/cache.py` | 通用 SQLite 缓存（ohlcv + financial_cache 两表） |
| 新建 | `tradingagents/dataflows/tushare.py` | 聚合重导出（无 news） |
| 新建 | `tradingagents/dataflows/tushare_stock.py` | `get_stock()` via `pro.daily()` |
| 新建 | `tradingagents/dataflows/tushare_fundamentals.py` | 4 个财务函数 |
| 新建 | `tradingagents/dataflows/tushare_indicator.py` | `get_indicator()` via tushare OHLCV → stockstats |
| 修改 | `tradingagents/dataflows/interface.py` | 注册 tushare + 全异常降级 |
| 修改 | `tradingagents/default_config.py` | `akshare_cache_dir`、`tushare_cache_dir` |
| 修改 | `.env` | `TUSHARE_TOKEN` |
| 修改 | 4 个 akshare 模块 | 接入 `cache.py` |

## 3. SQLite 缓存

目录：`data/akshare_cache/akshare.db`、`data/tushare_cache/tushare.db`

```sql
-- 行情表（按列展开，前复权为默认）
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol      TEXT,
    trade_date  TEXT,       -- "2026-05-10"
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    adj_close   REAL,
    volume      REAL,
    amount      REAL,
    PRIMARY KEY (symbol, trade_date)
);

-- 财务/其他数据（结构差异大，JSON 存储）
CREATE TABLE IF NOT EXISTS financial_cache (
    cache_key   TEXT PRIMARY KEY,
    data_json   TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**缓存策略**：查 OHLCV 先 `SELECT MIN(trade_date), MAX(trade_date), COUNT(*)` → 覆盖当前查询范围足够则直接返回 → 不足则远端拉取 → `INSERT OR REPLACE` 增量写入。

**复权**：默认前端复权（`qfq`/`adj="qfq"`），参数保留其他选项。

## 4. 降级机制

修改 `interface.py` 中 `route_to_vendor`：
- `except AlphaVantageRateLimitError` → `except Exception`
- 降级前 `logger.warning(f"[fallback] {vendor} failed: {e}, trying next...")`

## 5. Tushare 函数规范

| 函数 | Tushare API | 积分 |
|------|------------|:--:|
| `get_stock(symbol, start, end)` | `pro.daily(ts_code, start_date, end_date)` + `adj="qfq"` | 120 |
| `get_fundamentals(ticker, curr_date)` | `pro.fina_indicator(ts_code)` + `pro.daily_basic(ts_code)` | 2000 |
| `get_balance_sheet(ticker, freq, curr_date)` | `pro.balancesheet(ts_code)` | 2000 |
| `get_income_statement(ticker, freq, curr_date)` | `pro.income(ts_code)` | 2000 |
| `get_cashflow(ticker, freq, curr_date)` | `pro.cashflow(ts_code)` | 2000 |
| `get_indicator(symbol, indicator, curr_date, look_back)` | `pro.daily()` OHLCV → stockstats | 120 |

所有 Tushare 调用通过 `with_retry(tushare_call, name="xxx")` 包裹（复用 `retry.py`，默认 5 次重试）。

美股识别：`_is_a_share(symbol)` 返回 False → `raise ValueError(...)` → 降级到 akshare。

## 6. .env 新增

```bash
TUSHARE_TOKEN=your_token_here
```

## 7. 复用

- 市场识别 `_is_a_share()`、`_add_a_share_suffix()` 从 `akshare_stock.py` import
- `with_retry()` 从 `retry.py` import
- `cache.py` 同时用于 tushare 和 akshare
