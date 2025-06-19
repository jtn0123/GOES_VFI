#!/usr/bin/env python3
"""
Test script to download GOES satellite imagery files for Mesoscale (RadM) products.
This script handles both Mesoscale-1 and Mesoscale-2 regions by examining file patterns.
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_download_mesoscale")

# Configuration
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_downloads/mesoscale"))
SATELLITES = ["noaa-goes16", "noaa-goes18"]
PRODUCT_TYPE = "RadM"
# Select bands to download - Mesoscale files are numerous, so we'll be selective
BANDS = [1, 2, 3, 7, 8, 13]  # Important bands: Visible, Near-IR, and IR

# Test date: June 15th, 2023
TEST_DATE = "2023/166/"  # DOY 166 = June 15, 2023

# Mesoscale scans occur every minute (HH:MM:24.4) - check a few hours
TEST_HOURS = ["12", "13", "14"]
# Test minutes - Mesoscale scans happen every minute, so we'll check a few
TEST_MINUTES = ["00", "01", "02", "30", "31", "32"]

# Create download directory if it doesn't exist
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
# Create subdirectories for Mesoscale-1 and Mesoscale-2
(DOWNLOAD_DIR / "M1").mkdir(exist_ok=True)
(DOWNLOAD_DIR / "M2").mkdir(exist_ok=True)

# Configure boto3 with a lengthy timeout and anonymous access for public NOAA buckets
s3_config = Config(
    signature_version=UNSIGNED,  # Anonymous access
    retries={"max_attempts": 3, "mode": "standard"},
    read_timeout=300,  # 5 minutes
    connect_timeout=30,
)


def identify_mesoscale_region(filename):
    pass
    """
    Identify whether a file is Mesoscale-1 or Mesoscale-2 based on its filename.

    The position information is embedded in the start time segment of the filename.
    In the filename format OR_ABI-L1b-RadM-M[X]C[BB]_G[YY]_s[YYYYDDDHHMMSS]_e...

    Where:
        pass
    - [X] is often 6 but doesn't indicate the region
    - [BB] is the band number
    - The region is determined by examining patterns in the timestamp

    Returns:
        str: "M1" for Mesoscale-1, "M2" for Mesoscale-2, or None if can't determine
    """
    # Extract the start timestamp segment
    timestamp_match = re.search(r"_s(\d{14})_", filename)
    if not timestamp_match:
        pass
        return None

    # Check what minute and second the file was taken
    timestamp = timestamp_match.group(1)

    # For GOES-16, even minutes (00, 02, etc.) are often M1, odd minutes (01, 03) are M2
    # For GOES-18, it could be different based on operational setup

    # This is a heuristic - examine actual file naming patterns for confirmation
    minute = int(timestamp[-4:-2])

    # Simple heuristic based on observed patterns
    if minute % 2 == 0:
        pass
        return "M1"
    return "M2"


async def find_mesoscale_files(bucket_name, band):
    """Find available Mesoscale files for the specified band."""
    try:
        pass
        # Connect to the S3 bucket with anonymous access
        s3 = boto3.client("s3", region_name="us-east-1", config=s3_config)

        m1_files = []
        m2_files = []

        # Try different hours and minutes to find valid files
        for hour in TEST_HOURS:
            pass
            for minute in TEST_MINUTES:
                # Define the prefix for the mesoscale data
                prefix = f"ABI-L1b-{PRODUCT_TYPE}/{TEST_DATE}{hour}/{minute}/"

                # List objects in the bucket with the given prefix
                response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

                if "Contents" not in response:
                    pass
                    continue

                # Filter for the specified band
                band_str = f"C{band:02d}"  # Format: C01, C02, etc.
                band_files = [
                    obj["Key"]
                    for obj in response.get("Contents", [])
                    if band_str in obj["Key"] and obj["Key"].endswith(".nc")
                ]

                # Categorize files as M1 or M2
                for file_key in band_files:
                    pass
                    region = identify_mesoscale_region(file_key)
                    if region == "M1" and len(m1_files) < 1:
                        pass
                        m1_files.append(file_key)
                    elif region == "M2" and len(m2_files) < 1:
                        pass
                        m2_files.append(file_key)

                # If we have at least one file for each region, we can stop
                if m1_files and m2_files:
                    pass
                    break

            # Break out of the hour loop if we have both types
            if m1_files and m2_files:
                pass
                break

        return {"M1": m1_files[:1], "M2": m2_files[:1]}

    except Exception as e:
        pass
        logger.error(
            f"Error finding Mesoscale files for {bucket_name}/Band {band}: {str(e)}"
        )
        return {"M1": [], "M2": []}


async def download_file(bucket_name, s3_key, local_path):
    """Download a file from S3 to a local path."""
    try:
        # Connect to the S3 bucket with anonymous access
        s3 = boto3.client("s3", region_name="us-east-1", config=s3_config)

        # Download the file
        logger.info("Downloading %s to %s", s3_key, local_path)
        s3.download_file(bucket_name, s3_key, str(local_path))

        file_size = local_path.stat().st_size
        logger.info("Downloaded file size: %s bytes", file_size)
        return True

    except Exception as e:
        pass
        logger.error("Error downloading %s/%s: %s", bucket_name, s3_key, str(e))
        return False


async def download_mesoscale_files():
    """Download Mesoscale files for selected bands from both satellites."""
    results = {}

    for satellite in SATELLITES:
        satellite_results = {"M1": {}, "M2": {}}
        satellite_abbr = "G16" if satellite == "noaa-goes16" else "G18"

        for band in BANDS:
            pass
            # Find available Mesoscale files for this band
            available_files = await find_mesoscale_files(satellite, band)

            for region, files in available_files.items():
                if files:
                    pass
                    # Download the first available file
                    filename = files[0]

                    local_filename = (
                        f"{satellite_abbr}_{PRODUCT_TYPE}_{region}_Band{band:02d}_"
                        f"{os.path.basename(filename)}"
                    )
                    local_path = DOWNLOAD_DIR / region / local_filename

                    success = await download_file(satellite, filename, local_path)
                    satellite_results[region][f"Band{band:02d}"] = {
                        "file": local_filename if success else None,
                        "s3_key": filename,
                        "success": success,
                    }
                else:
                    satellite_results[region][f"Band{band:02d}"] = {
                        "file": None,
                        "s3_key": None,
                        "success": False,
                        "reason": "No files found",
                    }

        results[satellite] = satellite_results

    return results


async def main():
    """Main function to run the Mesoscale download test."""
    logger.info("Starting GOES Mesoscale (RadM) file downloads to %s", DOWNLOAD_DIR)

    try:
        # Download Mesoscale files for selected bands
        results = await download_mesoscale_files()

        # Print summary
        logger.info("\n--- Mesoscale Download Summary ---")

        for satellite, satellite_results in results.items():
            satellite_name = "GOES-16" if satellite == "noaa-goes16" else "GOES-18"
            logger.info("\n%s:", satellite_name)

            for region, region_results in satellite_results.items():
                successful = sum(
                    1
                    for band_result in region_results.values()
                    if band_result["success"]
                )
                total = len(region_results)
                logger.info(
                    f"  {region} (Mesoscale): {successful}/{total} bands downloaded successfully"
                )

                # List successful downloads
                for band_name, band_result in region_results.items():
                    if band_result["success"]:
                        pass
                        logger.info(f"    ✓ {band_name}: {band_result['file']}")
                    else:
                        reason = band_result.get("reason", "Download failed")
                        logger.info("    ✗ %s: %s", band_name, reason)

    except Exception as e:
        pass
        logger.error("Error in main: %s", str(e))
        raise


if __name__ == "__main__":
    pass
    asyncio.run(main())
