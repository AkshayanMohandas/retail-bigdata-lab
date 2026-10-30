-- Part H: load the new Kandy sales into BOTH raw sales tables (the "live" data)
-- Run:  docker exec -it cassandra cqlsh -f /opt/retail/cassandra/load_kandy.cql
-- (The MapReduce results - the batch view - are reloaded separately with load_summary.cql)
USE retail_analytics;

COPY transactions (transaction_id, txn_date, txn_time, branch, product_id, product_name,
                   category, quantity, unit_price, total_amount, customer_id, payment_method)
FROM '/opt/retail/data/kandy_sales.csv' WITH HEADER = TRUE;

COPY sales_by_branch (transaction_id, txn_date, txn_time, branch, product_id, product_name,
                      category, quantity, unit_price, total_amount, customer_id, payment_method)
FROM '/opt/retail/data/kandy_sales.csv' WITH HEADER = TRUE;
