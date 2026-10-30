#!/usr/bin/env python3
"""
generate_report.py - turn the stored sales data into a management report.

  python3 dashboard/generate_report.py                 # reads Cassandra
  RETAIL_SOURCE=files python3 dashboard/generate_report.py   # reads local files

Creates (in reports/):
  retail_report_<YYYYMMDD_HHMM>.html   - open in any browser, print to PDF if needed
  csv/branch_summary.csv, csv/category_summary.csv, csv/top_products.csv, csv/daily_sales.csv
"""
import base64
import datetime as dt
import html
import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                     # draw charts without a screen
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analytics as A                     # noqa: E402
import data_access as D                   # noqa: E402

BLUE, BLUE_DARK = "#2a78d6", "#1c5aa6"
PAY_COLORS = {"Cash": "#2a78d6", "Debit Card": "#eb6834",
              "Credit Card": "#1baf7a", "Mobile Wallet": "#eda100"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
})


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _millions(x, _pos=None):
    return f"{x / 1e6:.1f}M" if x >= 1e6 else f"{x / 1e3:.0f}k"


def chart_bar(df, label_col, title):
    d = df.sort_values("revenue")
    fig, ax = plt.subplots(figsize=(7, 0.42 * len(d) + 0.9))
    bars = ax.barh(d[label_col], d["revenue"], color=BLUE, height=0.62)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_millions))
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Revenue (LKR)")
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold")
    for b, v in zip(bars, d["revenue"]):
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f"  {v:,.0f}",
                va="center", fontsize=8.5, color=MUTED)
    ax.set_xlim(0, d["revenue"].max() * 1.22)
    ax.tick_params(axis="y", length=0)
    return _png(fig)


def chart_daily(daily):
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(daily["txn_date"], daily["revenue"], color="#9cc0ea", linewidth=1.2,
            label="Daily revenue")
    ax.plot(daily["txn_date"], daily["revenue_7day_avg"], color=BLUE_DARK, linewidth=2.2,
            label="7-day average")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_millions))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_ylabel("Revenue (LKR)")
    ax.set_title("Daily sales trend", loc="left", color=INK, fontsize=12, fontweight="bold")
    ax.legend(frameon=False, loc="upper left")
    fig.autofmt_xdate()
    return _png(fig)


def chart_payments(pay):
    d = pay.sort_values("transactions", ascending=False)
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    colors = [PAY_COLORS.get(p, "#999999") for p in d["payment_method"]]
    ax.pie(d["transactions"], colors=colors, startangle=90, counterclock=False,
           wedgeprops={"width": 0.38, "edgecolor": "white", "linewidth": 2})
    ax.legend([f"{p}  {n / d['transactions'].sum():.0%}"
               for p, n in zip(d["payment_method"], d["transactions"])],
              loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    ax.set_title("Payment methods (share of sales)", loc="left", color=INK,
                 fontsize=12, fontweight="bold")
    return _png(fig)


def _table(df, cols, money=("revenue",)):
    head = "".join(f"<th>{html.escape(h)}</th>" for h in cols.values())
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if c in money:
                cells.append(f"<td class='num'>{v:,.0f}</td>")
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                cells.append(f"<td class='num'>{v:,.0f}</td>")
            else:
                cells.append(f"<td>{html.escape(str(v))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def build_report_html(sales, summary, source_text):
    k = A.kpis(sales)
    br, cat = A.by_branch(sales), A.by_category(sales)
    pay, daily, top = A.by_payment(sales), A.daily_sales(sales), A.top_products(sales, 10)
    rec = A.reconcile(sales, summary)
    first, last = sales["txn_date"].min(), sales["txn_date"].max()
    br = br.assign(share=(br["revenue"] / br["revenue"].sum() * 100).round(1),
                   avg_sale=(br["revenue"] / br["transactions"]).round(0))
    cat = cat.assign(share=(cat["revenue"] / cat["revenue"].sum() * 100).round(1),
                     avg_sale=(cat["revenue"] / cat["transactions"]).round(0))
    days = sales.groupby("branch")["txn_date"].nunique()
    br["per_day"] = (br["revenue"] / br["branch"].map(days)).round(0)

    insights = "".join(f"<li>{html.escape(t)}</li>" for t in A.insights(sales))
    if rec["unprocessed_transactions"] == 0 and rec["unprocessed_revenue"] != 0:
        batch_note = (f"The number of sales matches, but revenue differs by LKR "
                      f"{rec['unprocessed_revenue']:+,} because a record was changed after the "
                      "last MapReduce run.")
    elif rec["unprocessed_transactions"] == 0:
        batch_note = ("The batch view (MapReduce results stored in Cassandra) matches the live "
                      "data exactly: every sale has been processed.")
    else:
        batch_note = (f"{rec['unprocessed_transactions']:,} sales "
                      f"(LKR {rec['unprocessed_revenue']:,}) arrived after the last MapReduce run. "
                      "They are included in this report, but the batch view will only show them "
                      "after the next batch run.")

    tiles = [("Total revenue", f"LKR {k['revenue']:,}"),
             ("Transactions", f"{k['transactions']:,}"),
             ("Products sold", f"{k['products_sold']:,}"),
             ("Best branch", f"{k['best_branch']}"),
             ("Best category", f"{k['best_category']}")]
    tiles_html = "".join(f"<div class='tile'><div class='lbl'>{l}</div>"
                         f"<div class='val'>{html.escape(v)}</div></div>" for l, v in tiles)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lanka Fresh Retail - Sales Report</title>
<style>
 :root {{ --ink:#0b0b0b; --muted:#52514e; --line:#e4e3df; --blue:#2a78d6; --bg:#ffffff; --soft:#f5f6f8; }}
 body {{ font-family: "Segoe UI", Arial, sans-serif; color:var(--ink); background:var(--bg);
        max-width:980px; margin:0 auto; padding:28px 20px 60px; line-height:1.45; }}
 header {{ border-bottom:3px solid var(--blue); padding-bottom:12px; margin-bottom:22px; }}
 h1 {{ margin:0; font-size:26px; }} h2 {{ font-size:18px; margin:34px 0 10px; }}
 .meta {{ color:var(--muted); font-size:13px; margin-top:6px; }}
 .tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }}
 .tile {{ background:var(--soft); border-radius:10px; padding:12px 14px; }}
 .lbl {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
 .val {{ font-size:20px; font-weight:700; margin-top:4px; }}
 table {{ border-collapse:collapse; width:100%; font-size:13px; margin:8px 0 4px; }}
 th, td {{ padding:6px 8px; border-bottom:1px solid var(--line); text-align:left; }}
 th {{ color:var(--muted); font-weight:600; font-size:12px; }}
 td.num {{ text-align:right; font-variant-numeric: tabular-nums; }}
 img {{ max-width:100%; width:760px; height:auto; display:block; margin:6px 0; }}
 .two img {{ width:100%; }}
 .two {{ display:grid; grid-template-columns: 1fr 1fr; gap:18px; align-items:start; }}
 @media (max-width:760px) {{ .two {{ grid-template-columns:1fr; }} }}
 .insights li {{ margin:6px 0; }}
 .note {{ background:#eef4fc; border-left:4px solid var(--blue); padding:10px 14px; border-radius:6px; font-size:14px; }}
 footer {{ margin-top:40px; color:var(--muted); font-size:12px; border-top:1px solid var(--line); padding-top:10px; }}
</style></head><body>
<header>
 <h1>Lanka Fresh Retail &mdash; Sales Performance Report</h1>
 <div class="meta">Period: {first:%d %b %Y} &ndash; {last:%d %b %Y} &nbsp;|&nbsp;
 Generated: {dt.datetime.now():%d %b %Y %H:%M} &nbsp;|&nbsp; Data source: {html.escape(source_text)}</div>
</header>

<section class="tiles">{tiles_html}</section>

<h2>Key insights</h2>
<ul class="insights">{insights}</ul>

<h2>1. Branch performance</h2>
<img alt="Revenue by branch" src="data:image/png;base64,{chart_bar(br, 'branch', 'Revenue by branch')}">
{_table(br, {'branch': 'Branch', 'transactions': 'Transactions', 'quantity': 'Items sold',
             'revenue': 'Revenue (LKR)', 'share': 'Share %', 'per_day': 'Revenue per trading day',
             'avg_sale': 'Avg sale (LKR)'}, money=('revenue', 'per_day', 'avg_sale'))}

<h2>2. Product category performance</h2>
<img alt="Revenue by category" src="data:image/png;base64,{chart_bar(cat, 'category', 'Revenue by product category')}">
{_table(cat, {'category': 'Category', 'transactions': 'Transactions', 'quantity': 'Items sold',
              'revenue': 'Revenue (LKR)', 'share': 'Share %', 'avg_sale': 'Avg sale (LKR)'},
        money=('revenue', 'avg_sale'))}

<h2>3. Sales trend</h2>
<img alt="Daily sales trend" src="data:image/png;base64,{chart_daily(daily)}">

<h2>4. Top 10 products and payment methods</h2>
<div class="two">
 <div>{_table(top.reset_index().rename(columns={'index': 'rank'}),
              {'rank': '#', 'product_name': 'Product', 'category': 'Category',
               'quantity': 'Units', 'revenue': 'Revenue (LKR)'})}</div>
 <div><img alt="Payment methods" src="data:image/png;base64,{chart_payments(pay)}"></div>
</div>

<h2>5. How these numbers were produced</h2>
<p class="note">Sales CSV &rarr; stored in <b>HDFS</b> &rarr; summarised by the <b>MapReduce</b> job
<code>SalesSummary</code> (batch view) &rarr; batch view and raw sales stored in <b>Cassandra</b>
&rarr; this report and the dashboard read from Cassandra.<br><br>
<b>Batch layer check:</b> live data has {rec['live_transactions']:,} sales (LKR {rec['live_revenue']:,});
the last MapReduce run processed {rec['batch_transactions']:,} sales (LKR {rec['batch_revenue']:,}).
{html.escape(batch_note)}</p>

<footer>CMM705 Big Data Programming &ndash; Weeks 1&ndash;5 integrated practical. Lanka Fresh Retail is a
fictional company and all data is synthetic.</footer>
</body></html>"""


def export_csvs(sales, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    A.by_branch(sales).to_csv(out_dir / "branch_summary.csv", index=False)
    A.by_category(sales).to_csv(out_dir / "category_summary.csv", index=False)
    A.top_products(sales, 10).to_csv(out_dir / "top_products.csv", index_label="rank")
    A.daily_sales(sales).to_csv(out_dir / "daily_sales.csv", index=False)


def main():
    sales = D.load_transactions()
    summary = D.load_summary()
    if sales.empty:
        sys.exit("No sales found - did you load the data into Cassandra (Part D)?")
    reports = D.PROJECT_DIR / "reports"
    reports.mkdir(exist_ok=True)
    path = reports / f"retail_report_{dt.datetime.now():%Y%m%d_%H%M}.html"
    path.write_text(build_report_html(sales, summary, D.source_description()), encoding="utf-8")
    export_csvs(sales, reports / "csv")
    print(f"Report written to {path}")
    print(f"CSV exports written to {reports / 'csv'}")


if __name__ == "__main__":
    main()
