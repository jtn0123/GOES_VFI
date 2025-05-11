#!/usr/bin/env python3
"""
Verify CMIP file paths with correct wildcards.
This script tests the exact path structure for Level-2 CMIP files.
"""
import os
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure boto3 for anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)

# Create download directory
download_dir = Path(os.path.expanduser("~/Downloads/goes_cmip_test"))
download_dir.mkdir(parents=True, exist_ok=True)


def test_cmip_paths():
    """Test different CMIP path structures to find the correct one."""
    bucket = "noaa-goes18"

    # Test parameters
    year = "2025"
    doy = "128"  # day of year
    hour = "00"
    band = 13

    # Test different product types
    products = [
        "ABI-L2-CMIPF",  # Full Disk
        "ABI-L2-CMIPC",  # CONUS
        "ABI-L2-CMIPM",  # Mesoscale
    ]

    for product in products:
        print(f"\n=== Testing {product} ===")

        # Correct prefix structure
        prefix = f"{product}/{year}/{doy}/{hour}/"
        print(f"Checking prefix: {prefix}")

        # List objects with this prefix
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

        if "Contents" in response:
            # This prefix exists
            print(f"Found {len(response['Contents'])} objects with this prefix")

            # Filter for the specified band - important part is C{band:02d} within the product code
            band_pattern = f"-M6C{band:02d}_"
            band_files = [
                obj["Key"]
                for obj in response["Contents"]
                if band_pattern in obj["Key"] and obj["Key"].endswith(".nc")
            ]

            if band_files:
                print(f"Found {len(band_files)} files for band {band}")

                # Take the first file for a sample
                sample_file = band_files[0]
                print(f"Sample file: {sample_file}")

                # Download this file
                local_name = f"{product}_band{band}_{os.path.basename(sample_file)}"
                local_path = download_dir / local_name

                print(f"Downloading to {local_path}...")
                s3.download_file(bucket, sample_file, str(local_path))
                file_size = local_path.stat().st_size
                print(f"Downloaded {file_size:,} bytes")

                # List the first few files to understand naming pattern
                print("\nSample file names in this directory:")
                for i, obj in enumerate(response["Contents"][:5]):
                    print(f"  {i+1}. {os.path.basename(obj['Key'])}")
            else:
                print(f"No files found for band {band} with pattern '{band_pattern}'")
        else:
            print("No objects found with this prefix")


if __name__ == "__main__":
    print("Testing CMIP file paths...")
    test_cmip_paths()
    print(f"\nFiles downloaded to: {download_dir}")
    print("Test complete.")
