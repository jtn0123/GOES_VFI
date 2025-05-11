#!/usr/bin/env python3
"""
Download GOES Level-2 Mesoscale data from both M1 and M2 regions.
This script specifically targets the high-frequency (1-minute) Mesoscale imagery.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import numpy as np
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("download_mesoscale_l2")

# Configuration
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_mesoscale"))
SATELLITES = {"GOES-16": "noaa-goes16", "GOES-18": "noaa-goes18"}

# Create base download directory
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Create subdirectories for M1 and M2
(DOWNLOAD_DIR / "M1").mkdir(exist_ok=True)
(DOWNLOAD_DIR / "M2").mkdir(exist_ok=True)

# Configure S3 client with anonymous access
s3_config = Config(
    signature_version=UNSIGNED,
    region_name="us-east-1",
    retries={"max_attempts": 3, "mode": "standard"},
    read_timeout=300,  # 5 minutes
    connect_timeout=30,
)


async def list_s3_files(bucket, prefix):
    """List files in S3 bucket with given prefix."""
    s3 = boto3.client("s3", config=s3_config)
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if "Contents" in response:
            return [obj["Key"] for obj in response["Contents"]]
        return []
    except Exception as e:
        logger.error(f"Error listing files in {bucket}/{prefix}: {e}")
        return []


async def download_file(bucket, key, dest_path):
    """Download a file from S3."""
    s3 = boto3.client("s3", config=s3_config)
    try:
        logger.info(f"Downloading {bucket}/{key} to {dest_path}")
        s3.download_file(bucket, key, str(dest_path))
        file_size = dest_path.stat().st_size
        logger.info(f"Downloaded {dest_path.name} ({file_size:,} bytes)")
        return True
    except Exception as e:
        logger.error(f"Failed to download {key}: {e}")
        return False


def save_truecolor_image(nc_path, out_png):
    """Extract and save true color composite from a Level-2 CMIP NetCDF file."""
    try:
        with xr.open_dataset(nc_path) as ds:
            # Check if this file has the true color composite
            if "CMI_C01_C02_C03" in ds:
                # Get the RGB data
                rgb = ds["CMI_C01_C02_C03"].values.transpose(1, 2, 0)

                # Ensure it's scaled to 0-255
                if rgb.max() <= 1.0:
                    rgb = (rgb * 255).astype(np.uint8)
                else:
                    rgb = rgb.astype(np.uint8)

                # Save as PNG
                Image.fromarray(rgb, "RGB").save(out_png)
                logger.info(f"Saved true color image to {out_png}")
                return True
            else:
                logger.warning(f"No true color composite found in {nc_path}")
                return False
    except Exception as e:
        logger.error(f"Error processing true color image from {nc_path}: {e}")
        return False


def save_ir_image(nc_path, out_png, band=13):
    """Extract and save IR image from a Level-2 CMIP NetCDF file."""
    try:
        with xr.open_dataset(nc_path) as ds:
            # Get the CMI data for the specified band
            if "CMI" in ds:
                # Get the IR data
                ir = ds["CMI"].values

                # Scale to 0-255
                if ir.max() <= 1.0:
                    ir = (ir * 255).astype(np.uint8)
                else:
                    ir = ir.astype(np.uint8)

                # Save as grayscale PNG
                Image.fromarray(ir, "L").save(out_png)
                logger.info(f"Saved IR band {band} image to {out_png}")
                return True
            else:
                logger.warning(f"No CMI data found in {nc_path}")
                return False
    except Exception as e:
        logger.error(f"Error processing IR image from {nc_path}: {e}")
        return False


def determine_mesoscale_region(filename):
    """
    Determine whether a file is from Mesoscale-1 or Mesoscale-2 region.

    For GOES-18, the file name directly indicates the region with "RadM1" or "RadM2".
    This is much more reliable than timestamp-based heuristics.
    """
    # Check for explicit M1/M2 labeling in the filename
    if "RadM1" in filename:
        return "M1"
    elif "RadM2" in filename:
        return "M2"

    # Fallback to timestamp-based heuristic only if direct labeling is missing
    if "_s" in filename and "_e" in filename:
        timestamp = filename.split("_s")[1].split("_e")[0]

        # Use second digit of seconds as a heuristic
        if len(timestamp) > 12:
            second_digit = int(timestamp[-2])
            if second_digit % 2 == 0:
                return "M1"
            else:
                return "M2"

    # If we can't determine, default to M1
    return "M1"


async def download_mesoscale_minute_by_minute(
    satellite, date_str, hour="18", minute_range=5
):
    """
    Download mesoscale data for a range of consecutive minutes.

    Args:
        satellite: Satellite name (e.g., "GOES-18")
        date_str: Date string in format YYYY/DDD (e.g., "2023/129")
        hour: Hour string (e.g., "18")
        minute_range: Number of consecutive minutes to download (from 00)
    """
    satellite_abbr = satellite.replace("GOES-", "G")  # GOES-16 -> G16
    bucket_name = SATELLITES.get(satellite)

    minute_start = 0
    minutes = [f"{m:02d}" for m in range(minute_start, minute_start + minute_range)]

    m1_count = 0
    m2_count = 0

    for minute in minutes:
        prefix = f"ABI-L2-CMIPM/{date_str}/{hour}/{minute}/"
        files = await list_s3_files(bucket_name, prefix)

        if not files:
            logger.warning(f"No files found for {satellite} at {hour}:{minute}")
            continue

        # Process all files for this minute (there may be both M1 and M2)
        for file_key in files:
            base_filename = os.path.basename(file_key)

            # Determine if this is M1 or M2
            region = determine_mesoscale_region(base_filename)
            region_dir = DOWNLOAD_DIR / region

            # Create filenames
            nc_path = region_dir / f"{satellite_abbr}_{region}_{base_filename}"

            # Download the file
            success = await download_file(bucket_name, file_key, nc_path)

            if success:
                # Extract timestamp for output filenames
                if "_s" in base_filename:
                    timestamp = base_filename.split("_s")[1].split("_")[0]
                    # Last 6 digits are hour, minute, second
                    time_code = timestamp[-6:]

                    # Process file into images
                    truecolor_path = (
                        region_dir
                        / f"{satellite_abbr}_{region}_{time_code}_truecolor.png"
                    )
                    ir_path = (
                        region_dir / f"{satellite_abbr}_{region}_{time_code}_ir13.png"
                    )

                    tc_success = save_truecolor_image(nc_path, truecolor_path)
                    ir_success = save_ir_image(nc_path, ir_path)

                    if tc_success or ir_success:
                        if region == "M1":
                            m1_count += 1
                        else:
                            m2_count += 1

    return m1_count, m2_count


async def download_recent_mesoscale(satellite="GOES-18", hours_back=1):
    """
    Download recent mesoscale data from approximately hours_back hours ago.
    Uses current date and time to calculate the appropriate YYYY/DDD path.
    """
    # Get current time
    now = datetime.utcnow() - timedelta(hours=hours_back)

    # Format date in YYYY/DDD format
    year = now.year
    day_of_year = now.timetuple().tm_yday
    date_str = f"{year}/{day_of_year:03d}"

    # Format hour
    hour = f"{now.hour:02d}"

    logger.info(f"Downloading recent mesoscale data from {date_str} hour {hour}")

    return await download_mesoscale_minute_by_minute(
        satellite, date_str, hour, minute_range=5
    )


async def main():
    """Main function to download mesoscale data."""
    satellites = ["GOES-18"]  # Focus on GOES-18 for testing

    logger.info(f"Starting GOES Level-2 Mesoscale data download to {DOWNLOAD_DIR}")

    # Option 1: Use a specific date with known data availability
    test_date = "2025/128"  # May 7, 2025
    test_hour = "00"  # 00:00 UTC

    logger.info("Downloading mesoscale data for each satellite...")

    results = {}

    for satellite in satellites:
        logger.info(f"\nProcessing {satellite}:")

        # Download specific date
        logger.info(f"Downloading data from {test_date} hour {test_hour}...")
        m1_count, m2_count = await download_mesoscale_minute_by_minute(
            satellite, test_date, test_hour, minute_range=5
        )

        results[satellite] = {"specific_date": {"M1": m1_count, "M2": m2_count}}

        # Also try for recent data
        logger.info("Downloading recent data (from approximately 1 hour ago)...")
        recent_m1, recent_m2 = await download_recent_mesoscale(satellite, hours_back=1)

        results[satellite]["recent"] = {"M1": recent_m1, "M2": recent_m2}

    # Print summary
    logger.info("\n=== Download Summary ===")

    for satellite, counts in results.items():
        logger.info(f"\n{satellite}:")

        specific_counts = counts.get("specific_date", {})
        logger.info(f"  Specific date ({test_date} {test_hour}:00):")
        logger.info(f"    Mesoscale-1: {specific_counts.get('M1', 0)} files processed")
        logger.info(f"    Mesoscale-2: {specific_counts.get('M2', 0)} files processed")

        recent_counts = counts.get("recent", {})
        logger.info(f"  Recent data (approximately 1 hour ago):")
        logger.info(f"    Mesoscale-1: {recent_counts.get('M1', 0)} files processed")
        logger.info(f"    Mesoscale-2: {recent_counts.get('M2', 0)} files processed")

    logger.info(f"\nAll downloads completed. Files saved to: {DOWNLOAD_DIR}")
    logger.info("Check the M1 and M2 subdirectories for pre-processed PNG images")


if __name__ == "__main__":
    asyncio.run(main())
