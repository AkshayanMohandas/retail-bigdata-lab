"""
analytics.py - business metrics used by both the dashboard and the report.
Plain pandas, no storage code, so it is easy to read and test.
"""
import pandas as pd


def filter_sales(df, branches=None, categories=None, start=None, end=None):
    out = df
    if branches:
        out = out[out["branch"].isin(branches)]
    if categories:
        out = out[out["category"].isin(categories)]
    if start is not None:
        out = out[out["txn_date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["txn_date"] <= pd.Timestamp(end)]
    return out


def _group(df, col):
    g = (df.groupby(col)
           .agg(transactions=("transaction_id", "count"),
                quantity=("quantity", "sum"),
                revenue=("total_amount", "sum"))
           .reset_index()
           .sort_values("revenue", ascending=False))
    return g


def kpis(df):
    if df.empty:
        return {"revenue": 0, "transactions": 0, "products_sold": 0,
                "best_branch": "-", "best_branch_revenue": 0,
                "best_category": "-", "best_category_revenue": 0,
                "avg_sale": 0}
    b = _group(df, "branch").iloc[0]
    c = _group(df, "category").iloc[0]
    return {
        "revenue": int(df["total_amount"].sum()),
        "transactions": int(len(df)),
        "products_sold": int(df["quantity"].sum()),
        "best_branch": b["branch"], "best_branch_revenue": int(b["revenue"]),
        "best_category": c["category"], "best_category_revenue": int(c["revenue"]),
        "avg_sale": float(df["total_amount"].mean()),
    }


def by_branch(df):
    return _group(df, "branch")


def by_category(df):
    return _group(df, "category")


def by_payment(df):
    return _group(df, "payment_method")


def daily_sales(df):
    d = (df.groupby("txn_date")
           .agg(revenue=("total_amount", "sum"),
                transactions=("transaction_id", "count"))
           .reset_index())
    # 7-day moving average smooths out weekday/weekend ups and downs
    d["revenue_7day_avg"] = d["revenue"].rolling(7, min_periods=1).mean().round(0)
    return d


def top_products(df, n=10):
    g = (df.groupby(["product_name", "category"])
           .agg(quantity=("quantity", "sum"),
                transactions=("transaction_id", "count"),
                revenue=("total_amount", "sum"))
           .reset_index()
           .sort_values(["quantity", "revenue"], ascending=False)
           .head(n)
           .reset_index(drop=True))
    g.index = g.index + 1
    return g


def summary_view(summary, dimension):
    """One dimension of the MapReduce output, biggest revenue first."""
    s = summary[summary["dimension"] == dimension].copy()
    return s.sort_values("revenue", ascending=False).reset_index(drop=True)


def reconcile(df, summary):
    """Compare live data (all sales) with the batch view (last MapReduce run)."""
    batch = summary_view(summary, "branch")
    batch_txn = int(batch["transactions"].sum()) if not batch.empty else 0
    batch_rev = int(batch["revenue"].sum()) if not batch.empty else 0
    live_txn, live_rev = int(len(df)), int(df["total_amount"].sum())
    return {"live_transactions": live_txn, "live_revenue": live_rev,
            "batch_transactions": batch_txn, "batch_revenue": batch_rev,
            "unprocessed_transactions": live_txn - batch_txn,
            "unprocessed_revenue": live_rev - batch_rev}


def lkr(x):
    return f"LKR {x:,.0f}"


def insights(df):
    """A few plain-English findings calculated from the data."""
    if df.empty:
        return ["No sales in the selected period."]
    out = []
    total = df["total_amount"].sum()
    b = by_branch(df)
    top = b.iloc[0]
    out.append(f"{top['branch']} is the strongest branch with {lkr(top['revenue'])} "
               f"({top['revenue'] / total:.0%} of revenue). "
               f"{b.iloc[-1]['branch']} is the weakest with {lkr(b.iloc[-1]['revenue'])}.")

    c = by_category(df)
    by_txn = c.sort_values("transactions", ascending=False)
    hi = c.assign(avg=c["revenue"] / c["transactions"]).sort_values("avg", ascending=False).iloc[0]
    out.append(f"{c.iloc[0]['category']} earns the most revenue ({lkr(c.iloc[0]['revenue'])}), "
               f"while {hi['category']} has the highest value per sale "
               f"({lkr(hi['revenue'] / hi['transactions'])} on average from only "
               f"{int(hi['transactions'])} sales) - a few big-ticket items matter.")

    d = daily_sales(df)
    if len(d) >= 14:
        peak = d.sort_values("revenue", ascending=False).iloc[0]
        avg = d["revenue"].mean()
        out.append(f"The busiest day was {peak['txn_date']:%A %d %B %Y} with "
                   f"{lkr(peak['revenue'])}, {peak['revenue'] / avg:.1f} times an average day "
                   f"({lkr(avg)}).")
        wk = df.assign(weekend=df["txn_date"].dt.dayofweek >= 5)
        per_day = wk.groupby(["weekend", "txn_date"])["total_amount"].sum().groupby("weekend").mean()
        if True in per_day.index and False in per_day.index:
            out.append(f"An average weekend day brings {lkr(per_day[True])} compared with "
                       f"{lkr(per_day[False])} on a weekday "
                       f"({per_day[True] / per_day[False] - 1:+.0%}).")

    months = df["txn_date"].dt.to_period("M")
    if months.nunique() >= 2:
        share = (df.assign(m=months)
                   .groupby("m")["payment_method"]
                   .apply(lambda s: (s == "Mobile Wallet").mean()))
        out.append(f"Mobile Wallet payments grew from {share.iloc[0]:.0%} of sales in "
                   f"{share.index[0].strftime('%B')} to {share.iloc[-1]:.0%} in "
                   f"{share.index[-1].strftime('%B')}.")
    return out
