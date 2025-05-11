#!/usr/bin/env python3
"""
Extract pre-processed true color imagery from CMIP files.
CMIP files already contain variable CMI_C01_C02_C03 with pre-processed RGB data.
"""
import os
import re
from pathlib import Path

import boto3
import numpy as np
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config
from PIL import Image

# Configure boto3 for anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)

# Target date and hour
TEST_DATE = "2023/121"
TEST_HOUR = "19"  # 19:00 UTC (noon Pacific)

# Product type to use
PRODUCT_TYPE = "ABI-L2-CMIPF"  # Full Disk for best view

# Download directory
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_cmip_truecolor"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def find_cmip_files(bucket, product, date, hour):
    """Find CMIP files in the hour directory."""
    prefix = f"{product}/{date}/{hour}/"
    print(f"Looking for CMIP files in {bucket}/{prefix}...")

    # List all objects with this prefix
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    # Filter for files containing the true color bands (any band file could work)
    cmip_files = []

    for page in pages:
        if "Contents" not in page:
            continue

        for obj in page["Contents"]:
            key = obj["Key"]
            if key.endswith(".nc"):
                # Look for a pattern like CMIPF-M6C01 or similar
                # We need files with the visible bands (01, 02, 03)
                if "C01" in key:
                    cmip_files.append(key)

    print(f"  Found {len(cmip_files)} potential CMIP files")
    return cmip_files


def extract_timestamp(filename):
    """Extract timestamp from GOES filename."""
    match = re.search(r"s(\d{14})", filename)
    if match:
        return match.group(1)
    return None


def check_true_color_variable(bucket, key):
    """Check if the CMIP file has the CMI_C01_C02_C03 variable."""
    print(f"  Checking if {os.path.basename(key)} has true color variable...")

    try:
        # Create output path for temporary download
        file_name = os.path.basename(key)
        nc_path = DOWNLOAD_DIR / f"temp_{file_name}"

        # Download the file
        s3.download_file(bucket, key, str(nc_path))

        # Open and check for true color variable
        with xr.open_dataset(nc_path) as ds:
            variables = list(ds.variables.keys())
            has_true_color = "CMI_C01_C02_C03" in variables

            if has_true_color:
                print(f"  ✓ Found CMI_C01_C02_C03 variable!")
                print(f"  Shape: {ds['CMI_C01_C02_C03'].shape}")
                return True, nc_path
            else:
                print(f"  ✗ No CMI_C01_C02_C03 variable found. Available variables:")
                print(f"    {', '.join(variables[:10])}...")
                os.remove(nc_path)
                return False, None
    except Exception as e:
        print(f"  Error checking file: {e}")
        return False, None


def extract_true_color_image(nc_path, output_path):
    """Extract true color image from CMIP file."""
    print(f"  Extracting true color image from {os.path.basename(nc_path)}...")

    try:
        with xr.open_dataset(nc_path) as ds:
            # Extract the true color data
            # The CMI_C01_C02_C03 variable should have shape (3, height, width)
            rgb_data = ds["CMI_C01_C02_C03"].values

            # Transpose to get (height, width, 3) for PIL
            if rgb_data.shape[0] == 3:
                rgb_data = np.transpose(rgb_data, (1, 2, 0))

            # Convert to uint8 (should already be 0-255)
            rgb_uint8 = rgb_data.astype(np.uint8)

            # Replace NaN values with black
            rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0).astype(np.uint8)

            # Save as RGB image
            Image.fromarray(rgb_uint8, "RGB").save(output_path)
            print(f"  Saved true color image to {output_path}")

            return True
    except Exception as e:
        print(f"  Error extracting true color image: {e}")
        return False


def main():
    """Main function to extract true color imagery from CMIP files."""
    bucket = "noaa-goes16"

    print(
        f"Checking {bucket} for CMIP files with true color data at {TEST_DATE} {TEST_HOUR}:xx UTC"
    )
    print("-" * 70)

    # Find CMIP files
    cmip_files = find_cmip_files(bucket, PRODUCT_TYPE, TEST_DATE, TEST_HOUR)

    if not cmip_files:
        print("  No CMIP files found")
        return

    # Take a sample of files to check for true color variable
    # (We don't need to check all files, just a few to find one with the variable)
    sample_files = cmip_files[:3]

    for cmip_file in sample_files:
        has_true_color, nc_path = check_true_color_variable(bucket, cmip_file)

        if has_true_color and nc_path:
            # Extract timestamp for filename
            timestamp = extract_timestamp(cmip_file) or "unknown"
            output_path = DOWNLOAD_DIR / f"goes16_cmip_truecolor_{timestamp}.png"

            # Extract and save the true color image
            success = extract_true_color_image(nc_path, output_path)

            if success:
                print(f"\nSuccessfully extracted true color image from CMIP file")
                print(f"Image saved to: {output_path}")

                # Clean up the downloaded NetCDF file
                os.remove(nc_path)
                return
            else:
                print(f"Failed to extract true color image")

    print("\nCould not find a CMIP file with true color data")


if __name__ == "__main__":
    main()
