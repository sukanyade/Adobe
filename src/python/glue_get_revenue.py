import boto3
import json
import os
import uuid
from datetime import datetime

# import loguru

# from sonoma.config import CONFIG as SONOMA_CONFIG
# import toolbucket
import time

# log = loguru.logger

try:
    from pyspark.sql import functions as pyspark_sql_funcs
    from pyspark.sql.types import IntegerType

except ImportError:
    print("failed to import pyspark")

spark.conf.set("spark.sql.crossJoin.enabled", "true")


class Help:
    """
    Class to mimic ToolBucket functionality and reduce manual changes in the code
    """
    s3_client = boto3.client("s3")
    s3_resource = boto3.resource("s3")

    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    spark.conf.set("hive.exec.dynamic.partition.mode", "nonstrict")
    spark_session = spark

    def s3_construct_uri(self, bucket=None, prefix=None):
        return f"s3://{bucket}/{prefix}"

    def info(self, msg=None):
        print(msg)

    def exception(self, msg=None):
        print(msg)

    def debug(self, msg=None):
        print(msg)


log = Help()


class DataProcessingJob(Help):
    """
    This class contains methods to support data pre-processing
    """

    aws_manager = Help()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init(self):
        pass

    def commit(self):
        pass

    resolved_options = {
        "source_bucket_name": "cxdl4-sbx-curated-us-west-2",
        "key": "/test_suk/data.tsv",
        "target_bucket_name": "cxdl4-sbx-curated-us-west-2",
        "target_folder": "output_data"
    }

    def get_file_from_path(self, source_bucket_name: str = None, key: str = None):
        """
        Parse source file to get the necessary details
        :param manifest_bucket: source bucket where input file is available
        :param manifest_key: key where output file is stored
        """
        # Reading input data and dropping the fields not required
        try:
            data = spark.read.option("header", "true") \
                .option("sep", "\t") \
                .csv(f"""s3://{source_bucket_name}{key}""") \
                .drop("hit_time_gmt", "date_time", "user_agent", "event_list", "geo_city", "geo_region", "geo_country") \
                .cache()
            # If the input data frame has data:
            if data.count() > 1:
                return data
            else:
                log.exception("Input folder has no data.")
        except Exception as e:
            log.exception("Unable to read data from input S3 file.")
            raise e

    def transform_content(self, source_df=None):
        """
        transform content
            :param source_df: original data
            :param target_path: target path to save data to
        """
        try:
            # Get the Search engine name from the referrer link
            df_search = source_df.withColumn('Page_Url', pyspark_sql_funcs.split(source_df['page_url'], '/').getItem(2)) \
                .withColumn('Search Engine Domain', pyspark_sql_funcs.split(source_df['referrer'], '/').getItem(2))

            # For the records which hit the search engine, Page URL is not same as Referrer URL
            # search keywords are prefixed by p= or q=
            # Tracking the IP for Searches to find out the source of search request
            df_search = df_search.filter(df_search.Page_Url != df_search['Search Engine Domain']) \
                .select("ip", "Search Engine Domain", "referrer") \
                .withColumn("q_Keyword", pyspark_sql_funcs.split(df_search['referrer'], "q=").getItem(1)) \
                .withColumn("p_Keyword", pyspark_sql_funcs.split(df_search['referrer'], "p=").getItem(1))

            df_search = df_search.withColumn("q_Keyword",
                                             pyspark_sql_funcs.split(df_search['q_Keyword'], "&").getItem(0)) \
                .withColumn("p_Keyword", pyspark_sql_funcs.split(df_search['p_Keyword'], "&").getItem(0)) \
                .withColumn('Search Keyword', pyspark_sql_funcs.coalesce(pyspark_sql_funcs.col("q_Keyword"),
                                                                         pyspark_sql_funcs.col("p_Keyword"))) \
                .drop("p_Keyword", "referrer", "q_Keyword")

            # Get list of products from the Product_list.
            # The product list contains list of products seperated by comma and list of attributes seperated by ":"
            df_products = source_df \
                .filter(source_df.pagename == "Order Complete") \
                .withColumn('Products', pyspark_sql_funcs.split(source_df['product_list'], ',')) \
                .withColumn("Product_list", pyspark_sql_funcs.explode('Products')) \
                .drop('Products')

            df_revenue = df_products.withColumn('Revenue',
                                                pyspark_sql_funcs.split(df_products['product_list'], ';').getItem(3)) \
                .withColumn('Product', pyspark_sql_funcs.split(df_products['product_list'], ';').getItem(1)) \
                .na.drop(subset=["Revenue"])

            df_revenue = df_revenue \
                .withColumn("Revenue", df_revenue.Revenue.cast(IntegerType())) \
                .filter(df_revenue.Revenue > 0).select("Revenue", "ip", "Product").distinct()
            df_revenue_product = df_revenue.join(df_search, df_revenue.ip == df_search.ip, 'inner')

            df_revenue_product = df_revenue_product.filter(
                pyspark_sql_funcs.lower(pyspark_sql_funcs.col("Product")).contains(
                    pyspark_sql_funcs.lower(pyspark_sql_funcs.col('Search Keyword')))) \
                .drop("Product", "ip") \
                .withColumn("Search Keyword", pyspark_sql_funcs.lower(pyspark_sql_funcs.col("Search Keyword"))) \
                .withColumn("Revenue", df_revenue_product.Revenue.cast(IntegerType()))

            df_revenue_product = df_revenue_product \
                .groupby("Search Engine Domain", "Search Keyword") \
                .agg(pyspark_sql_funcs.sum('Revenue').alias('Revenue')) \
                .orderBy(pyspark_sql_funcs.desc("Revenue"))
            return df_revenue_product
        except Exception as e:
            log.exception("Unable to calculate revenue.")
            raise e

    def save_output_data(self, revenue_data: None,
                         output_bucket_name: None,
                         target_path: None):
        """
        save_output_data
        :param revenue_data: Renevue data frame
        :param target_path: target path to save data to
        """
        datetime.today().strftime('%Y-%m-%d')
        filename = datetime.today().strftime('%Y-%m-%d') + "_SearchKeywordPerformance.tab"
        filename = f"""{target_path}/{filename}"""
        print("key:", f"""{filename}""")
        # revenue_data.coalesce(1).write.mode("overwrite").option("header" , "true").format("csv").save(filename)
        self.aws_manager.s3_client.put_object(Body=str(revenue_data), Bucket=output_bucket_name, Key=f"""{filename}""")


def run():
    """
    Main driver method
    """

    job = DataProcessingJob()

    try:
        job.init()
        source_bucket_name = job.resolved_options["source_bucket_name"]
        source_key = job.resolved_options["key"]
        target_bucket_name = job.resolved_options["target_bucket_name"]
        target_prefix = job.resolved_options["target_folder"]

        data = job.get_file_from_path(source_bucket_name
                                      , source_key)

        revenue = job.transform_content(source_df=data)

        if revenue.count() > 0:
            job.save_output_data(revenue_data=revenue
                                 , output_bucket_name=target_bucket_name
                                 , target_path=f"""{target_prefix}""")
        else:
            log.exception("Revenue information not found for any of the search engines")
        job.commit()
    except Exception as e:
        log.exception(e)
        raise e

