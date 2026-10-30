-- ============================================================
-- Retail Analytics lab - Cassandra schema (keyspace + 3 tables)
-- Run:  docker exec -it cassandra cqlsh -f /opt/retail/cassandra/schema.cql
-- ============================================================

-- One copy of the data (we have a single Cassandra node).
-- In Week 4 you used replication_factor 2 on a two-node cluster.
CREATE KEYSPACE IF NOT EXISTS retail_analytics
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE retail_analytics;

-- 1) Every sale, looked up by its ID (the "raw" or "live" data)
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id  text PRIMARY KEY,
    txn_date        date,
    txn_time        text,
    branch          text,
    product_id      text,
    product_name    text,
    category        text,
    quantity        int,
    unit_price      int,
    total_amount    int,
    customer_id     text,
    payment_method  text
);

-- 2) The same sales, organised for the query "show me the sales of ONE branch"
--    partition key = branch, rows inside a partition sorted by date (newest first)
CREATE TABLE IF NOT EXISTS sales_by_branch (
    branch          text,
    txn_date        date,
    transaction_id  text,
    txn_time        text,
    product_id      text,
    product_name    text,
    category        text,
    quantity        int,
    unit_price      int,
    total_amount    int,
    customer_id     text,
    payment_method  text,
    PRIMARY KEY ((branch), txn_date, transaction_id)
) WITH CLUSTERING ORDER BY (txn_date DESC, transaction_id ASC);

-- 3) Results of the MapReduce job (the "batch view")
--    partition key = dimension (branch / category / product / date / payment)
CREATE TABLE IF NOT EXISTS sales_summary (
    dimension     text,
    item          text,
    transactions  int,
    quantity      int,
    revenue       bigint,
    PRIMARY KEY ((dimension), item)
);
