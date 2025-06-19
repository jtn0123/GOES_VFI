#!/usr/bin/env python3
"""
List available files and download one.
"""
import os
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure S3 client with anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us - east - 1")

s3 = boto3.client("s3", config=s3_config)

# Create download directory
download_dir = Path(os.path.expanduser("~/Downloads / goes_test"))
download_dir.mkdir(parents=True, exist_ok=True)


def list_and_download():
    bucket = "noaa - goes18"

# Paths to check
paths = [
"ABI - L1b - RadF / 2025 / 128 / 00/", # Full Disk
"ABI - L1b - RadC / 2025 / 128 / 00/", # CONUS
"ABI - L1b - RadM / 2025 / 128 / 00/", # Mesoscale
]

# For each path, list files and download one
for path in paths:
     product_name = path.split("/")[0].split("-")[-1] # Extract RadF, RadC, or RadM
print(f"\nChecking {product_name} files in {path}:")

try:
     # List files
result = s3.list_objects_v2(Bucket=bucket, Prefix=path)

if "Contents" in result:
     pass
# Look for Band 13 (Clean IR) files
band13_files = [
obj["Key"]
for obj in result.get("Contents", [])
if "C13" in obj["Key"] and obj["Key"].endswith(".nc")
]

if band13_files:
     pass
# Take the first Band 13 file
file_key = band13_files[0]
local_filename = f"{product_name}_test_{os.path.basename(file_key)}"
local_path = download_dir / local_filename

# Download
print(f"Downloading: {file_key}")
s3.download_file(bucket, file_key, str(local_path))

# Verify download
file_size = local_path.stat().st_size
print(f"Successfully downloaded to {local_path}")
print(f"File size: {file_size:,} bytes")
else:
     print(f"No Band 13 files found in {path}")
else:
     print(f"No files found in {path}")

except Exception as e:
     pass
print(f"Error processing {path}: {str(e)}")


if __name__ == "__main__":
    pass
print("Starting list and download test...")
list_and_download()
print(f"\nFiles downloaded to: {download_dir}")
print("Test complete.")
