-- Replace the batch view with the latest MapReduce output
-- Run:  docker exec -it cassandra cqlsh -f /opt/retail/cassandra/load_summary.cql
USE retail_analytics;

TRUNCATE sales_summary;

COPY sales_summary (dimension, item, transactions, quantity, revenue)
FROM '/opt/retail/results/sales_summary.csv' WITH HEADER = FALSE;
