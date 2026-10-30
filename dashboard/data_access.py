"""
data_access.py - the ONLY place where the dashboard, simulator and report
talk to storage.

Default source is Cassandra (the NoSQL layer of our pipeline):
    transactions   -> every sale (raw / "live" data)
    sales_summary  -> MapReduce results (batch view)

Fallback source "files" reads the same information from local files:
    data/*.csv                 -> every sale
    results/sales_summary.csv  -> MapReduce results (copied out of HDFS)
Use it only if Cassandra is not running:   export RETAIL_SOURCE=files
"""
import glob
import os
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
RESULTS_FILE = PROJECT_DIR / "results" / "sales_summary.csv"

SOURCE = os.environ.get("RETAIL_SOURCE", "cassandra").lower()
CASSANDRA_HOST = os.environ.get("CASSANDRA_HOST", "127.0.0.1")
CASSANDRA_PORT = int(os.environ.get("CASSANDRA_PORT", "9042"))
KEYSPACE = "retail_analytics"

TXN_COLUMNS = ["transaction_id", "txn_date", "txn_time", "branch", "product_id",
               "product_name", "category", "quantity", "unit_price",
               "total_amount", "customer_id", "payment_method"]
SUMMARY_COLUMNS = ["dimension", "item", "transactions", "quantity", "revenue"]

_session = None
_insert_stmts = None


def get_session():
    """Open (once) a connection to Cassandra and return the session."""
    global _session
    if _session is None:
        from cassandra.cluster import Cluster
        from cassandra.query import dict_factory
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
        _session = cluster.connect(KEYSPACE)
        _session.row_factory = dict_factory      # each row comes back as a dict
    return _session


def _tidy_transactions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=TXN_COLUMNS)
    df = df[TXN_COLUMNS].copy()
    # Cassandra returns its own Date type; str() gives 'YYYY-MM-DD'
    df["txn_date"] = pd.to_datetime(df["txn_date"].astype(str))
    for c in ("quantity", "unit_price", "total_amount"):
        df[c] = pd.to_numeric(df[c]).astype("int64")
    return df.sort_values(["txn_date", "txn_time", "transaction_id"]).reset_index(drop=True)


def load_transactions(source: str = None) -> pd.DataFrame:
    """All sales as a DataFrame."""
    source = (source or SOURCE).lower()
    if source == "files":
        files = sorted(glob.glob(str(DATA_DIR / "*.csv")))
        frames = [pd.read_csv(f) for f in files]
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not df.empty:
            df = df.drop_duplicates("transaction_id", keep="last")
        return _tidy_transactions(df)
    session = get_session()
    # Fine for a few thousand rows. With millions of rows we would NOT scan the
    # whole table - we would read a pre-aggregated table instead (sales_summary).
    rows = session.execute("SELECT * FROM transactions")
    return _tidy_transactions(pd.DataFrame(list(rows)))


def load_summary(source: str = None) -> pd.DataFrame:
    """MapReduce results (batch view) as a DataFrame."""
    source = (source or SOURCE).lower()
    if source == "files":
        if not RESULTS_FILE.exists():
            return pd.DataFrame(columns=SUMMARY_COLUMNS)
        df = pd.read_csv(RESULTS_FILE, header=None, names=SUMMARY_COLUMNS)
    else:
        session = get_session()
        rows = session.execute("SELECT * FROM sales_summary")
        df = pd.DataFrame(list(rows))
        if df.empty:
            return pd.DataFrame(columns=SUMMARY_COLUMNS)
        df = df[SUMMARY_COLUMNS]
    for c in ("transactions", "quantity", "revenue"):
        df[c] = pd.to_numeric(df[c]).astype("int64")
    return df


def insert_transaction(row: dict):
    """Write one new sale into BOTH Cassandra sales tables."""
    import datetime as dt
    global _insert_stmts
    session = get_session()
    if _insert_stmts is None:             # prepare the INSERTs once, reuse them
        cols = ", ".join(TXN_COLUMNS)
        marks = ", ".join(["?"] * len(TXN_COLUMNS))
        _insert_stmts = (
            session.prepare(f"INSERT INTO transactions ({cols}) VALUES ({marks})"),
            session.prepare(f"INSERT INTO sales_by_branch ({cols}) VALUES ({marks})"))
    values = [row[c] for c in TXN_COLUMNS]
    values[1] = dt.date.fromisoformat(row["txn_date"])
    for c in ("quantity", "unit_price", "total_amount"):
        values[TXN_COLUMNS.index(c)] = int(row[c])
    for stmt in _insert_stmts:
        session.execute(stmt, values)


def source_description(source: str = None) -> str:
    source = (source or SOURCE).lower()
    if source == "files":
        return "Local files (data/*.csv and results/sales_summary.csv)"
    return f"Cassandra {CASSANDRA_HOST}:{CASSANDRA_PORT}, keyspace '{KEYSPACE}'"
