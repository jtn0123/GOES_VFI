#!/usr/bin/env python3
"""
Scan through multiple hours to find GOES data.
This script checks availability across different hours to find data.
"""
import asyncio
import logging
from datetime import datetime

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("scan_goes_hours")

# Configure S3 client with anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)

# Test date
TEST_DATE = "2025/125"  # May 5, 2025

# Product types to check
PRODUCT_TYPES = [
    "ABI-L2-CMIPF",  # Full Disk
    "ABI-L2-CMIPC",  # CONUS
    "ABI-L2-CMIPM",  # Mesoscale
]


async def check_hour(bucket, product_type, hour, band=13):
    """Check if files exist for a specific hour."""
    # Format hour as 2 digits
    hour_str = f"{hour:02d}"

    # Generate the prefix
    prefix = f"{product_type}/{TEST_DATE}/{hour_str}/"

    # List files
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    if "Contents" in response:
        # Filter for the specified band
        band_str = f"C{band:02d}"
        band_files = [
            obj["Key"]
            for obj in response.get("Contents", [])
            if band_str in obj["Key"] and obj["Key"].endswith(".nc")
        ]

        return len(band_files)

    return 0


async def scan_hours():
    """Scan through multiple hours and product types."""
    bucket = "noaa-goes18"
    hours = range(24)  # 0-23

    logger.info(f"Scanning through all hours for {TEST_DATE} in {bucket}")

    # Print header
    header = "Hour (UTC) | " + " | ".join(
        f"{product.split('-')[-1]}" for product in PRODUCT_TYPES
    )
    logger.info("-" * len(header))
    logger.info(header)
    logger.info("-" * len(header))

    # Check each hour
    for hour in hours:
        results = []

        # Check each product type
        for product_type in PRODUCT_TYPES:
            file_count = await check_hour(bucket, product_type, hour)
            results.append(file_count)

        # Print results for this hour
        time_str = f"{hour:02d}:00 UTC"
        local_time = f"{(hour - 7) % 24:02d}:00 PDT"  # Convert to Pacific time

        # Highlight hours with data
        if any(count > 0 for count in results):
            result_line = f"{hour:02d}:00 ({local_time}) | " + " | ".join(
                f"{count:^7}" for count in results
            )
            logger.info(result_line)

    logger.info("-" * len(header))
    logger.info("Completed scan of all hours")


if __name__ == "__main__":
    asyncio.run(scan_hours())
