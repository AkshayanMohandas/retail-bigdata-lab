# Retail Big Data Lab — CMM705 Weeks 1–5 integrated practical

**Lanka Fresh Retail** (fictional) has 8 branches in Sri Lanka. In this lab you build a small
end-to-end analytics pipeline with the tools from Weeks 1–5:

```
generate_sales.py → CSV → HDFS → MapReduce (Java) → Cassandra → Streamlit dashboard → HTML report
                                                       ↑
                         simulate_live_sales.py ───────┘  (simulated near-real-time sales)
```

Follow the **Student Lab Sheet** (step by step) or the **Quick Lab Guide** (commands only).

## Folder layout

| Folder / file | What it is |
|---|---|
| `data/sales_transactions.csv` | 4,000 synthetic sales, 1 Feb – 30 Apr 2026 (regenerate with `python3 scripts/generate_sales.py --initial`) |
| `scripts/generate_sales.py` | creates the dataset and new batches (`--count`, `--branch`, `--days`) |
| `scripts/refresh_batch_view.sh` | re-runs the whole batch layer: CSVs → HDFS → MapReduce → Cassandra |
| `docker/docker-compose-hadoop.yaml` | Hadoop 3.2.1 cluster (1 NameNode, 2 DataNodes, YARN) — same images as the module's `lab1` |
| `docker/docker-compose-cassandra.yaml` | single-node Cassandra 4.0.12 — same image as the module's `lab2` |
| `mapreduce/` | Maven project, `org.iit.retail.SalesSummary` (mapper + combiner + reducer) |
| `cassandra/*.cql` | keyspace/tables, CSV loading (`COPY`), handy queries |
| `dashboard/app.py` | Streamlit + Plotly dashboard (Live view, Batch view) |
| `dashboard/simulate_live_sales.py` | inserts new sales into Cassandra one by one |
| `dashboard/generate_report.py` | management report (HTML) + CSV exports in `reports/` |
| `results/` | MapReduce output copied out of HDFS (`sales_summary.csv`) |
| `docs/expected_output/` | the MapReduce output you should get for the initial dataset |

## Requirements

Ubuntu 22.04 (WSL2) or the module VM, Docker with Compose v2, JDK 8+ and Maven (as in Week 5),
Python 3.10–3.12 (`pip install -r dashboard/requirements.txt` in a virtual environment).
About 5 GB of free RAM for Docker (Hadoop + Cassandra together).

## Ports

9870 NameNode UI · 8088 YARN UI · 9042 Cassandra · 8501 dashboard

## Running without Cassandra

`export RETAIL_SOURCE=files` makes the dashboard, simulator and report read `data/*.csv` and
`results/sales_summary.csv` instead of Cassandra (fallback for troubleshooting only).

## Clean up

```
docker compose -f docker/docker-compose-hadoop.yaml down -v
docker compose -f docker/docker-compose-cassandra.yaml down -v
```
