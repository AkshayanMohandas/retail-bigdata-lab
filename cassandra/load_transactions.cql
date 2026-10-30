-- Load the raw sales CSV into BOTH sales tables
-- Run:  docker exec -it cassandra cqlsh -f /opt/retail/cassandra/load_transactions.cql
USE retail_analytics;

COPY transactions (transaction_id, txn_date, txn_time, branch, product_id, product_name,
                   category, quantity, unit_price, total_amount, customer_id, payment_method)
FROM '/opt/retail/data/sales_transactions.csv' WITH HEADER = TRUE;

COPY sales_by_branch (transaction_id, txn_date, txn_time, branch, product_id, product_name,
                      category, quantity, unit_price, total_amount, customer_id, payment_method)
FROM '/opt/retail/data/sales_transactions.csv' WITH HEADER = TRUE;
