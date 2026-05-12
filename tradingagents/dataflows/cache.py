"""SQLite cache for OHLCV and financial data."""
import sqlite3
import json
import os
import pandas as pd


class DataCache:
    """SQLite-backed cache with OHLCV columnar table and financial JSON table."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_tables()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_tables(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv (
                    symbol      TEXT,
                    trade_date  TEXT,
                    open        REAL,
                    high        REAL,
                    low         REAL,
                    close       REAL,
                    adj_close   REAL,
                    volume      REAL,
                    amount      REAL,
                    PRIMARY KEY (symbol, trade_date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS financial_cache (
                    cache_key   TEXT PRIMARY KEY,
                    data_json   TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    # ── OHLCV ──────────────────────────────────────────────────

    def load_ohlcv(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Load cached OHLCV data for *symbol* in the given date range."""
        with self._connect() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM ohlcv WHERE symbol = ? AND trade_date >= ? AND trade_date <= ? ORDER BY trade_date",
                conn,
                params=(symbol, start_date, end_date),
            )
        if not df.empty and "symbol" in df.columns:
            df = df.drop(columns=["symbol"])
        return df

    def ohlcv_range(self, symbol: str):
        """Return (min_date, max_date, count) for cached OHLCV data."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM ohlcv WHERE symbol = ?",
                (symbol,),
            ).fetchone()
        return row if row else (None, None, 0)

    def save_ohlcv(self, symbol: str, df: pd.DataFrame):
        """Insert or replace OHLCV rows for *symbol*."""
        if df is None or df.empty:
            return
        with self._connect() as conn:
            for _, row in df.iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO ohlcv
                       (symbol, trade_date, open, high, low, close, adj_close, volume, amount)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        symbol,
                        str(row.get("Date", "")),
                        row.get("Open"),
                        row.get("High"),
                        row.get("Low"),
                        row.get("Close"),
                        row.get("Adj Close"),
                        row.get("Volume"),
                        row.get("Amount"),
                    ),
                )

    # ── Financial ───────────────────────────────────────────────

    def get_financial(self, cache_key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM financial_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        return row[0] if row else None

    def set_financial(self, cache_key: str, data_json: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO financial_cache (cache_key, data_json) VALUES (?, ?)",
                (cache_key, data_json),
            )
