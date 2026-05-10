# akshare 重试机制 — 实施计划

> **For agentic workers:** Inline execution.

**Goal:** 对所有 akshare API 调用增加 5 次重试 + 指数退避 + 日志记录。

**Architecture:** 新建 `retry.py` 通用包装器，在 4 个 akshare 模块中用 `with_retry(lambda: ak.xxx(), name="...")` 包裹每个 `ak.*()` 调用。

---

### Task 1: 创建 retry.py 通用重试模块

**Files:** Create `tradingagents/dataflows/retry.py`

- [ ] 写入：

```python
"""Generic retry wrapper used by data-fetching modules."""
import time
import logging

logger = logging.getLogger(__name__)


def with_retry(func, max_retries=5, base_delay=1.0, name="call"):
    """Call *func* with retry + exponential backoff on any exception.

    Logs each attempt number. After *max_retries* failures, re-raises
    the last exception so the caller's existing try/except catches it.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    f"[{name}] 第 {attempt}/{max_retries} 轮失败, "
                    f"{delay:.0f}s 后重试: {e}"
                )
                time.sleep(delay)
            else:
                logger.error(f"[{name}] 全部 {max_retries} 轮重试均失败: {e}")
                raise
```

### Task 2: 修改 akshare_stock.py

**Files:** Modify `tradingagents/dataflows/akshare_stock.py`

- [ ] 在文件顶部 `import pandas as pd` 之后添加 `from .retry import with_retry`
- [ ] `_fetch_ohlcv_a_share`: 将 `df = ak.stock_zh_a_hist(...)` 改为 `df = with_retry(lambda: ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq"), name="stock_zh_a_hist")`
- [ ] `_fetch_ohlcv_us`: 同样包裹 `ak.stock_us_hist(...)` 调用

### Task 3: 修改 akshare_fundamentals.py

**Files:** Modify `tradingagents/dataflows/akshare_fundamentals.py`

- [ ] 顶部添加 `from .retry import with_retry`
- [ ] 逐个包裹所有 `ak.*()` 调用（约 11 处），每处用 `with_retry(lambda: ak.xxx(...), name="xxx")` 替换直接调用

### Task 4: 修改 akshare_indicator.py / akshare_news.py

**Files:** Modify `tradingagents/dataflows/akshare_indicator.py`, `tradingagents/dataflows/akshare_news.py`

- [ ] `akshare_indicator.py`: 添加 import，包裹 `_load_ohlcv_akshare` 中的 akshare 调用
- [ ] `akshare_news.py`: 添加 import，包裹 `stock_news_em`, `stock_info_global_em`, `stock_inner_trade_xq` 调用

### Task 5: 验证

- [ ] 运行 `conda run -n hollis-tradingagents-py313 python -c "from tradingagents.dataflows.retry import with_retry; import time; with_retry(lambda: 1/0, max_retries=3, base_delay=0.1)"` — 应看到 3 轮日志后抛出 ZeroDivisionError
