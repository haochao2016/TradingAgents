# TODO

## 数据源优化

### Tushare Vendor（实施中）

**目标**：K线 + 财务报表使用 Tushare（稳定），新闻/内幕保留 akshare。

| 数据类别 | 主 vendor | 降级 vendor |
|---------|----------|------------|
| `core_stock_apis` | **tushare** | akshare |
| `technical_indicators` | **tushare** | akshare |
| `fundamental_data` | **tushare** | akshare |
| `news_data` | **akshare** | — |

**Tushare 接口映射**（2000 积分/200 元/年）：

| TradingAgents 功能 | Tushare API | 积分要求 |
|---|---|---|
| `get_stock_data` | `pro.daily(ts_code, start_date, end_date)` | 120 |
| `get_indicators` | `pro.daily()` OHLCV → stockstats 计算 | 120 |
| `get_fundamentals` | `pro.fina_indicator(ts_code)` + `pro.daily_basic(ts_code)` | 2000 |
| `get_balance_sheet` | `pro.balancesheet(ts_code)` | 2000 |
| `get_income_statement` | `pro.income(ts_code)` | 2000 |
| `get_cashflow` | `pro.cashflow(ts_code)` | 2000 |

### 数据源架构重构（待实施）

**目标**：4 个 vendor 都继承 `BaseDataSource`，`interface.py` 的 `VENDOR_METHODS` 从 dict 映射函数改为映射类实例。

```python
class BaseDataSource:
    def get_stock(self, symbol, start_date, end_date): raise NotImplementedError
    def get_indicator(self, symbol, indicator, curr_date, look_back_days): raise NotImplementedError
    def get_fundamentals(self, ticker, curr_date): raise NotImplementedError
    # ...

class TushareSource(BaseDataSource): ...
class AKShareSource(BaseDataSource): ...
class YFinanceSource(BaseDataSource): ...
class AlphaVantageSource(BaseDataSource): ...
```

通过 `.env` 配置选择默认 vendor，工厂函数根据配置创建实例。利于扩展、测试和统一缓存逻辑。

重构时同步完成以下缓存任务：

### SQLite 数据缓存

**目标**：tushare 和 akshare 拉回的数据通过 SQLite 缓存，避免重复远端请求。

目录：`data/tushare_cache/tushare.db`、`data/akshare_cache/akshare.db`

```sql
-- 行情表（按列展开，高频读取）
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol      TEXT,
    trade_date  TEXT,       -- "2026-05-10"
    open        REAL, high  REAL, low     REAL,
    close       REAL, adj_close REAL,
    volume      REAL, amount  REAL,
    PRIMARY KEY (symbol, trade_date)
);

-- 财务/其他低频数据（结构差异大，JSON 存储）
CREATE TABLE IF NOT EXISTS financial_cache (
    cache_key   TEXT PRIMARY KEY,
    data_json   TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**缓存逻辑**：查 ohlcv 先 `SELECT MIN/MAX/COUNT` → 覆盖范围足够则直接返回 → 不足则远端拉取 → `INSERT OR REPLACE` 增量写入。在 `BaseDataSource` 基类中统一实现 `_cache_ohlcv()` 和 `_cache_financial()` 方法，子类共享。
