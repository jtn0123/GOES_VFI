#!/usr/bin/env python3
"""
List the contents of a GOES S3 bucket directory to examine its structure.
"""
import argparse
import sys

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure boto3 for anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)


def list_directory(bucket, prefix, max_items=20):
    """List the contents of a directory in the S3 bucket."""
    print(f"Listing contents of s3://{bucket}/{prefix}")
    print("-" * 70)

    try:
        # List objects with the given prefix
        paginator = s3.get_paginator("list_objects_v2")

        item_count = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
            # List common prefixes (like directories)
            if "CommonPrefixes" in page:
                for common_prefix in page["CommonPrefixes"]:
                    print(f"DIR: {common_prefix['Prefix']}")
                    item_count += 1
                    if item_count >= max_items:
                        break

            # List actual objects
            if "Contents" in page:
                for item in page["Contents"]:
                    key = item["Key"]
                    size = item["Size"]
                    modified = item["LastModified"]

                    # Skip if it's just the directory itself
                    if key == prefix:
                        continue

                    print(f"FILE: {key} ({size} bytes, modified {modified})")
                    item_count += 1
                    if item_count >= max_items:
                        break

            if item_count >= max_items:
                print(f"\nShowing {item_count} items. Use --max-items for more.")
                break

    except Exception as e:
        print(f"Error: {e}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description="List contents of a GOES S3 bucket directory"
    )
    parser.add_argument(
        "--bucket", default="noaa-goes16", help="S3 bucket name (default: noaa-goes16)"
    )
    parser.add_argument(
        "--prefix",
        required=True,
        help="Directory prefix to list (e.g., 'ABI-L2-CMIPF/2023/121/19/')",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="Maximum number of items to show (default: 20)",
    )
    args = parser.parse_args()

    list_directory(args.bucket, args.prefix, args.max_items)


if __name__ == "__main__":
    main()
