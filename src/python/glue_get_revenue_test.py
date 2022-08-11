# -*- coding: utf-8 -*-

"""
glue_get_revenue_test

# Test cases for glue_get_revenue
"""
import json
import logging
import os
import sys

import loguru
import pyspark  # pragma: no cover pylint: disable=W0611
import pytest



@pytest.fixture(name="setup_resources")
def fixture_setup_resources(setup_env_vars):
    """setup resources"""
    raw_bucket_name = "sukde-input-raw-bucket"
    curated_bucket_name = "sukde-output-curated-bucket"
    buckets = ["sukde-input-raw-bucket", "sukde-output-curated-bucket"]
    aws_mgr = src.python.glue_get_revenue.Help()
    try:
        for bucket in buckets:
            aws_mgr.s3_resource.Bucket(bucket).objects.all().delete()
            aws_mgr.s3_client.delete_bucket(Bucket=bucket)

    except aws_mgr.s3_client.exceptions.ClientError as excpt:
        logging.exception(excpt)

    # re-create buckets
    aws_mgr.s3_client.create_bucket(Bucket=raw_bucket_name, CreateBucketConfiguration={"LocationConstraint": aws_mgr.region_name})
    aws_mgr.s3_client.create_bucket(Bucket=curated_bucket_name, CreateBucketConfiguration={"LocationConstraint": aws_mgr.region_name})


    # add test file to source bucket:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    fname = "test_data/data.tsv"
    full_path = f"{dir_path}/{fname}"
    key_feed = "/08-11-2022/data.tsv"
    with open(full_path, mode="rb") as file_handle:
        body_feed = file_handle.read()
        aws_mgr.s3_resource.Object(raw_bucket_name, key_feed).put(Body=body_feed)
    _ = setup_env_vars  # Pylint W0613


class TestGetRevenueMethods:
    """test glue methods"""

    def test_method_run(self, setup_env_vars, setup_resources):
        """test run method"""
        job = src.python.glue_get_revenue
        job.run()

        _ = setup_env_vars  # Pylint W0613
        _ = setup_resources  # Pylint W0613
        _ = self.__ne__(None)  # Pylint R0201

    def test_all_exceptions(self):
        job = src.python.glue_get_revenue.DataProcessingJob()
        #Test Exception scenario for get_file_from_path
        with pytest.raises(Exception) as expt:
            log.exception(expt)
            job.get_file_from_path()

        # Test Exception scenario for get_file_from_path
        with pytest.raises(Exception) as expt:
            log.exception(expt)
            job.save_output_data()

        # Test Exception scenario for transform_content
        with pytest.raises(Exception) as expt:
            log.exception(expt)
            job.transform_content()
