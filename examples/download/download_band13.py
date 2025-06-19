#!/usr/bin/env python
"""
Test script for downloading Band 13 (Clean IR) GOES files from AWS S3.

This script saves the downloaded files to a fixed directory for inspection.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.utils import date_utils, log

# Set up logging
logging.basicConfig(
level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
LOGGER = log.get_logger(__name__)

# Set the download directory - create if it doesn't exist
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads / goes_downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def list_s3_objects_band13(bucket: str, prefix: str, limit: int = 10):
    """List Band 13 objects in an S3 bucket with the given prefix.

Args:
     bucket: S3 bucket name
prefix: Prefix to filter objects
limit: Maximum number of objects to return

Returns:
     List of S3 object keys for Band 13
"""
LOGGER.info(f"Listing Band 13 objects in s3://{bucket}/{prefix} (limit: {limit})")

import aioboto3
from botocore import UNSIGNED
from botocore.config import Config

# Create a session with unsigned access (no credentials needed)
session = aioboto3.Session()

# Configure for unsigned access to public buckets
config = Config(
signature_version=UNSIGNED,
connect_timeout=30,
read_timeout=30,
retries={"max_attempts": 3},
)

# Create S3 client
async with session.client("s3", config=config) as s3:
     try:
     # Use paginator for listing objects
paginator = s3.get_paginator("list_objects_v2")

all_objects = []

async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
     if "Contents" in page:
         pass
     pass
for obj in page["Contents"]:
     all_objects.append(obj["Key"])

# Filter objects for Band 13 (C13)
import re

band13_pattern = re.compile(r"M6C13")
band13_objects = [key for key in all_objects if band13_pattern.search(key)]

# Sort by timestamp
band13_objects = sorted(band13_objects)

LOGGER.info(
f"Found {len(band13_objects)} Band 13 objects out of {len(all_objects)} total"
)

# Return the first 'limit' Band 13 objects
return band13_objects[:limit]
except Exception as e:
     pass
LOGGER.error(f"Error listing objects: {e}")
return []


async def test_download_band13(timestamp, satellite_pattern, product_type, dest_dir):
    """Test downloading a Band 13 file.

Args:
     timestamp: Datetime object for the image
satellite_pattern: SatellitePattern enum
product_type: Product type ("RadF", "RadC", "RadM")
dest_dir: Directory to save downloaded files

Returns:
     Path to downloaded file if successful, None otherwise
"""
LOGGER.info(
f"Testing download of Band 13 {product_type} for {satellite_pattern.name} at {timestamp.isoformat()}"
)

# Create S3 store
s3_store = S3Store(timeout=60)

try:
     pass
# Get bucket name
bucket = TimeIndex.get_s3_bucket(satellite_pattern)

# Find the nearest valid timestamps for this product
nearest_times = TimeIndex.find_nearest_intervals(timestamp, product_type)
if not nearest_times:
     pass
LOGGER.warning(f"No valid scan times found for {product_type}")
return None

LOGGER.info(
f"Found {len(nearest_times)} nearest scan times: {[t.isoformat() for t in nearest_times]}"
)

# Convert date to DOY format
year = timestamp.year
doy = date_utils.date_to_doy(timestamp.date())
doy_str = f"{doy:03d}"
hour = timestamp.strftime("%H")

# List Band 13 objects for this hour
prefix = f"ABI - L1b-{product_type}/{year}/{doy_str}/{hour}/"
band13_keys = await list_s3_objects_band13(bucket, prefix, limit=5)

if not band13_keys:
     pass
LOGGER.warning(f"No Band 13 files found for s3://{bucket}/{prefix}")
return None

# Try to download a single Band 13 file
test_key = band13_keys[0]
LOGGER.info(f"Testing download of key: s3://{bucket}/{test_key}")

# Generate destination path with product type and satellite in the filename
filename = (
f"{satellite_pattern.name}_{product_type}_Band13_{test_key.split('/')[-1]}"
)
dest_path = dest_dir / filename

# Create a file pattern for list_objects_v2 that uses actual pattern
try:
     # Extract timestamp components from the filename
# Format: OR_ABI - L1b - RadC - M6C13_G16_s20231661201176_e20231661203561_c20231661204041.nc
import re

# Filenames use a format like: s20231661201176 where:
     # - First 4 digits are year (2023)
# - Next 3 digits are DOY (166)
# - Next 2 digits are hour (12)
# - Next 2 digits are minute (01)
# - Next 3 digits are milliseconds or other precision info
pattern = r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{3})_"
match = re.search(pattern, test_key)

if match:
     pass
# Extract components
file_year = int(match.group(1))
file_doy = int(match.group(2))
file_hour = int(match.group(3))
file_minute = int(match.group(4))
# The last 3 digits are not seconds - they're milliseconds or tenths of seconds
# Just use 0 for seconds to avoid the "second must be in 0..59" error

# Convert DOY to date
date_obj = date_utils.doy_to_date(file_year, file_doy)

# Create timestamp for download
file_ts = datetime(
date_obj.year,
date_obj.month,
date_obj.day,
hour=file_hour,
minute=file_minute,
second=0, # Use 0 for seconds to avoid errors
)

LOGGER.info(f"Extracted timestamp: {file_ts.isoformat()}")

# Fix for product type - we need to search in the correct directory
search_product_type = product_type

# Now try to download using the S3Store's band support
result = await s3_store.download(
file_ts,
satellite_pattern,
dest_path,
product_type=search_product_type,
band=13, # Explicitly request Band 13
)

if dest_path.exists():
     pass
file_size = dest_path.stat().st_size
LOGGER.info(
f"✓ Successfully downloaded to {dest_path} ({file_size} bytes)"
)
return dest_path
else:
     LOGGER.error(
f"✗ Download failed: File doesn't exist at {dest_path}"'
)
return None
else:
     LOGGER.error(f"✗ Failed to extract timestamp from filename: {test_key}")
return None
except Exception as e:
     pass
LOGGER.error(f"✗ Error during download: {e}")
return None

except Exception as e:
     pass
LOGGER.error(f"✗ Error: {e}")
return None
finally:
     # Close the S3 store
await s3_store.close()

return None


async def download_fixed_list():
    """Download specific Band 13 files that we know exist."""
# Set of specific files known to be available for Band 13
KNOWN_FILES = [
# GOES - 16 RadC
(
"noaa - goes16",
"ABI - L1b - RadC / 2023 / 166 / 12 / OR_ABI - L1b - RadC - M6C13_G16_s20231661201176_e20231661203561_c20231661204041.nc",
),
# GOES - 18 RadC
(
"noaa - goes18",
"ABI - L1b - RadC / 2023 / 166 / 12 / OR_ABI - L1b - RadC - M6C13_G18_s20231661201181_e20231661203567_c20231661204040.nc",
),
]

downloaded_files = []

for bucket, key in KNOWN_FILES:
     pass
LOGGER.info(f"Downloading known file: s3://{bucket}/{key}")

# Create S3 store
s3_store = S3Store(timeout=60)

try:
     import aioboto3
from botocore import UNSIGNED
from botocore.config import Config

# Create a session with unsigned access (no credentials needed)
session = aioboto3.Session()

# Configure for unsigned access to public buckets
config = Config(
signature_version=UNSIGNED,
connect_timeout=30,
read_timeout=30,
retries={"max_attempts": 3},
)

# Create destination path
filename = key.split("/")[-1]
sat_name = "GOES16" if bucket == "noaa - goes16" else "GOES18"
dest_path = DOWNLOAD_DIR / f"{sat_name}_{filename}"

# Create S3 client and download
async with session.client("s3", config=config) as s3:
     pass
LOGGER.info(f"Downloading to {dest_path}")
await s3.download_file(Bucket=bucket, Key=key, Filename=str(dest_path))

if dest_path.exists():
     pass
file_size = dest_path.stat().st_size
LOGGER.info(
f"✓ Successfully downloaded to {dest_path} ({file_size} bytes)"
)
downloaded_files.append(dest_path)
else:
     LOGGER.error(
f"✗ Download failed: File doesn't exist at {dest_path}"'
)
except Exception as e:
     pass
LOGGER.error(f"✗ Error downloading {key}: {e}")
finally:
     await s3_store.close()

return downloaded_files


async def main():
    """Main entry point for the script."""
LOGGER.info(f"Downloading files to: {DOWNLOAD_DIR}")

# First try the dynamic approach
test_time = datetime(2023, 6, 15, 12, 0, 0)
LOGGER.info(f"Testing with timestamp: {test_time.isoformat()}")

# Test with GOES - 16 and GOES - 18
satellites = [
(SatellitePattern.GOES_16, "GOES - 16"),
(SatellitePattern.GOES_18, "GOES - 18"),
]

# Test with RadF, RadC, and RadM product types
product_types = ["RadF", "RadC", "RadM"]

results = {}
downloaded_files = []

for satellite, sat_name in satellites:
     results[sat_name] = {}

for product_type in product_types:
     downloaded_path = await test_download_band13(
test_time, satellite, product_type, DOWNLOAD_DIR
)
results[sat_name][product_type] = downloaded_path is not None
if downloaded_path:
     pass
downloaded_files.append(downloaded_path)

# If dynamic approach didn't work well, try direct downloads
if not downloaded_files:
     pass
LOGGER.info("Dynamic approach failed, trying direct downloads of known files")
downloaded_files = await download_fixed_list()

# Print final summary
LOGGER.info("\n=== TEST SUMMARY ===")
for satellite, products in results.items():
     successful = [p for p, s in products.items() if s]
failed = [p for p, s in products.items() if not s]

LOGGER.info(f"{satellite}: {len(successful)}/{len(products)} successful")
LOGGER.info(f" Successful: {', '.join(successful) if successful else 'None'}")
LOGGER.info(f" Failed: {', '.join(failed) if failed else 'None'}")

# List all downloaded files
LOGGER.info("\n=== DOWNLOADED FILES ===")
for i, path in enumerate(downloaded_files):
     pass
LOGGER.info(f"{i + 1}. {path} ({path.stat().st_size} bytes)")

LOGGER.info(f"\nDownloaded files are saved in: {DOWNLOAD_DIR}")
LOGGER.info("Please check this directory to view the downloaded files.")


if __name__ == "__main__":
    pass
# Run the async main function
asyncio.run(main())
