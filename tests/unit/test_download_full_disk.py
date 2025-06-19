#!/usr/bin/env python3
"""
Test script to download GOES satellite imagery files for Full Disk (RadF) products.
This script downloads Full Disk images for all bands from both GOES-16 and GOES-18.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import botocore.session
from botocore.config import Config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_download_full_disk")

# Configuration
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_downloads/full_disk"))
SATELLITES = ["noaa-goes16", "noaa-goes18"]
PRODUCT_TYPE = "RadF"
# All 16 bands
BANDS = list(range(1, 17))

# Test date: June 15th, 2023
TEST_DATE = "2023/166/"  # DOY 166 = June 15, 2023

# Full Disk scan hours - they occur every 10 minutes at HH:00:00.3, HH:10:00.3, etc.
# Checking a few hours to find viable files
TEST_HOURS = ["12", "13", "14", "15"]

# Create download directory if it doesn't exist
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Configure boto3 with a lengthy timeout for large files
s3_config = Config(
    retries={"max_attempts": 3, "mode": "standard"},
    read_timeout=300,  # 5 minutes
    connect_timeout=30,
)


async def find_full_disk_files(bucket_name, band):
    """Find available Full Disk files for the specified band."""
    try:
        pass
        # Connect to the S3 bucket with anonymous access
        s3 = boto3.client(
            "s3",
            region_name="us-east-1",
            config=s3_config,
            signature_version=botocore.UNSIGNED,
        )

        band_files = []

        # Try different hours to find a valid file
        for hour in TEST_HOURS:
            pass
            # Define the prefix for the full disk
            prefix = f"ABI-L1b-{PRODUCT_TYPE}/{TEST_DATE}{hour}/"

            # List objects in the bucket with the given prefix
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

            # Filter for the specified band
            band_str = f"C{band:02d}"  # Format: C01, C02, etc.
            hour_files = [
                obj["Key"]
                for obj in response.get("Contents", [])
                if band_str in obj["Key"] and obj["Key"].endswith(".nc")
            ]

            if hour_files:
                pass
                band_files.extend(hour_files[:1])  # Take the first file from each hour

                # If we found a file, we can stop looking through hours
                if len(band_files) >= 1:
                    pass
                    break

        return band_files

    except Exception as e:
        pass
        logger.error(
            f"Error finding Full Disk files for {bucket_name}/Band {band}: {str(e)}"
        )
        return []


async def download_file(bucket_name, s3_key, local_path):
    """Download a file from S3 to a local path."""
    try:
        # Connect to the S3 bucket with anonymous access
        s3 = boto3.client(
            "s3",
            region_name="us-east-1",
            config=s3_config,
            signature_version=botocore.UNSIGNED,
        )

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


async def download_full_disk_files():
    """Download Full Disk files for all bands from both satellites."""
    results = {}

    for satellite in SATELLITES:
        satellite_results = {}
        satellite_abbr = "G16" if satellite == "noaa-goes16" else "G18"

        for band in BANDS:
            pass
            # Find available Full Disk files for this band
            available_files = await find_full_disk_files(satellite, band)

            if available_files:
                pass
                # Download the first available file
                filename = available_files[0]

                local_filename = (
                    f"{satellite_abbr}_{PRODUCT_TYPE}_Band{band:02d}_"
                    f"{os.path.basename(filename)}"
                )
                local_path = DOWNLOAD_DIR / local_filename

                success = await download_file(satellite, filename, local_path)
                satellite_results[f"Band{band:02d}"] = {
                    "file": local_filename if success else None,
                    "s3_key": filename,
                    "success": success,
                }
            else:
                satellite_results[f"Band{band:02d}"] = {
                    "file": None,
                    "s3_key": None,
                    "success": False,
                    "reason": "No files found",
                }

        results[satellite] = satellite_results

    return results


async def main():
    """Main function to run the Full Disk download test."""
    logger.info("Starting GOES Full Disk (RadF) file downloads to %s", DOWNLOAD_DIR)

    try:
        # Download Full Disk files for all bands
        results = await download_full_disk_files()

        # Print summary
        logger.info("\n--- Full Disk Download Summary ---")

        for satellite, satellite_results in results.items():
            satellite_name = "GOES-16" if satellite == "noaa-goes16" else "GOES-18"
            logger.info("\n%s:", satellite_name)

            successful = sum(
                1
                for band_result in satellite_results.values()
                if band_result["success"]
            )
            total = len(satellite_results)
            logger.info(
                f"  Full Disk (RadF): {successful}/{total} bands downloaded successfully"
            )

            # List successful downloads
            for band_name, band_result in satellite_results.items():
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
