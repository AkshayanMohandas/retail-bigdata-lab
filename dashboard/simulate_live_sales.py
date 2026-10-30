#!/usr/bin/env python3
"""
simulate_live_sales.py - pretend the tills are ringing.

Creates new sales (for the day after the latest date already in data/), then:
  1. saves them to data/new_sales_<n>.csv   (so they can go into HDFS for the next batch run)
  2. inserts them one by one into Cassandra (transactions + sales_by_branch)
     with a short pause, so you can watch the dashboard change.

  python3 dashboard/simulate_live_sales.py                  # 30 sales, 1 per second
  python3 dashboard/simulate_live_sales.py --count 50 --interval 0.5
  python3 dashboard/simulate_live_sales.py --count 100 --branch Kandy --days 7 --interval 0

This is SIMULATED near-real-time data. The dashboard re-reads the database every few
seconds; no stream-processing engine is involved.
"""
import argparse
import glob
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROJECT / "scripts"))
import data_access as D                     # noqa: E402
from generate_sales import new_batch, write_csv   # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=30, help="number of new sales (default 30)")
    ap.add_argument("--interval", type=float, default=1.0,
                    help="seconds to wait between inserts (default 1.0)")
    ap.add_argument("--branch", help="put all new sales in this branch, e.g. Kandy")
    ap.add_argument("--days", type=int, default=1, help="spread the sales over N new days")
    ap.add_argument("--out", help="CSV file to write (default data/new_sales_<n>.csv)")
    args = ap.parse_args()

    data_dir = PROJECT / "data"
    rows = new_batch(args.count, str(data_dir), args.branch, args.days)
    if args.out:
        out = Path(args.out)
    else:
        n = len(glob.glob(str(data_dir / "new_sales_*.csv"))) + 1
        out = data_dir / f"new_sales_{n:03d}.csv"
    write_csv(rows, str(out))
    print(f"Saved {len(rows)} new sales to {out.relative_to(PROJECT) if out.is_absolute() else out}")

    if D.SOURCE == "files":
        print("RETAIL_SOURCE=files -> not writing to Cassandra (the dashboard reads data/*.csv).")
        return

    print(f"Inserting into {D.source_description()} ...")
    total = 0
    for i, r in enumerate(rows, 1):
        D.insert_transaction(r)
        total += r["total_amount"]
        print(f"[{i:>3}/{len(rows)}] {r['transaction_id']}  {r['txn_date']} {r['txn_time']}  "
              f"{r['branch']:<12} {r['product_name']:<28} x{r['quantity']}  "
              f"LKR {r['total_amount']:>7,}   (running total LKR {total:,})", flush=True)
        if args.interval > 0:
            time.sleep(args.interval)
    print(f"Done: {len(rows)} sales, LKR {total:,} added to Cassandra.")
    print("Next for the batch view: put the new CSV into HDFS, re-run MapReduce, reload sales_summary.")


if __name__ == "__main__":
    main()
