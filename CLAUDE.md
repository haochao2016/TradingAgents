# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install from source (preferred)
pip install .

# Run CLI (interactive mode or single analysis)
tradingagents
tradingagents analyze --ticker 000001 --date 2026-05-10

# Run from source
python -m cli.main
python -m cli.main analyze --ticker NVDA --date 2026-01-15

# Tests (use markers: unit, integration, smoke)
pytest
pytest -m unit
pytest tests/path/test_file.py::test_name -v
```

## Architecture

TradingAgents is a multi-agent trading framework built on **LangGraph**. The workflow graph (`tradingagents/graph/setup.py`) chains 13 nodes in sequence:

```
START → [Market Analyst → Social Analyst → News Analyst → Fundamentals Analyst]
         → Bull Researcher ↔ Bear Researcher (debate loop)
         → Research Manager → Trader
         → Aggressive ↔ Conservative ↔ Neutral Risk Analysts (debate loop)
         → Portfolio Manager → END
```

Each analyst node is an LLM agent with bound tools. Analyst selection is configurable (`selected_analysts` param). Two LLMs are used: `quick_thinking_llm` for analysts/debaters and `deep_thinking_llm` for managers.

## Data Vendors

Data fetching routes through `tradingagents/dataflows/interface.py` (`route_to_vendor`). Three vendors supported:

| Vendor | Stock focus | Access | Config key |
|--------|-------------|--------|------------|
| **akshare** (default) | A-share first, US compatible | Free, web-scraped, unstable in some regions | `"akshare"` |
| **yfinance** | US stocks | Free, blocked in mainland China | `"yfinance"` |
| **alpha_vantage** | Global | Free tier limited, API key required | `"alpha_vantage"` |

Default configured in `tradingagents/default_config.py` → `data_vendors`. Each of 4 categories (`core_stock_apis`, `technical_indicators`, `fundamental_data`, `news_data`) can use a different vendor. Tool-level overrides via `tool_vendors`. The fallback chain is built from the comma-separated vendor config; only `AlphaVantageRateLimitError` triggers fallback.

New vendors follow the file-per-category pattern: `{vendor}_stock.py`, `{vendor}_fundamentals.py`, `{vendor}_indicator.py`, `{vendor}_news.py`, plus a `{vendor}.py` re-export. Register in `interface.py` (imports, `VENDOR_LIST`, all 9 `VENDOR_METHODS` entries).

## LLM Providers

Multi-provider support via `tradingagents/llm_clients/factory.py`. Configuration keys in `default_config.py`:
- `llm_provider`: `"openai"`, `"google"`, `"anthropic"`, `"xai"`, `"deepseek"`, `"qwen"`, `"glm"`, `"openrouter"`, `"ollama"`, `"azure"`
- `deep_think_llm` / `quick_think_llm`: model names
- `backend_url`: override endpoint (None = provider default)

API keys via environment variables (`DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, etc.) or `.env` file.

## Key Directories

| Path | Purpose |
|------|---------|
| `tradingagents/agents/` | LLM agent definitions (analysts, researchers, risk, trader, managers) |
| `tradingagents/graph/` | LangGraph workflow (setup, conditional edges, propagation, checkpoint) |
| `tradingagents/dataflows/` | Data vendor implementations and routing |
| `tradingagents/llm_clients/` | Multi-provider LLM client wrappers |
| `tradingagents/agents/utils/` | Tool definitions (wrappers around `route_to_vendor`) and shared state |
| `cli/` | Typer CLI application |

## Windows / Conda Notes

- Conda environments on Windows with bash shell: `openssl_activate.sh` may set a broken `SSL_CERT_FILE` path (missing `Library/`). Workaround: set correct path in `.env`.
- Use `no_proxy="*"` for akshare when proxy misconfigured (`RemoteDisconnected` errors).
- Conda `python -c` with multi-line scripts fails; use single-line or write to temp file.
