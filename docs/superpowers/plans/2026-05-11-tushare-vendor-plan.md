# Tushare Vendor 实施计划

> **For agentic workers:** Inline execution.

**Goal:** 新增 Tushare 模块函数 vendor（A股），Tushare 失败时降级到 akshare。

**Architecture:** 参照现有 akshare 模式，4 个新文件 + 3 个修改，不改缓存。

---

### Task 1: .env 添加 TUSHARE_TOKEN

**Files:** Modify `.env`

```bash
TUSHARE_TOKEN=your_token_here
```

### Task 2: 创建 tushare_stock.py

**Files:** Create `tradingagents/dataflows/tushare_stock.py`

- 复用 `akshare_stock.py` 的 `_is_a_share`、`_add_a_share_suffix`
- `get_stock(symbol, start_date, end_date) → str`
- A股: `pro.daily(ts_code, start_date, end_date)` → 列名英文化 → CSV 输出
- 美股: `raise ValueError("Tushare only supports A-shares, fallback to next vendor")`
- 通过 `with_retry(lambda: pro.daily(...), name="pro.daily")` 包裹，5 次重试

### Task 3: 创建 tushare_fundamentals.py

**Files:** Create `tradingagents/dataflows/tushare_fundamentals.py`

- 4 函数: `get_fundamentals`, `get_balance_sheet`, `get_income_statement`, `get_cashflow`
- A股 → 调用对应 pro API，with_retry 包裹
- 美股 → raise ValueError 触发降级

### Task 4: 创建 tushare_indicator.py

**Files:** Create `tradingagents/dataflows/tushare_indicator.py`

- `get_indicator(symbol, indicator, curr_date, look_back_days, **kwargs)`
- `_load_ohlcv_tushare(symbol, curr_date)` → `pro.daily()` → stockstats
- 美股 → raise ValueError

### Task 5: 创建 tushare.py 重导出

**Files:** Create `tradingagents/dataflows/tushare.py`

```python
from .tushare_stock import get_stock
from .tushare_indicator import get_indicator
from .tushare_fundamentals import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
```

### Task 6: 修改 interface.py

**Files:** Modify `tradingagents/dataflows/interface.py`

- 添加 tushare import（9 个函数别名 `get_tushare_xxx`）
- `VENDOR_LIST` 追加 `"tushare"`
- 9 个 `VENDOR_METHODS` 各加 `"tushare": get_tushare_xxx`（news 类别除外）
- `route_to_vendor` 中 `except AlphaVantageRateLimitError` → `except Exception`

### Task 7: 修改 default_config.py

**Files:** Modify `tradingagents/default_config.py`

```python
"data_vendors": {
    "core_stock_apis": "tushare,akshare",
    "technical_indicators": "tushare,akshare",
    "fundamental_data": "tushare,akshare",
    "news_data": "akshare",
},
```

### Task 8: 验证

```bash
# A股 K线通过 tushare
conda run -n hollis-tradingagents-py313 python -c "from tradingagents.dataflows.tushare import get_stock; print('import OK')"

# 美股请求 tushare → 抛异常 → route_to_vendor 降级到 akshare
conda run -n hollis-tradingagents-py313 python -c "from tradingagents.dataflows.interface import route_to_vendor; r=route_to_vendor('get_stock_data','AAPL','2026-03-01','2026-05-01'); print('fallback OK, len:', len(r))"
```
