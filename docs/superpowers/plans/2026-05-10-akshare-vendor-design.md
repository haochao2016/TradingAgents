# 添加 akshare 作为 A 股优先数据源

**日期**: 2026-05-10
**状态**: draft

## 背景

TradingAgents 目前仅支持 yfinance 和 Alpha Vantage 两个数据源，两者均依赖国外 API，
在中国大陆无法正常访问。用户主要分析 A 股，而 akshare 对 A 股有成熟、稳定的原生支持。
本次改造将 akshare 集成作为默认数据源，yfinance 和 Alpha Vantage 保留为静默降级备选。

## 设计

### 架构：5 个新文件 + 3 个修改

```
tradingagents/dataflows/
  akshare_stock.py          ← OHLCV K线（A股: stock_zh_a_hist / 美股: stock_us_hist）
  akshare_fundamentals.py   ← 基本面 + 三张报表
  akshare_indicator.py      ← akshare取OHLCV → stockstats计算指标
  akshare_news.py           ← 新闻 + 内幕交易（A股原生 / 美股回退yfinance）
  akshare.py                ← 聚合重导出
```

修改文件：

- `tradingagents/dataflows/interface.py` — 注册 akshare 到 VENDOR_LIST 和 VENDOR_METHODS
- `tradingagents/default_config.py` — 将 4 个类别的默认值设为 `"akshare"`
- `pyproject.toml` — 添加 akshare 可选依赖

### 市场自动识别

根据 symbol 格式在每个 akshare 模块入口处判断：

| 格式 | 市场 | 后缀规则 |
|------|------|----------|
| `\d{6}` 纯数字 | A股 | `0xx/3xx` → `.SZ`, `6xx` → `.SH`, `4xx/8xx` → `.BJ` |
| `[A-Z]{1,5}` 纯字母 | 美股 | 直接使用，转大写 |

### 设计决策

**A 股优先的 API 选择。** 每个函数先判断市场，调用对应的 akshare API。
A 股接口（如 `stock_zh_a_hist`、`stock_balance_sheet_by_report_em`）为主路径；
美股接口（如 `stock_us_hist`、`stock_financial_us_report_em`）为辅路径。

**静默降级，不崩溃。** 所有 akshare API 调用均用 try/except 包裹。
失败时返回描述性错误字符串，绝不抛出异常。
配合 `route_to_vendor` 现有的降级链（`akshare → yfinance → alpha_vantage`），
确保分析主流程不会因数据获取失败而中断。

**新闻/内幕交易：美股回退 yfinance。** akshare 对 A 股的新闻和内部人交易有良好支持
（`stock_news_em`、`stock_inner_trade_xq`），但对美股个股无原生接口。
当 symbol 为美股时，`get_news` 和 `get_insider_transactions` 内部回退到 yfinance，
并用 try/except 双重保护。全球新闻统一使用 `stock_info_global_em()`。

**指标模块自带数据加载。** 指标模块包含独立的 `_load_ohlcv_akshare()` 辅助函数，
从 akshare 获取 OHLCV 并缓存，再交给 stockstats 计算指标。
不与 `stockstats_utils.load_ohlcv()`（使用 yfinance）共享代码，
保持 vendor 边界干净——每个数据源端到端拥有自己的数据管道。

### 逐函数规格

#### 1. `akshare_stock.py` — `get_stock(symbol, start_date, end_date) -> str`

- 根据 symbol 识别市场。
- A股：`ak.stock_zh_a_hist(symbol=<带后缀>, period="daily", start_date=<YYYYMMDD>, end_date=<YYYYMMDD>, adjust="qfq")`。
- 美股：`ak.stock_us_hist(symbol=<大写>, period="daily", start_date=<YYYYMMDD>, end_date=<YYYYMMDD>, adjust="qfq")`。
- 列名中译英：日期→Date, 开盘→Open, 收盘→Close, 最高→High, 最低→Low, 成交量→Volume, 成交额→Amount。
- "Adj Close" = Close（前复权价格已包含除权除息调整）。
- 日期格式转为 `YYYY-MM-DD`，升序排列，数值四舍五入，输出 CSV 带 `#` 信息头。
- 异常时返回报错字符串。

#### 2. `akshare_fundamentals.py` — 4 个函数

`get_fundamentals(ticker, curr_date=None) -> str`:
- A股：`ak.stock_individual_info_em(symbol=<带后缀>)` 获取公司概况；`ak.stock_financial_analysis_indicator(symbol=<带后缀>)` 获取财务比率。
- 美股：`ak.stock_us_spot_em()` 筛选 symbol → PE、市值；`ak.stock_individual_basic_info_us_xq(symbol)` → 公司描述；`ak.stock_financial_us_analysis_indicator_em(symbol)` → 财务比率。
- 输出英文标签的字段，格式与 yfinance 保持一致。

`get_balance_sheet(ticker, freq="quarterly", curr_date=None) -> str`:
`get_income_statement(ticker, freq="quarterly", curr_date=None) -> str`:
`get_cashflow(ticker, freq="quarterly", curr_date=None) -> str`:
- A股：`ak.stock_balance_sheet_by_report_em`、`ak.stock_profit_sheet_by_report_em`、`ak.stock_cash_flow_sheet_by_report_em`。
- 美股：`ak.stock_financial_us_report_em(symbol=<报表类型>)`，分别用 `资产负债表`/`综合损益表`/`现金流量表`。
- 筛选 `curr_date` 之后的列以防止前视偏差。
- CSV 输出带 `#` 信息头。

#### 3. `akshare_indicator.py` — `get_indicator(symbol, indicator, curr_date, look_back_days, **kwargs) -> str`

- 用 `y_finance.py` 中相同的 `best_ind_params` 字典校验 `indicator` 是否受支持。
- `_load_ohlcv_akshare(symbol, curr_date)` 辅助函数：从 akshare 获取 OHLCV（含 60 天缓冲用于 stockstats 预热），按 symbol 缓存到 `data_cache_dir`，清洗并过滤防止前视偏差。
- 输入 stockstats：`df = wrap(data)`，触发 `df[indicator]`，逐日提取指标值。
- 输出格式与 yfinance 一致：日期-数值行 + 指标说明。
- 接受额外的关键字参数（`interval`、`time_period`、`series_type`）以保证签名兼容，内部忽略。
- 异常返回描述性字符串。

#### 4. `akshare_news.py` — 3 个函数

`get_news(ticker, start_date, end_date) -> str`:
- A股：`ak.stock_news_em(symbol=<6位数字>)` → 按日期范围筛选 → 格式化文章列表。
- 美股：内部回退 yfinance（`yf.Ticker(...).news`）+ 完整 try/except 保护；失败则返回 `"个股新闻暂不支持美股。"`。

`get_global_news(curr_date, look_back_days=7, limit=50) -> str`:
- 所有市场：`ak.stock_info_global_em()` → 按日期筛选 → 格式化文章列表。
- 格式：`### {标题} (来源: {来源})\n{摘要}\n链接: {URL}`。

`get_insider_transactions(symbol) -> str`:
- A股：`ak.stock_inner_trade_xq(symbol=<6位数字>)` → CSV 格式。
- 美股：内部回退 yfinance + 完整 try/except 保护；失败则返回 `"内幕交易数据暂不支持美股。"`。

#### 5. `akshare.py` — 聚合重导出

遵循 `alpha_vantage.py` 的相同模式：导入全部 9 个函数并列入 `__all__`。

### 配置变更

`default_config.py`：
```python
"data_vendors": {
    "core_stock_apis": "akshare",       # 可选: akshare, yfinance, alpha_vantage
    "technical_indicators": "akshare",  # 可选: akshare, yfinance, alpha_vantage
    "fundamental_data": "akshare",      # 可选: akshare, yfinance, alpha_vantage
    "news_data": "akshare",             # 可选: akshare, yfinance, alpha_vantage
},
```

### 异常处理契约

| 层级 | 行为 |
|------|------|
| akshare 函数 | try/except → 返回报错字符串，绝不抛出 |
| yfinance 回退（新闻/内幕） | try/except → 返回描述性信息 |
| `route_to_vendor` 降级 | 仅捕获 `AlphaVantageRateLimitError`；其他异常向上传播（但 akshare 不会抛出） |
| LLM agent | 接收报错字符串作为工具输出，优雅处理 |

## 验证

1. `pip install akshare` — 安装依赖
2. 运行 `python -c "from tradingagents.dataflows.akshare_stock import get_stock; print(get_stock('000001', '2026-03-01', '2026-05-01')[:200])"` — 验证 A 股 K 线
3. 运行 `python -c "from tradingagents.dataflows.akshare_stock import get_stock; print(get_stock('AAPL', '2026-03-01', '2026-05-01')[:200])"` — 验证美股 K 线
4. 运行 `python -c "from tradingagents.dataflows.akshare_fundamentals import get_fundamentals; print(get_fundamentals('600519')[:300])"` — 验证基本面
5. 运行 `python -c "from tradingagents.dataflows.akshare_indicator import get_indicator; print(get_indicator('000001', 'rsi', '2026-05-08', 30))"` — 验证技术指标
6. 运行完整分析：`python -m cli.main analyze` 使用 A 股代码 — 验证端到端
