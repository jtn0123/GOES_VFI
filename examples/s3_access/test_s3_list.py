#!/usr/bin/env python
"""
Test script for listing objects in the NOAA S3 buckets.

This script uses boto3 to list objects in the NOAA S3 buckets
to help debug the file pattern matching issues.
"""

import asyncio
import logging
import sys
from datetime import datetime

import aioboto3
from botocore import UNSIGNED
from botocore.config import Config

from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.utils import date_utils, log

# Set up logging
logging.basicConfig(
level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
LOGGER = log.get_logger(__name__)


async def list_s3_objects(
bucket: str, prefix: str, limit: int = 10, search_bands: bool = False
):
    """List objects in an S3 bucket with the given prefix.

Args:
     bucket: S3 bucket name
prefix: Prefix to filter objects
limit: Maximum number of objects to return
search_bands: If True, search for all available bands

Returns:
     List of S3 object keys
"""
LOGGER.info(f"Listing objects in s3://{bucket}/{prefix} (limit: {limit})")

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

count = 0
objects = []

# If searching for bands, we'll organize by band
band_counts = {}

async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
     if "Contents" in page:
         pass
     pass
for obj in page["Contents"]:
     key = obj["Key"]
size = obj["Size"]
last_modified = obj["LastModified"]

# If searching for bands, extract band number
if search_bands:
     pass
# Find band number (e.g., M6C13 where 13 is the band)
import re

band_match = re.search(r"M\d + C(\d+)", key)
if band_match:
     pass
band = band_match.group(1)
band_counts[band] = band_counts.get(band, 0) + 1

objects.append(
{"key": key, "size": size, "last_modified": last_modified}
)

count += 1
if count >= limit and not search_bands:
     pass
break

if count >= limit and not search_bands:
     pass
break

# If searching for bands, log band information
if search_bands and band_counts:
     pass
LOGGER.info(f"Found {len(band_counts)} different bands:")
for band, count in sorted(band_counts.items(), key=lambda x: int(x[0])):
     LOGGER.info(f" Band {band}: {count} files")

return objects
except Exception as e:
     pass
LOGGER.error(f"Error listing objects: {e}")
return []


async def main():
    """Main entry point for the script."""
# Get command line arguments
if len(sys.argv) > 1:
     pass
# Use date from command line (format: YYYY - MM - DD)
date_str = sys.argv[1]
try:
     year, month, day = map(int, date_str.split("-"))
test_date = datetime(year, month, day, 12, 0, 0)
except Exception:
     pass
LOGGER.error(f"Invalid date format: {date_str} (use YYYY - MM - DD)")
return
else:
     # Use a recent date
test_date = datetime(2023, 6, 15, 12, 0, 0)

LOGGER.info(f"Testing with date: {test_date.isoformat()}")

# Convert date to DOY format
year = test_date.year
doy = date_utils.date_to_doy(test_date.date())
doy_str = f"{doy:03d}"
hour = test_date.strftime("%H")

LOGGER.info(f"Date components: Year={year}, DOY={doy_str}, Hour={hour}")

# Test with GOES - 16 and GOES - 18
satellites = [
(SatellitePattern.GOES_16, "GOES - 16"),
(SatellitePattern.GOES_18, "GOES - 18"),
]

# Test with RadF, RadC, and RadM product types
product_types = ["RadF", "RadC", "RadM"]

# Search more broadly to see what bands are available
for satellite, sat_name in satellites:
     LOGGER.info(f"\nSearching for available bands in {sat_name}:")

# Get bucket name
bucket = TimeIndex.get_s3_bucket(satellite)

for product_type in product_types:
     LOGGER.info(f"\n Searching bands for {product_type}:")

# Create prefix for listing objects (scan the whole hour)
prefix = f"ABI - L1b-{product_type}/{year}/{doy_str}/{hour}/"

# Set a high limit but use search_bands=True to find all available bands
await list_s3_objects(bucket, prefix, limit=100, search_bands=True)

# Now do the regular object listing
for satellite, sat_name in satellites:
     LOGGER.info(f"\nTesting {sat_name}:")

# Get bucket name
bucket = TimeIndex.get_s3_bucket(satellite)

for product_type in product_types:
     LOGGER.info(f"\n Testing {product_type}:")

# Create prefix for listing objects
prefix = f"ABI - L1b-{product_type}/{year}/{doy_str}/{hour}/"

LOGGER.info(f" Listing objects with prefix: {prefix}")

# List objects
objects = await list_s3_objects(bucket, prefix, limit=5)

if objects:
     pass
LOGGER.info(f" Found {len(objects)} objects:")
for i, obj in enumerate(objects):
     LOGGER.info(
f" {i + 1}. {obj['key']} ({obj['size']} bytes, {obj['last_modified']})"
)
else:
     pass
LOGGER.info(f" No objects found with prefix: {prefix}")


if __name__ == "__main__":
    pass
# Run the async main function
asyncio.run(main())
