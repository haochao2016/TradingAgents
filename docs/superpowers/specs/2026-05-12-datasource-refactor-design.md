# BaseDataSource 重构 + SQLite 缓存

**日期**: 2026-05-12
**状态**: draft

## 1. 类层次

```
BaseDataSource (tradingagents/dataflows/base.py)
├── TushareSource       ← A股 K线+财务，默认数据源
├── AKShareSource        ← A股全类+美股+新闻
├── YFinanceSource       ← 美股+新闻
└── AlphaVantageSource   ← 全球
```

BaseDataSource 定义 9 个方法签名，默认抛出 `NotImplementedError`。子类按需覆盖。

## 2. 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `dataflows/base.py` | BaseDataSource + 市场检测（`_is_a_share`, `_add_a_share_suffix`） |
| 新建 | `dataflows/cache.py` | SQLite 缓存（ohlcv + financial_cache 两表） |
| 新建 | `dataflows/tushare_source.py` | TushareSource（A股，6 个方法） |
| 新建 | `dataflows/akshare_source.py` | AKShareSource（全部 9 个方法） |
| 新建 | `dataflows/yfinance_source.py` | YFinanceSource（现有逻辑封装为类） |
| 新建 | `dataflows/alpha_vantage_source.py` | AlphaVantageSource（现有逻辑封装为类） |
| 修改 | `dataflows/interface.py` | VENDOR_METHODS 改为使用类实例 |
| 修改 | `dataflows/retry.py` | 不变，复用 |
| 删除 | `dataflows/akshare*.py` | 4 个旧模块，逻辑迁入 `akshare_source.py` |
| 删除 | `dataflows/tushare*.py` | 4 个旧模块，逻辑迁入 `tushare_source.py` |

## 3. SQLite 缓存

路径: `data/tushare_cache/tushare.db` / `data/akshare_cache/akshare.db`

```sql
CREATE TABLE ohlcv (symbol TEXT, trade_date TEXT, open, high, low, close, adj_close, volume, amount, PRIMARY KEY(symbol, trade_date));
CREATE TABLE financial_cache (cache_key TEXT PRIMARY KEY, data_json TEXT, created_at DEFAULT CURRENT_TIMESTAMP);
```

方法: `load_ohlcv(symbol, start, end) → pd.DataFrame`（查本地→不足补远端→`save_ohlcv`）, `save_ohlcv(symbol, df)`, `get_financial(key)`, `set_financial(key, json)`.

## 4. interface.py

VENDOR_METHODS 按键映射到类实例方法。`route_to_vendor` 逻辑不变。

## 5. 配置

`.env` 中 `DEFAULT_VENDOR=tushare`，`TUSHARE_TOKEN=xxx`。`default_config.py` 中 `data_vendors` 不变。

## 6. 行为

- OHLCV 默认前复权
- Tushare 调用 `with_retry`，5 次重试
- 美股请求 → Tushare → NotImplementedError → 降级 akshare
- 缓存优先：先查本地 SQLite → 范围不够 → 远端拉取 → 增量写入
