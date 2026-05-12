"""Verify Tushare data caching to SQLite.

Usage:  conda run -n hollis-tradingagents-py313 python tools/verify_tushare_cache.py [ticker]
"""
import sys, os
from datetime import datetime
from dotenv import find_dotenv, load_dotenv

# Load .env before anything else (same as cli/main.py does)
load_dotenv(find_dotenv(usecwd=True))

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Verify token is loaded
token = os.getenv("TUSHARE_TOKEN", "")
print(f"[Token检查] TUSHARE_TOKEN={'***' + token[-8:] if len(token) > 8 else '未设置'}")

from tradingagents.dataflows.tushare_source import TushareSource
from tradingagents.dataflows.cache import DataCache


TICKER = sys.argv[1] if len(sys.argv) > 1 else "600519"
CACHE_DB = "data/tushare_cache/tushare.db"


def main():
    print(f"=== Tushare SQLite 缓存验证 ===")
    print(f"Ticker: {TICKER}")
    print(f"Cache DB: {CACHE_DB}")
    print()

    # 1. Check cache before any fetch
    cache = DataCache(CACHE_DB)
    min_d, max_d, count = cache.ohlcv_range(f"{TICKER}.SH")
    print(f"[缓存状态] {TICKER}.SH 已有 {count} 条记录, 日期范围: {min_d} ~ {max_d}")
    print()

    # 2. Create source and fetch
    source = TushareSource(cache_db=CACHE_DB)
    start = "2026-03-01"
    end = "2026-05-01"

    print(f"[拉取数据] {TICKER} from {start} to {end} ...")
    try:
        result = source.get_stock(TICKER, start, end)
    except Exception as e:
        result = f"Error: {e}"

    if "Error" in result:
        print(f"  FAIL: {result[:200]}")
        print(f"  提示: 请检查 .env 中 TUSHARE_TOKEN 是否正确")
    else:
        print(f"  OK: {len(result)} 字符")
        print(f"  预览:\n{result[:400]}")

    print()

    # 3. Verify cache after fetch
    min_d, max_d, count = cache.ohlcv_range(f"{TICKER}.SH")
    print(f"[缓存状态] {TICKER}.SH 现有 {count} 条记录, 日期范围: {min_d} ~ {max_d}")

    if count > 0:
        print()
        print("[缓存数据样例]")
        df = cache.load_ohlcv(f"{TICKER}.SH", start, end)
        if not df.empty:
            print(df.head(5).to_string())
            print(f"\n  共 {len(df)} 行")

    # 4. Second fetch — should hit cache
    print()
    print(f"[二次拉取] {TICKER} from {start} to {end} (应从缓存读取)...")
    try:
        result2 = source.get_stock(TICKER, start, end)
    except Exception as e:
        result2 = f"Error: {e}"

    if "Error" in result2:
        print(f"  FAIL: {result2[:200]}")
    else:
        print(f"  OK: {len(result2)} 字符 (与首次{'一致' if result == result2 else '不一致'})")

    print()
    print("=== 验证完成 ===")


if __name__ == "__main__":
    main()
