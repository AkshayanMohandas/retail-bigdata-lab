package org.iit.retail;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.Reducer;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.util.GenericOptionsParser;

import java.io.IOException;

/**
 * SalesSummary - one MapReduce job that summarises retail sales by
 * branch, category, product, date and payment method in a single pass.
 *
 * Input  (CSV, one sale per line):
 *   transaction_id,txn_date,txn_time,branch,product_id,product_name,category,
 *   quantity,unit_price,total_amount,customer_id,payment_method
 *
 * Output (CSV, one line per dimension/item):
 *   dimension,item,transactions,quantity,revenue
 *   e.g.  branch,Colombo,937,1747,1224510
 *
 * Run:  yarn jar retail-analytics-1.0.jar org.iit.retail.SalesSummary <in> <out>
 */
public class SalesSummary {

    /**
     * MAPPER: called once for every line of the CSV.
     * For each sale it emits FIVE key/value pairs - one per dimension:
     *   key   = "branch,Colombo"      value = "1,2,3300"
     *   key   = "category,Groceries"  value = "1,2,3300"   ... and so on.
     * The value is "count,quantity,amount" for this single sale (count = 1).
     */
    public static class SalesMapper extends Mapper<Object, Text, Text, Text> {

        private final Text outKey = new Text();
        private final Text outValue = new Text();

        @Override
        public void map(Object key, Text value, Context context)
                throws IOException, InterruptedException {

            String line = value.toString().trim();

            // Skip empty lines and the CSV header line
            if (line.isEmpty() || line.startsWith("transaction_id")) {
                return;
            }

            String[] f = line.split(",");
            if (f.length != 12) {                 // bad / incomplete record
                context.getCounter("DataQuality", "MalformedRecords").increment(1);
                return;
            }

            String date     = f[1];
            String branch   = f[3];
            String product  = f[5];
            String category = f[6];
            String payment  = f[11];
            long quantity;
            long amount;
            try {
                quantity = Long.parseLong(f[7]);
                amount   = Long.parseLong(f[9]);
            } catch (NumberFormatException e) {
                context.getCounter("DataQuality", "BadNumbers").increment(1);
                return;
            }

            context.getCounter("DataQuality", "ValidRecords").increment(1);

            outValue.set("1," + quantity + "," + amount);

            outKey.set("branch," + branch);
            context.write(outKey, outValue);

            outKey.set("category," + category);
            context.write(outKey, outValue);

            outKey.set("product," + product);
            context.write(outKey, outValue);

            outKey.set("date," + date);
            context.write(outKey, outValue);

            outKey.set("payment," + payment);
            context.write(outKey, outValue);
        }
    }

    /** Adds up a list of "count,quantity,amount" strings. */
    static long[] addUp(Iterable<Text> values) {
        long count = 0, quantity = 0, amount = 0;
        for (Text v : values) {
            String[] p = v.toString().split(",");
            count    += Long.parseLong(p[0]);
            quantity += Long.parseLong(p[1]);
            amount   += Long.parseLong(p[2]);
        }
        return new long[]{count, quantity, amount};
    }

    /**
     * REDUCER: receives ONE key with ALL its values, e.g.
     *   "branch,Colombo" -> ["1,2,3300", "1,1,650", "35,61,48210", ...]
     * and writes the totals "transactions,quantity,revenue".
     *
     * The same class is also used as the COMBINER (a mini reducer that runs on
     * the map side to cut network traffic). That is safe because
     *   (1) adding numbers gives the same answer in any order/grouping, and
     *   (2) the output format "count,quantity,amount" is the same as the input.
     */
    public static class SalesReducer extends Reducer<Text, Text, Text, Text> {
        private final Text outValue = new Text();

        @Override
        public void reduce(Text key, Iterable<Text> values, Context context)
                throws IOException, InterruptedException {
            long[] t = addUp(values);
            outValue.set(t[0] + "," + t[1] + "," + t[2]);
            context.write(key, outValue);
        }
    }

    public static void main(String[] args) throws Exception {
        Configuration conf = new Configuration();
        // Write "key,value" instead of the default "key<TAB>value" so the output is a CSV
        conf.set("mapreduce.output.textoutputformat.separator", ",");

        String[] otherArgs = new GenericOptionsParser(conf, args).getRemainingArgs();
        if (otherArgs.length != 2) {
            System.err.println("Usage: SalesSummary <input path> <output path>");
            System.exit(2);
        }

        Job job = Job.getInstance(conf, "retail sales summary");
        job.setJarByClass(SalesSummary.class);
        job.setMapperClass(SalesMapper.class);
        job.setCombinerClass(SalesReducer.class);
        job.setReducerClass(SalesReducer.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);
        FileInputFormat.addInputPath(job, new Path(otherArgs[0]));
        FileOutputFormat.setOutputPath(job, new Path(otherArgs[1]));
        System.exit(job.waitForCompletion(true) ? 0 : 1);
    }
}
