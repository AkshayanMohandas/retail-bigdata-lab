#!/usr/bin/env bash
# refresh_batch_view.sh - re-run the whole BATCH layer in one go (used in Part F and the challenge)
#   1. copy every CSV in data/ into HDFS  (/user/retail/input)
#   2. delete the old MapReduce output and run the SalesSummary job again
#   3. copy the result out of HDFS        (results/sales_summary.csv)
#   4. reload the Cassandra table sales_summary
# Run from the project folder:   bash scripts/refresh_batch_view.sh
set -euo pipefail

JAR=/opt/retail/mapreduce/target/retail-analytics-1.0.jar
IN=/user/retail/input
OUT=/user/retail/output/sales_summary

echo "== 1. Uploading data/*.csv to HDFS $IN"
docker exec namenode bash -c "hdfs dfs -mkdir -p $IN && hdfs dfs -put -f /opt/retail/data/*.csv $IN/ && hdfs dfs -ls $IN"

echo "== 2. Running MapReduce (SalesSummary)"
docker exec namenode bash -c "hdfs dfs -rm -r -f $OUT && yarn jar $JAR org.iit.retail.SalesSummary $IN $OUT"

echo "== 3. Copying the result out of HDFS"
docker exec namenode bash -c "hdfs dfs -cat $OUT/part-r-* > /opt/retail/results/sales_summary.csv && wc -l /opt/retail/results/sales_summary.csv"

echo "== 4. Reloading Cassandra table sales_summary"
docker exec cassandra cqlsh -f /opt/retail/cassandra/load_summary.cql

echo "Batch view refreshed. Look at the 'Batch view' tab in the dashboard."
