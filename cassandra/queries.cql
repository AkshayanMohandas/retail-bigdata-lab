-- Handy queries for Part D (type them one at a time inside cqlsh)
USE retail_analytics;

SELECT COUNT(*) FROM transactions;
SELECT * FROM transactions WHERE transaction_id = 'T000004';
SELECT * FROM sales_summary WHERE dimension = 'branch';
SELECT * FROM sales_summary WHERE dimension = 'category';
SELECT branch, txn_date, product_name, total_amount FROM sales_by_branch WHERE branch = 'Jaffna' LIMIT 10;
SELECT * FROM sales_by_branch WHERE branch = 'Galle' AND txn_date = '2026-04-11';
