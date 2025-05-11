#!/usr/bin/env python3
"""
List specific paths in NOAA S3 buckets to understand the structure.
"""
import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure S3 client with anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)


# Check specific path
def list_specific_path(bucket, path, max_keys=10):
    print(f"Listing objects in {bucket}/{path} (max: {max_keys}):")

    try:
        result = s3.list_objects_v2(Bucket=bucket, Prefix=path, MaxKeys=max_keys)

        if "Contents" in result and result["Contents"]:
            for i, item in enumerate(result["Contents"]):
                key = item["Key"]
                size = item["Size"]
                print(f"  {i+1}. {key} ({size:,} bytes)")

            print(f"Found {len(result['Contents'])} items.")
        else:
            print("  No objects found.")
    except Exception as e:
        print(f"Error: {str(e)}")


# Main function
def main():
    bucket = "noaa-goes18"

    # Try different path structures
    paths = [
        "ABI-L2-CMIPF/2025/128/",
        "ABI-L2-CMIPF/2025/127/",
        "ABI-L2-CMIPF/2025/128/05",
        # Try L1b paths for comparison
        "ABI-L1b-RadF/2025/128/",
        "ABI-L1b-RadC/2025/128/",
        "ABI-L1b-RadM/2025/128/",
    ]

    for path in paths:
        list_specific_path(bucket, path)
        print()


if __name__ == "__main__":
    main()
