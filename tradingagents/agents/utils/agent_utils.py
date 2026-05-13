from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Only applied to user-facing agents (analysts, portfolio manager).
    Internal debate agents stay in English for reasoning quality.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def _resolve_company_name(ticker: str) -> str:
    """Look up the official company name for *ticker* from the configured data source.

    Returns the verified name string, or an empty string on failure.
    """
    try:
        from tradingagents.dataflows.base import is_a_share, add_a_share_suffix

        if not is_a_share(ticker):
            return ""

        api_sym = add_a_share_suffix(ticker)

        # Try tushare first (stock_basic has the official name)
        try:
            import tushare as ts
            from tradingagents.dataflows.config import get_config
            token = get_config().get("tushare_token", "")
            if token:
                ts.set_token(token)
                pro = ts.pro_api()
                df = pro.stock_basic(ts_code=api_sym, fields="name")
                if df is not None and not df.empty:
                    name = str(df.iloc[0]["name"]).strip()
                    if name:
                        return name
        except Exception:
            pass

        # Fallback: try akshare
        try:
            import akshare as ak
            info = ak.stock_individual_info_em(symbol=api_sym)
            if info is not None and not info.empty:
                for _, row in info.iterrows():
                    if str(row.get("item", "")) == "股票简称":
                        name = str(row.get("value", "")).strip()
                        if name:
                            return name
        except Exception:
            pass

    except Exception:
        pass
    return ""


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers.

    Also looks up the verified company name from the data source to prevent
    LLM hallucination (e.g. confusing 688271 联影医疗 for 华大智造).
    """
    name = _resolve_company_name(ticker)
    name_part = f" ({name})" if name else ""
    return (
        f"The instrument to analyze is `{ticker}`{name_part}. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`). "
        f"If the data source returns a different company name than what you thought, "
        f"TRUST THE DATA SOURCE. The ticker `{ticker}`{name_part} is the only correct instrument."
    )

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
