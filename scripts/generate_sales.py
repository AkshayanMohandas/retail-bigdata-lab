#!/usr/bin/env python3
"""
generate_sales.py  -  synthetic sales data for the CMM705 Weeks 1-5 integrated lab.

Lanka Fresh Retail (a fictional supermarket chain) has 8 branches in Sri Lanka.
Every row in the CSV is one sale (one product line) at a till.

Usage (run from the project folder, retail-bigdata-lab/):

  # 1) Create the initial dataset (4,000 sales, 1 Feb 2026 - 30 Apr 2026)
  python3 scripts/generate_sales.py --initial

  # 2) Create a new batch of 30 sales for the next day
  python3 scripts/generate_sales.py --count 30

  # 3) Final challenge: 100 sales for a NEW branch in Kandy
  python3 scripts/generate_sales.py --count 100 --branch Kandy --days 7 --out data/kandy_sales.csv

Only the Python standard library is used, so no installation is needed.
"""
import argparse
import csv
import datetime as dt
import glob
import os
import random

COLUMNS = ["transaction_id", "txn_date", "txn_time", "branch", "product_id",
           "product_name", "category", "quantity", "unit_price", "total_amount",
           "customer_id", "payment_method"]

# ---------------------------------------------------------------- branches
# weight = share of the chain's footfall
BRANCHES = {
    "Colombo":      0.22,
    "Negombo":      0.13,
    "Galle":        0.13,
    "Kurunegala":   0.12,
    "Jaffna":       0.11,
    "Matara":       0.10,
    "Anuradhapura": 0.10,
    "Ratnapura":    0.09,
}

# ---------------------------------------------------------------- products
# (product_id, name, category, unit price in LKR, popularity weight, max qty)
PRODUCTS = [
    ("P001", "Keeri Samba Rice 5kg",          "Groceries",      1650, 9, 3),
    ("P002", "Red Raw Rice 5kg",              "Groceries",      1150, 8, 3),
    ("P003", "Mysore Dhal 1kg",               "Groceries",       390, 9, 4),
    ("P004", "White Sugar 1kg",               "Groceries",       280, 8, 4),
    ("P005", "Wheat Flour 1kg",               "Groceries",       220, 6, 4),
    ("P006", "Coconut Oil 1L",                "Groceries",       780, 7, 3),
    ("P007", "Full Cream Milk Powder 400g",   "Groceries",      1150, 8, 3),
    ("P008", "Ceylon Black Tea 400g",         "Beverages",       950, 8, 3),
    ("P009", "Instant Coffee 100g",           "Beverages",      1250, 4, 2),
    ("P010", "Ginger Beer 1.5L",              "Beverages",       450, 5, 4),
    ("P011", "Mineral Water 1.5L",            "Beverages",       140, 7, 6),
    ("P012", "Orange Juice 1L",               "Beverages",       690, 3, 3),
    ("P013", "Sandwich Bread 450g",           "Dairy & Bakery",  180, 9, 3),
    ("P014", "Fresh Milk 1L",                 "Dairy & Bakery",  520, 6, 3),
    ("P015", "Buffalo Curd 1kg",              "Dairy & Bakery",  650, 5, 2),
    ("P016", "Cheese Slices 200g",            "Dairy & Bakery",  980, 3, 2),
    ("P017", "Butter Cake 500g",              "Dairy & Bakery",  850, 4, 2),
    ("P018", "Big Onions 1kg",                "Fresh Produce",   320, 8, 3),
    ("P019", "Potatoes 1kg",                  "Fresh Produce",   360, 7, 3),
    ("P020", "Carrots 500g",                  "Fresh Produce",   220, 5, 3),
    ("P021", "Ambul Bananas 1kg",             "Fresh Produce",   300, 6, 3),
    ("P022", "Eggs 10 Pack",                  "Fresh Produce",   420, 8, 3),
    ("P023", "Dishwash Liquid 500ml",         "Household",       420, 5, 2),
    ("P024", "Laundry Powder 1kg",            "Household",       690, 5, 2),
    ("P025", "Floor Cleaner 1L",              "Household",       560, 3, 2),
    ("P026", "Toilet Tissue 4 Pack",          "Household",       480, 5, 3),
    ("P027", "Mosquito Coils 10 Pack",        "Household",       260, 4, 3),
    ("P028", "Herbal Soap 100g",              "Personal Care",   160, 7, 5),
    ("P029", "Toothpaste 120g",               "Personal Care",   330, 6, 3),
    ("P030", "Shampoo 180ml",                 "Personal Care",   720, 4, 2),
    ("P031", "Body Lotion 400ml",             "Personal Care",  1350, 2, 2),
    ("P032", "Coconut Hair Oil 200ml",        "Personal Care",   450, 4, 2),
    ("P033", "LED Bulb 9W",                   "Electronics",     650, 3, 4),
    ("P034", "Extension Cord 4 Way",          "Electronics",    3200, 1.2, 1),
    ("P035", "Electric Kettle 1.7L",          "Electronics",    8900, 0.6, 1),
    ("P036", "Rice Cooker 1.8L",              "Electronics",   18500, 0.4, 1),
    ("P037", "Bluetooth Speaker",             "Electronics",   12500, 0.4, 1),
    ("P038", "Phone Charger 20W",             "Electronics",    4200, 1.0, 1),
]

PAYMENTS = ["Cash", "Debit Card", "Credit Card", "Mobile Wallet"]

# Branch personality: city branches use more cards / wallets, others more cash.
PAYMENT_MIX = {
    "Colombo":      [0.25, 0.27, 0.23, 0.25],
    "Negombo":      [0.38, 0.25, 0.17, 0.20],
    "Galle":        [0.38, 0.25, 0.17, 0.20],
    "Kurunegala":   [0.47, 0.23, 0.12, 0.18],
    "Jaffna":       [0.55, 0.20, 0.10, 0.15],
    "Matara":       [0.45, 0.24, 0.13, 0.18],
    "Anuradhapura": [0.55, 0.20, 0.10, 0.15],
    "Ratnapura":    [0.52, 0.21, 0.11, 0.16],
    "Kandy":        [0.35, 0.27, 0.18, 0.20],
}

# Category boosts per branch (realistic local flavour)
CATEGORY_BOOST = {
    "Colombo":      {"Electronics": 2.2, "Beverages": 1.3, "Personal Care": 1.2},
    "Negombo":      {"Beverages": 1.3},
    "Galle":        {"Dairy & Bakery": 1.2},
    "Jaffna":       {"Groceries": 1.35, "Fresh Produce": 1.2},
    "Anuradhapura": {"Groceries": 1.3},
    "Kurunegala":   {"Groceries": 1.15, "Household": 1.1},
    "Kandy":        {"Beverages": 1.3, "Dairy & Bakery": 1.2},
}

START_DATE = dt.date(2026, 2, 1)
END_DATE = dt.date(2026, 4, 30)
AVURUDU = dt.date(2026, 4, 14)       # Sinhala & Tamil New Year
INITIAL_ROWS = 4000
CUSTOMERS = 1500
SEED = 705                           # module code CMM705 - makes the data reproducible


def day_weight(day: dt.date) -> float:
    """How busy a day is (relative). Weekends and the run-up to New Year are busier."""
    w = 1.0
    if day.weekday() >= 5:                       # Saturday / Sunday
        w *= 1.35
    if dt.date(2026, 4, 1) <= day <= dt.date(2026, 4, 13):
        w *= 1.9                                 # Avurudu shopping season
    if dt.date(2026, 4, 14) <= day <= dt.date(2026, 4, 15):
        w *= 0.45                                # holidays - many shops quiet
    if day == dt.date(2026, 2, 4):
        w *= 0.7                                 # Independence Day
    return w


def random_time(rng: random.Random) -> str:
    """Opening hours 08:00-21:59 with lunch-time and evening peaks."""
    hour = rng.choices(range(8, 22),
                       weights=[3, 4, 5, 6, 8, 7, 5, 5, 6, 8, 10, 9, 6, 3])[0]
    return f"{hour:02d}:{rng.randint(0, 59):02d}"


def build_customers(rng: random.Random, branches):
    """Each loyalty customer has a home branch."""
    names = list(branches)
    weights = [BRANCHES.get(b, 0.1) for b in names]
    return {f"C{i:05d}": rng.choices(names, weights=weights)[0]
            for i in range(1, CUSTOMERS + 1)}


def pick_product(rng, branch, day):
    boost = CATEGORY_BOOST.get(branch, {})
    in_season = dt.date(2026, 4, 1) <= day <= dt.date(2026, 4, 13)
    weights = []
    for p in PRODUCTS:
        w = p[4] * boost.get(p[2], 1.0)
        if in_season and p[2] in ("Groceries", "Household", "Electronics"):
            w *= 1.4                             # New Year: rice, oil, new kettles...
        weights.append(w)
    return rng.choices(PRODUCTS, weights=weights)[0]


def pick_payment(rng, branch, day, amount):
    mix = list(PAYMENT_MIX.get(branch, PAYMENT_MIX["Kandy"]))
    # Mobile wallet use grows month by month (Feb -> Apr and beyond)
    months_in = (day.year - 2026) * 12 + day.month - 2
    mix[3] *= 1 + 0.25 * max(months_in, 0)
    if amount >= 5000:                           # big tickets are rarely cash
        mix[0] *= 0.4
        mix[2] *= 2.0
    return rng.choices(PAYMENTS, weights=mix)[0]


def make_rows(rng, n, days, branches, customers, first_id):
    """Create n sales spread over the given days."""
    day_list = rng.choices(days, weights=[day_weight(d) for d in days], k=n)
    branch_names = list(branches)
    branch_w = [branches[b] for b in branch_names]
    by_branch = {}
    for cid, home in customers.items():
        by_branch.setdefault(home, []).append(cid)
    rows = []
    for day in day_list:
        branch = rng.choices(branch_names, weights=branch_w)[0]
        product = pick_product(rng, branch, day)
        pid, name, cat, price, _, max_qty = product
        qty = rng.choices(range(1, max_qty + 1),
                          weights=[max_qty - i + 1 for i in range(max_qty)])[0]
        amount = qty * price
        # 85% of the time a local customer, otherwise a visitor from anywhere
        local = by_branch.get(branch)
        if local and rng.random() < 0.85:
            cust = rng.choice(local)
        else:
            cust = rng.choice(list(customers))
        rows.append({
            "txn_date": day.isoformat(), "txn_time": random_time(rng),
            "branch": branch, "product_id": pid, "product_name": name,
            "category": cat, "quantity": qty, "unit_price": price,
            "total_amount": amount, "customer_id": cust,
            "payment_method": pick_payment(rng, branch, day, amount),
        })
    rows.sort(key=lambda r: (r["txn_date"], r["txn_time"], r["branch"]))
    for i, r in enumerate(rows):
        r["transaction_id"] = f"T{first_id + i:06d}"
    return rows


def existing_state(data_dir):
    """Return (last transaction number, last date) found in data/*.csv."""
    last_id, last_date = 0, END_DATE
    for path in glob.glob(os.path.join(data_dir, "*.csv")):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    last_id = max(last_id, int(r["transaction_id"][1:]))
                    last_date = max(last_date, dt.date.fromisoformat(r["txn_date"]))
                except (KeyError, ValueError):
                    continue
    return last_id, last_date


def write_csv(rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def new_batch(count, data_dir="data", branch=None, days=1, seed=None):
    """Rows for the next day(s) after the latest date already in data/.
    Used by this script and by dashboard/simulate_live_sales.py."""
    last_id, last_date = existing_state(data_dir)
    rng = random.Random(seed)
    day_range = [last_date + dt.timedelta(days=i) for i in range(1, days + 1)]
    customers = build_customers(random.Random(SEED), BRANCHES)
    if branch:
        branches = {branch: 1.0}
        # a new branch attracts new loyalty customers
        start = CUSTOMERS + 1
        customers = dict(customers)
        for i in range(start, start + 300):
            customers[f"C{i:05d}"] = branch
    else:
        branches = BRANCHES
    return make_rows(rng, count, day_range, branches, customers, last_id + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--initial", action="store_true",
                    help="create data/sales_transactions.csv (4,000 rows)")
    ap.add_argument("--count", type=int, default=30, help="rows for a new batch")
    ap.add_argument("--branch", help="put every new row in this branch (e.g. Kandy)")
    ap.add_argument("--days", type=int, default=1, help="spread a new batch over N days")
    ap.add_argument("--out", help="output CSV (default: data/new_sales_<n>.csv)")
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args()

    if args.initial:
        rng = random.Random(SEED)
        days = [START_DATE + dt.timedelta(days=i)
                for i in range((END_DATE - START_DATE).days + 1)]
        customers = build_customers(rng, BRANCHES)
        rows = make_rows(rng, INITIAL_ROWS, days, BRANCHES, customers, 1)
        out = args.out or os.path.join(args.data_dir, "sales_transactions.csv")
    else:
        rows = new_batch(args.count, args.data_dir, args.branch, args.days)
        if args.out:
            out = args.out
        else:
            n = len(glob.glob(os.path.join(args.data_dir, "new_sales_*.csv"))) + 1
            out = os.path.join(args.data_dir, f"new_sales_{n:03d}.csv")
    write_csv(rows, out)
    total = sum(r["total_amount"] for r in rows)
    print(f"Wrote {len(rows):,} rows to {out}")
    print(f"  IDs {rows[0]['transaction_id']} .. {rows[-1]['transaction_id']}, "
          f"dates {rows[0]['txn_date']} .. {rows[-1]['txn_date']}, "
          f"revenue LKR {total:,}")


if __name__ == "__main__":
    main()
