# akshare 网络重试机制

**日期**: 2026-05-10
**状态**: draft

## 背景

akshare 依赖网络抓取东方财富等财经网站，网络抖动导致 `RemoteDisconnected` 等错误。
当前代码直接 try/except 一次即放弃，需要加入重试提升数据获取成功率。

## 设计

### 新增 `tradingagents/dataflows/retry.py`

统一的 `with_retry(func, max_retries=5, base_delay=1.0, name="")` 包装器：

- 最多重试 5 次
- 指数退避：1s → 2s → 4s → 8s
- 每轮记录日志：`logger.warning(f"[{name}] 第 {attempt}/{max_retries} 轮失败, {delay}s 后重试")`
- 5 轮全失败：`logger.error` + 抛出最后一个异常 → 被调用方现有 try/except 捕获 → 返回错误字符串

### 修改 4 个 akshare 模块

每个 `ak.xxx()` 调用用 `with_retry(lambda: ak.xxx(), name="...")` 包裹：

| 模块 | 包裹点 |
|------|--------|
| `akshare_stock.py` | `stock_zh_a_hist`, `stock_us_hist` |
| `akshare_fundamentals.py` | 全部 11 个 `ak.*` 调用 |
| `akshare_indicator.py` | 无需改动（内部调 stock 层） |
| `akshare_news.py` | `stock_news_em`, `stock_info_global_em`, `stock_inner_trade_xq` |

### 行为

现有 try/except → 返回错误字符串 → LLM 继续生成其他报告的流程不变。
