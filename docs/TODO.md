# TODO

## 数据源优化

### Tushare Vendor（等待购买 Tushare Pro 后实施）

**目标**：K线 + 财务报表使用 Tushare（稳定），新闻/内幕保留 akshare（免费且 Tushare 无对应接口）。

| 数据类别 | 当前（默认） | 计划（购买后） |
|---------|:----------:|:----------:|
| `core_stock_apis` | akshare | **Tushare**（200 元/年 套餐内） |
| `technical_indicators` | akshare | **Tushare OHLCV → stockstats 计算** |
| `fundamental_data` | akshare | **Tushare**（200 元/年 套餐内） |
| `news_data` | akshare（保留） | akshare（保留，Tushare 无全球新闻/内幕交易） |

**Tushare 接口映射**：

| TradingAgents 功能 | Tushare API |
|------|------|
| `get_stock_data` | `pro.daily()` — A 股日线复权行情 |
| `get_indicators` | 同上获取 OHLCV → stockstats 计算 |
| `get_fundamentals` | `pro.daily_basic()` + `pro.fina_indicator()` |
| `get_balance_sheet` | `pro.balancesheet()` |
| `get_income_statement` | `pro.income()` |
| `get_cashflow` | `pro.cashflow()` |

**实施**：参照 `alpha_vantage` 的文件模式，新增 4 个模块（`tushare_stock.py` / `tushare_fundamentals.py` / `tushare_indicator.py` / `tushare.py`），在 `interface.py` 注册为 `"tushare"` vendor。不需要新闻模块（akshare 保留）。
