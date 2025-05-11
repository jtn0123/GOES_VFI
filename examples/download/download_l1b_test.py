#!/usr/bin/env python3
"""
Direct test to download a specific L1b file.
"""
import os
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure S3 client with anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)

# Create download directory
download_dir = Path(os.path.expanduser("~/Downloads/goes_test"))
download_dir.mkdir(parents=True, exist_ok=True)


# Direct download test
def download_direct_test():
    # Using a specific file path that we know exists
    bucket = "noaa-goes18"
    key_full_disk = "ABI-L1b-RadF/2025/128/00/OR_ABI-L1b-RadF-M6C13_G18_s20251280000206_e20251280009514_c20251280009541.nc"
    key_conus = "ABI-L1b-RadC/2025/128/00/OR_ABI-L1b-RadC-M6C13_G18_s20251280001174_e20251280003547_c20251280003585.nc"
    key_meso1 = "ABI-L1b-RadM/2025/128/00/OR_ABI-L1b-RadM1-M6C13_G18_s20251280000281_e20251280000339_c20251280000379.nc"

    # Download the files
    files_to_download = [
        ("Full Disk", key_full_disk, "full_disk_test.nc"),
        ("CONUS", key_conus, "conus_test.nc"),
        ("Mesoscale-1", key_meso1, "meso1_test.nc"),
    ]

    for label, key, local_name in files_to_download:
        try:
            # Local path
            local_path = download_dir / local_name

            # Download
            print(f"Downloading {label} file: {key}")

            # Create a progress callback
            file_size = s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
            print(f"File size: {file_size:,} bytes")

            s3.download_file(bucket, key, str(local_path))

            # Verify download
            actual_size = local_path.stat().st_size
            print(f"Successfully downloaded to {local_path}")
            print(f"File size on disk: {actual_size:,} bytes\n")

        except Exception as e:
            print(f"Error downloading {label} file: {str(e)}\n")


if __name__ == "__main__":
    print("Starting direct download test...")
    download_direct_test()
    print(f"Files downloaded to: {download_dir}")
    print("Test complete.")
