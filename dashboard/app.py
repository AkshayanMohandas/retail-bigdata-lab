"""
app.py - Lanka Fresh Retail sales dashboard (Streamlit + Plotly)

Run from the project folder (retail-bigdata-lab/):
    streamlit run dashboard/app.py
then open http://localhost:8501

Where the numbers come from
  * "Live view"  -> Cassandra table transactions  (changes as soon as a sale is inserted)
  * "Batch view" -> Cassandra table sales_summary (MapReduce output; changes only after
                    the MapReduce job is re-run and its result re-loaded)
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analytics as A            # noqa: E402
import data_access as D          # noqa: E402
from generate_report import build_report_html   # noqa: E402

BLUE = "#2a78d6"
PAY_COLORS = {"Cash": "#2a78d6", "Debit Card": "#eb6834",
              "Credit Card": "#1baf7a", "Mobile Wallet": "#eda100"}

st.set_page_config(page_title="Lanka Fresh Retail Dashboard", page_icon="🛒", layout="wide")


# ------------------------------------------------------------------ data
def get_data():
    try:
        return D.load_transactions(), D.load_summary(), None
    except Exception as e:                       # Cassandra not running, keyspace missing ...
        return pd.DataFrame(columns=D.TXN_COLUMNS), pd.DataFrame(columns=D.SUMMARY_COLUMNS), e


sales, summary, error = get_data()

st.title("🛒 Lanka Fresh Retail — Sales Analytics Dashboard")
st.caption(f"Data source: {D.source_description()}  ·  CMM705 Weeks 1–5 integrated practical "
           "(fictional company, synthetic data)")

if error is not None:
    st.error(f"Could not read the data: {error}")
    st.info("Check that the Cassandra container is running and that Part D (schema + load) "
            "has been completed. To run without Cassandra: `export RETAIL_SOURCE=files`.")
    st.stop()
if sales.empty:
    st.warning("The transactions table is empty. Load the CSV into Cassandra (Part D) first.")
    st.stop()

# ------------------------------------------------------------------ sidebar filters
st.sidebar.header("Filters")
all_branches = sorted(sales["branch"].unique())
all_categories = sorted(sales["category"].unique())
branches = st.sidebar.multiselect("Branch", all_branches, default=all_branches)
categories = st.sidebar.multiselect("Product category", all_categories, default=all_categories)
min_d, max_d = sales["txn_date"].min().date(), sales["txn_date"].max().date()
picked = st.sidebar.date_input("Date range", value=(min_d, max_d),
                               min_value=min_d, max_value=max(max_d, dt.date.today()))
start, end = (picked if isinstance(picked, (list, tuple)) and len(picked) == 2
              else (min_d, max_d))
# Left at the full range? Then do not cut off new sales that arrive with later dates.
if start == min_d:
    start = None
if end == max_d:
    end = None

st.sidebar.header("Live monitoring")
auto = st.sidebar.toggle("Auto-refresh", value=False,
                         help="Re-read Cassandra every few seconds while the simulator runs")
every = st.sidebar.slider("Refresh every (seconds)", 3, 30, 5, disabled=not auto)
if st.sidebar.button("Reset baseline"):
    st.session_state.pop("baseline", None)


@st.cache_data(show_spinner=False)
def report_html(sales_df, summary_df, source_text):
    return build_report_html(sales_df, summary_df, source_text)


st.sidebar.header("Report")
st.sidebar.download_button(
    "⬇️ Download management report (HTML)",
    data=report_html(sales, summary, D.source_description()),
    file_name=f"retail_report_{dt.datetime.now():%Y%m%d_%H%M}.html",
    mime="text/html")


# ------------------------------------------------------------------ charts
def bar_h(df, label, title):
    fig = px.bar(df, x="revenue", y=label, orientation="h", text="revenue",
                 color_discrete_sequence=[BLUE], title=title,
                 hover_data={"transactions": ":,", "quantity": ":,", "revenue": ":,"})
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
    fig.update_layout(yaxis={"categoryorder": "total ascending", "title": None},
                      xaxis_title="Revenue (LKR)", height=360,
                      margin={"l": 10, "r": 40, "t": 50, "b": 10})
    return fig


def live_view(branches, categories, start, end):
    """Everything in this function re-runs on its own when auto-refresh is on."""
    data = D.load_transactions()
    view = A.filter_sales(data, branches, categories, start, end)
    k = A.kpis(view)

    # Baseline = the numbers when you first opened the page (or pressed Reset baseline,
    # or changed a filter). The green arrows under the KPIs show change since then.
    sig = (tuple(branches), tuple(categories), str(start), str(end))
    base = st.session_state.get("baseline")
    if base is None or base["sig"] != sig:
        base = {"sig": sig, "revenue": k["revenue"], "transactions": k["transactions"],
                "products_sold": k["products_sold"]}
        st.session_state["baseline"] = base

    def delta(key, money=False):
        diff = k[key] - base[key]
        if diff == 0:
            return None
        return f"{diff:+,} LKR" if money else f"{diff:+,}"

    c = st.columns(5)
    c[0].metric("Total revenue", f"LKR {k['revenue']:,}", delta("revenue", True))
    c[1].metric("Transactions", f"{k['transactions']:,}", delta("transactions"))
    c[2].metric("Products sold", f"{k['products_sold']:,}", delta("products_sold"))
    c[3].metric("Best branch", k["best_branch"], f"LKR {k['best_branch_revenue']:,}",
                delta_color="off")
    c[4].metric("Best category", k["best_category"], f"LKR {k['best_category_revenue']:,}",
                delta_color="off")
    st.caption(f"Last refreshed {dt.datetime.now():%H:%M:%S} · {len(data):,} sales in the "
               f"transactions table · {len(view):,} match the filters")

    if view.empty:
        st.info("No sales match the filters.")
        return

    left, right = st.columns(2)
    left.plotly_chart(bar_h(A.by_branch(view), "branch", "Revenue by branch"),
                      use_container_width=True)
    right.plotly_chart(bar_h(A.by_category(view), "category", "Sales by product category"),
                       use_container_width=True)

    daily = A.daily_sales(view)
    fig = px.line(daily, x="txn_date", y=["revenue", "revenue_7day_avg"],
                  title="Daily sales trend",
                  color_discrete_map={"revenue": "#9cc0ea", "revenue_7day_avg": "#1c5aa6"})
    fig.for_each_trace(lambda t: t.update(
        name={"revenue": "Daily revenue", "revenue_7day_avg": "7-day average"}[t.name],
        line_width=1.4 if t.name == "revenue" else 2.6))
    fig.update_layout(xaxis_title=None, yaxis_title="Revenue (LKR)", legend_title=None,
                      hovermode="x unified", height=360,
                      margin={"l": 10, "r": 10, "t": 50, "b": 10})
    st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns([1, 1.4])
    pay = A.by_payment(view)
    fig = px.pie(pay, names="payment_method", values="transactions", hole=0.55,
                 color="payment_method", color_discrete_map=PAY_COLORS,
                 title="Payment method distribution")
    fig.update_traces(textinfo="label+percent", marker_line_color="white",
                      marker_line_width=2)
    fig.update_layout(showlegend=False, height=380, margin={"l": 10, "r": 10, "t": 50, "b": 10})
    left.plotly_chart(fig, use_container_width=True)

    right.markdown("**Top 10 best-selling products (by units sold)**")
    right.dataframe(A.top_products(view, 10), use_container_width=True,
                    column_config={
                        "product_name": "Product", "category": "Category",
                        "quantity": st.column_config.NumberColumn("Units", format="%d"),
                        "transactions": st.column_config.NumberColumn("Sales", format="%d"),
                        "revenue": st.column_config.NumberColumn("Revenue (LKR)", format="%d"),
                    })

    with st.expander("Key insights (calculated from the filtered data)"):
        for line in A.insights(view):
            st.markdown(f"- {line}")


def batch_view():
    summ = D.load_summary()
    data = D.load_transactions()
    if summ.empty:
        st.warning("sales_summary is empty - run the MapReduce job and load its output (Part C/D).")
        return
    rec = A.reconcile(data, summ)
    if rec["unprocessed_transactions"] == 0 and rec["unprocessed_revenue"] != 0:
        st.warning(f"Same number of sales, but live revenue differs from the batch view by "
                   f"LKR {rec['unprocessed_revenue']:+,}: a record was changed after the last "
                   f"MapReduce run. Re-run the batch job to bring the views back in line.")
    elif rec["unprocessed_transactions"] == 0:
        st.success(f"Batch view is up to date: MapReduce processed all "
                   f"{rec['batch_transactions']:,} sales (LKR {rec['batch_revenue']:,}).")
    else:
        st.warning(f"{rec['unprocessed_transactions']:,} new sales "
                   f"(LKR {rec['unprocessed_revenue']:,}) are in Cassandra but NOT yet in the "
                   f"batch view. Re-run the MapReduce job and reload sales_summary (Part F).")
    c = st.columns(3)
    c[0].metric("Live sales (transactions table)", f"{rec['live_transactions']:,}")
    c[1].metric("Processed by MapReduce (sales_summary)", f"{rec['batch_transactions']:,}")
    c[2].metric("Waiting for next batch run", f"{rec['unprocessed_transactions']:,}")

    left, right = st.columns(2)
    br = A.summary_view(summ, "branch")
    left.plotly_chart(bar_h(br, "item", "MapReduce: revenue by branch"), use_container_width=True)
    cat = A.summary_view(summ, "category")
    right.plotly_chart(bar_h(cat, "item", "MapReduce: revenue by category"),
                       use_container_width=True)

    dim = st.selectbox("Show raw MapReduce output for dimension",
                       ["branch", "category", "product", "payment", "date"])
    st.dataframe(A.summary_view(summ, dim), use_container_width=True, hide_index=True)


tab_live, tab_batch, tab_about = st.tabs(["📈 Live view", "🗂️ Batch view (MapReduce)",
                                          "🧭 How this works"])

with tab_live:
    # st.fragment re-runs ONLY this part of the page every `every` seconds
    live_fragment = st.fragment(live_view, run_every=every if auto else None)
    live_fragment(branches, categories, start, end)

with tab_batch:
    batch_view()

with tab_about:
    st.markdown("""
**Pipeline:** `generate_sales.py` → CSV → **HDFS** (`/user/retail/input`) → **MapReduce**
(`SalesSummary`) → `results/sales_summary.csv` → **Cassandra** (`sales_summary`) → this dashboard.

Raw sales are also loaded into Cassandra (`transactions`, `sales_by_branch`).
`simulate_live_sales.py` inserts new sales straight into Cassandra, so the **Live view** changes
within seconds, while the **Batch view** only changes after the next MapReduce run.

This is *near-real-time monitoring* built from a database that is re-read every few seconds.
It is **not** stream processing: nothing analyses each event as it arrives. Real stream
processing (e.g. Siddhi) comes later in the module.
""")
