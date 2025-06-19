#!/usr/bin/env python3
"""
Test script to download GOES satellite imagery files from AWS S3 buckets.
This script attempts to download examples of all product types (RadF, RadC, RadM)
and multiple bands for verification and testing.
"""
import asyncio
import logging
import os
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

logging.basicConfig(
level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_download_all_products")

# Configuration
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads / goes_downloads"))
SATELLITES = ["noaa - goes16", "noaa - goes18"]
PRODUCT_TYPES = ["RadF", "RadC", "RadM"]
# Bands 1 - 6: Visible / Near - IR, 7 - 16: IR
BANDS = list(range(1, 17)) # All bands 1 - 16

# Test date: June 15th, 2023
TEST_DATE = "2023 / 166/" # DOY 166 = June 15, 2023

# Create download directory if it doesn't exist
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Configure boto3 with a lengthy timeout and anonymous access for public NOAA buckets
s3_config = Config(
signature_version=UNSIGNED, # Anonymous access
retries={"max_attempts": 3, "mode": "standard"},
read_timeout=300, # 5 minutes
connect_timeout=30,
)


async def list_available_files(bucket_name, product_type, band, hour="12"):
    """List available files in the S3 bucket for a specific product type and band."""
try:
     pass
# Connect to the S3 bucket with anonymous access
s3 = boto3.client("s3", region_name="us - east - 1", config=s3_config)

# Define the prefix for the specified product type, date and hour
prefix = f"ABI - L1b-{product_type}/{TEST_DATE}{hour}/"

# List objects in the bucket with the given prefix
response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

# Filter for the specified band
band_str = f"C{band:02d}" # Format: C01, C02, etc.
band_files = [
obj["Key"]
for obj in response.get("Contents", [])
if band_str in obj["Key"] and obj["Key"].endswith(".nc")
]

return band_files[:3] # Return up to 3 files for each combination

except Exception as e:
     pass
logger.error(
f"Error listing files for {bucket_name}/{product_type}/Band {band}: {str(e)}"
)
return []


async def download_file(bucket_name, s3_key, local_path):
    """Download a file from S3 to a local path."""
try:
     # Connect to the S3 bucket with anonymous access
s3 = boto3.client("s3", region_name="us - east - 1", config=s3_config)

# Download the file
logger.info(f"Downloading {s3_key} to {local_path}")
s3.download_file(bucket_name, s3_key, str(local_path))

file_size = local_path.stat().st_size
logger.info(f"Downloaded file size: {file_size:,} bytes")
return True

except Exception as e:
     pass
logger.error(f"Error downloading {bucket_name}/{s3_key}: {str(e)}")
return False


async def sample_all_products_and_bands():
    """Sample files from all product types and bands for both satellites."""
results = {}

for satellite in SATELLITES:
     satellite_results = {}

for product_type in PRODUCT_TYPES:
     product_results = {}

for band in BANDS:
     # Only attempt a few bands for each product to avoid excessive downloads
if product_type == "RadM" and band > 8:
     pass
# Skip some bands for RadM to keep test duration reasonable
continue

# List available files for this combination
available_files = await list_available_files(
satellite, product_type, band
)

if available_files:
     pass
# Download the first available file
filename = available_files[0]
satellite_abbr = "G16" if satellite == "noaa - goes16" else "G18"

local_filename = (
f"{satellite_abbr}_{product_type}_Band{band:02d}_"
f"{os.path.basename(filename)}"
)
local_path = DOWNLOAD_DIR / local_filename

success = await download_file(satellite, filename, local_path)
product_results[f"Band{band:02d}"] = {
"file": local_filename if success else None,
"s3_key": filename,
"success": success,
}
else:
     product_results[f"Band{band:02d}"] = {
"file": None,
"s3_key": None,
"success": False,
"reason": "No files found",
}

satellite_results[product_type] = product_results

results[satellite] = satellite_results

return results


async def main():
    """Main function to run the tests."""
logger.info(f"Starting GOES satellite file downloads to {DOWNLOAD_DIR}")

try:
     # Download samples of all product types and bands
results = await sample_all_products_and_bands()

# Print summary
logger.info("\n--- Download Summary ---")

for satellite, satellite_results in results.items():
     satellite_name = "GOES - 16" if satellite == "noaa - goes16" else "GOES - 18"
logger.info(f"\n{satellite_name}:")

for product_type, product_results in satellite_results.items():
     successful = sum(
1
for band_result in product_results.values()
if band_result["success"]
)
total = len(product_results)
logger.info(
f" {product_type}: {successful}/{total} bands downloaded successfully"
)

# List successful downloads
for band_name, band_result in product_results.items():
     if band_result["success"]:
         pass
     pass
logger.info(f" ✓ {band_name}: {band_result['file']}")
else:
     reason = band_result.get("reason", "Download failed")
logger.info(f" ✗ {band_name}: {reason}")

except Exception as e:
     pass
logger.error(f"Error in main: {str(e)}")
raise


if __name__ == "__main__":
    pass
asyncio.run(main())
