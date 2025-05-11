#!/usr/bin/env python3
"""
Download GOES Level-2 data products and save as ready-to-view images.
This script focuses on the Level-2 CMIP products which contain pre-processed imagery.
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
logger = logging.getLogger("download_goes_l2")

# Configuration
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_l2_downloads"))
SATELLITES = {"GOES-16": "noaa-goes16", "GOES-18": "noaa-goes18"}

# Product types
PRODUCT_TYPES = {
    "Full Disk": "CMIPF",  # 10-minute interval
    "CONUS": "CMIPC",  # 5-minute interval
    "Mesoscale": "CMIPM",  # 1-minute interval
}

# Rain rate products
RAIN_PRODUCTS = {"Full Disk": "RRQPEF", "CONUS": "RRQPEC", "Mesoscale": "RRQPEM"}

# Create base download directory
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Create subdirectories for each product type
for product in PRODUCT_TYPES.values():
    (DOWNLOAD_DIR / product).mkdir(exist_ok=True)

# Create subdirectories for rain rate products
for product in RAIN_PRODUCTS.values():
    (DOWNLOAD_DIR / product).mkdir(exist_ok=True)

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


def save_rainfall_image(nc_path, out_png):
    """Extract and save rainfall rate from a Level-2 RRQPE NetCDF file."""
    try:
        with xr.open_dataset(nc_path) as ds:
            if "RRQPE" in ds:
                # Get the rainfall rate data
                rain_rate = ds["RRQPE"].values

                # Create a simple colormap for rainfall
                # Scale rainfall rate to 0-255
                # This is a simple scaling that could be improved
                rain_scaled = np.clip(rain_rate * 10, 0, 255).astype(np.uint8)

                # Create a simple colormap: blue for light rain, red for heavy
                colormap = np.zeros((256, 3), dtype=np.uint8)
                # Blue to red gradient
                colormap[:, 0] = np.linspace(0, 255, 256)  # Red increases
                colormap[:, 2] = np.linspace(255, 0, 256)  # Blue decreases

                # Apply colormap
                rgb = colormap[rain_scaled]

                # Save as PNG
                Image.fromarray(rgb, "RGB").save(out_png)
                logger.info(f"Saved rainfall rate image to {out_png}")
                return True
            else:
                logger.warning(f"No RRQPE data found in {nc_path}")
                return False
    except Exception as e:
        logger.error(f"Error processing rainfall rate from {nc_path}: {e}")
        return False


async def download_and_process_cmip(
    satellite, product_type, date_str, hour="12", minutes=None
):
    """Download and process Level-2 CMIP files for a satellite and product type."""
    # Map product type to the actual product name in S3
    product_name = PRODUCT_TYPES.get(product_type)
    if not product_name:
        logger.error(f"Unknown product type: {product_type}")
        return False

    # Map satellite to bucket name
    bucket_name = SATELLITES.get(satellite)
    if not bucket_name:
        logger.error(f"Unknown satellite: {satellite}")
        return False

    # Default minutes based on product type
    if minutes is None:
        if product_type == "Full Disk":
            minutes = ["00", "10", "20", "30", "40", "50"]
        elif product_type == "CONUS":
            minutes = [
                "01",
                "06",
                "11",
                "16",
                "21",
                "26",
                "31",
                "36",
                "41",
                "46",
                "51",
                "56",
            ]
        elif product_type == "Mesoscale":
            # Just a sample of minutes for Mesoscale
            minutes = ["00", "01", "02", "03", "04", "05"]

    satellite_abbr = satellite.replace("GOES-", "G")  # GOES-16 -> G16

    # Create directory for this product
    product_dir = DOWNLOAD_DIR / product_name
    product_dir.mkdir(exist_ok=True)

    success_count = 0
    failed_count = 0

    # Process for each minute
    for minute in minutes:
        # Generate the S3 prefix for this product, date, hour, minute
        prefix = f"ABI-L2-{product_name}/{date_str}/{hour}/{minute}/"

        # List files in this prefix
        files = await list_s3_files(bucket_name, prefix)

        if not files:
            logger.warning(
                f"No files found for {satellite} {product_type} at {hour}:{minute}"
            )
            continue

        # Take the first file for each minute (usually there's only one)
        file_key = files[0]

        # Create descriptive filenames
        base_filename = os.path.basename(file_key)
        nc_path = product_dir / f"{satellite_abbr}_{product_name}_{base_filename}"

        # Download the file
        success = await download_file(bucket_name, file_key, nc_path)

        if success:
            # Process the file to extract images
            # 1. True color image
            truecolor_path = (
                product_dir
                / f"{satellite_abbr}_{product_name}_{hour}{minute}_truecolor.png"
            )
            success_tc = save_truecolor_image(nc_path, truecolor_path)

            # 2. IR image (Band 13)
            ir_path = (
                product_dir / f"{satellite_abbr}_{product_name}_{hour}{minute}_ir13.png"
            )
            success_ir = save_ir_image(nc_path, ir_path)

            # Only count as success if at least one image was extracted
            if success_tc or success_ir:
                success_count += 1
            else:
                failed_count += 1
        else:
            failed_count += 1

    return success_count, failed_count


async def download_and_process_rainfall(
    satellite, product_type, date_str, hour="12", minutes=None
):
    """Download and process Level-2 RRQPE (rainfall) files for a satellite and product type."""
    # Map product type to the actual product name in S3
    product_name = RAIN_PRODUCTS.get(product_type)
    if not product_name:
        logger.error(f"Unknown product type for rainfall: {product_type}")
        return False

    # Map satellite to bucket name
    bucket_name = SATELLITES.get(satellite)
    if not bucket_name:
        logger.error(f"Unknown satellite: {satellite}")
        return False

    # Default minutes based on product type
    if minutes is None:
        if product_type == "Full Disk":
            minutes = ["00", "10", "20", "30", "40", "50"]
        elif product_type == "CONUS":
            minutes = [
                "01",
                "06",
                "11",
                "16",
                "21",
                "26",
                "31",
                "36",
                "41",
                "46",
                "51",
                "56",
            ]
        elif product_type == "Mesoscale":
            # Just a sample of minutes for Mesoscale
            minutes = ["00", "01", "02", "03", "04", "05"]

    satellite_abbr = satellite.replace("GOES-", "G")  # GOES-16 -> G16

    # Create directory for this product
    product_dir = DOWNLOAD_DIR / product_name
    product_dir.mkdir(exist_ok=True)

    success_count = 0
    failed_count = 0

    # Process for each minute
    for minute in minutes:
        # Generate the S3 prefix for this product, date, hour, minute
        prefix = f"ABI-L2-{product_name}/{date_str}/{hour}/{minute}/"

        # List files in this prefix
        files = await list_s3_files(bucket_name, prefix)

        if not files:
            logger.warning(
                f"No rainfall files found for {satellite} {product_type} at {hour}:{minute}"
            )
            continue

        # Take the first file for each minute (usually there's only one)
        file_key = files[0]

        # Create descriptive filenames
        base_filename = os.path.basename(file_key)
        nc_path = product_dir / f"{satellite_abbr}_{product_name}_{base_filename}"

        # Download the file
        success = await download_file(bucket_name, file_key, nc_path)

        if success:
            # Process the file to extract rainfall image
            rain_path = (
                product_dir
                / f"{satellite_abbr}_{product_name}_{hour}{minute}_rainfall.png"
            )
            if save_rainfall_image(nc_path, rain_path):
                success_count += 1
            else:
                failed_count += 1
        else:
            failed_count += 1

    return success_count, failed_count


async def download_mesoscale_regions(satellite, date_str, hour="12"):
    """Download Mesoscale data for both M1 and M2 regions based on timing patterns."""
    # For Mesoscale, we need to find both M1 and M2 regions
    # We'll use specific times when each is active
    # M1 often runs on even minutes (00, 02, etc.)
    # M2 often runs on odd minutes (01, 03, etc.)

    # Create separate directories for M1 and M2
    m1_dir = DOWNLOAD_DIR / "CMIPM" / "M1"
    m2_dir = DOWNLOAD_DIR / "CMIPM" / "M2"
    m1_dir.mkdir(parents=True, exist_ok=True)
    m2_dir.mkdir(parents=True, exist_ok=True)

    satellite_abbr = satellite.replace("GOES-", "G")  # GOES-16 -> G16
    bucket_name = SATELLITES.get(satellite)

    # Sample minutes to test even/odd pattern for M1/M2
    test_minutes = [
        "00",
        "01",
        "02",
        "03",
        "04",
        "05",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
    ]

    m1_files = []
    m2_files = []

    # First, scan for available files
    for minute in test_minutes:
        prefix = f"ABI-L2-CMIPM/{date_str}/{hour}/{minute}/"
        files = await list_s3_files(bucket_name, prefix)

        for file_key in files:
            # Examine start time in filename to determine if M1 or M2
            # Example: OR_ABI-L2-CMIPM-M6_G18_s20251291800244_e20251291800506_c20251291800596.nc
            filename = os.path.basename(file_key)

            # Extract timestamp info (simplified heuristic)
            # In reality, we'd need to analyze a larger dataset to determine the exact pattern
            if "_s" in filename and "_e" in filename:
                timestamp = filename.split("_s")[1].split("_e")[0]
                # Simplified heuristic: even seconds tend to be M1, odd seconds M2
                if len(timestamp) > 12:  # Make sure we have enough digits
                    second_digit = int(timestamp[-2])  # Second digit of seconds
                    if second_digit % 2 == 0:
                        m1_files.append(file_key)
                    else:
                        m2_files.append(file_key)

    # Process M1 files
    m1_success = 0
    m2_success = 0

    # Download and process up to 3 M1 files
    for file_key in m1_files[:3]:
        base_filename = os.path.basename(file_key)
        nc_path = m1_dir / f"{satellite_abbr}_CMIPM_M1_{base_filename}"

        success = await download_file(bucket_name, file_key, nc_path)
        if success:
            # Extract timestamp for filenames
            if "_s" in base_filename:
                timestamp = base_filename.split("_s")[1].split("_")[0]
                # Last 4 digits are minute and second
                minute_sec = timestamp[-6:-2]

                # Process the file to extract images
                truecolor_path = (
                    m1_dir / f"{satellite_abbr}_M1_{minute_sec}_truecolor.png"
                )
                ir_path = m1_dir / f"{satellite_abbr}_M1_{minute_sec}_ir13.png"

                tc_success = save_truecolor_image(nc_path, truecolor_path)
                ir_success = save_ir_image(nc_path, ir_path)

                if tc_success or ir_success:
                    m1_success += 1

    # Download and process up to 3 M2 files
    for file_key in m2_files[:3]:
        base_filename = os.path.basename(file_key)
        nc_path = m2_dir / f"{satellite_abbr}_CMIPM_M2_{base_filename}"

        success = await download_file(bucket_name, file_key, nc_path)
        if success:
            # Extract timestamp for filenames
            if "_s" in base_filename:
                timestamp = base_filename.split("_s")[1].split("_")[0]
                # Last 4 digits are minute and second
                minute_sec = timestamp[-6:-2]

                # Process the file to extract images
                truecolor_path = (
                    m2_dir / f"{satellite_abbr}_M2_{minute_sec}_truecolor.png"
                )
                ir_path = m2_dir / f"{satellite_abbr}_M2_{minute_sec}_ir13.png"

                tc_success = save_truecolor_image(nc_path, truecolor_path)
                ir_success = save_ir_image(nc_path, ir_path)

                if tc_success or ir_success:
                    m2_success += 1

    return m1_success, m2_success


async def main():
    """Main function to download and process GOES Level-2 data."""
    # Use noon Pacific time on May 5, 2025
    test_date = "2025/125"
    test_hour = "19"  # 19:00 UTC (noon Pacific Daylight Time)

    logger.info(f"Starting GOES Level-2 data download to {DOWNLOAD_DIR}")
    results = {}

    # Download data for GOES-18 (West)
    satellite_name = "GOES-18"
    satellite_results = {}

    # 1. Download Full Disk (CMIPF) data
    logger.info(f"Downloading {satellite_name} Full Disk (CMIPF) data...")
    success, failed = await download_and_process_cmip(
        satellite_name, "Full Disk", test_date, test_hour, minutes=["00", "10"]
    )
    satellite_results["CMIPF"] = {"success": success, "failed": failed}

    # 2. Download CONUS (CMIPC) data
    logger.info(f"Downloading {satellite_name} CONUS (CMIPC) data...")
    success, failed = await download_and_process_cmip(
        satellite_name, "CONUS", test_date, test_hour, minutes=["01", "06"]
    )
    satellite_results["CMIPC"] = {"success": success, "failed": failed}

    # 3. Download Mesoscale data - both M1 and M2
    logger.info(f"Downloading {satellite_name} Mesoscale (CMIPM) data...")
    m1_success, m2_success = await download_mesoscale_regions(
        satellite_name, test_date, test_hour
    )
    satellite_results["CMIPM"] = {"M1_success": m1_success, "M2_success": m2_success}

    # 4. Download Full Disk rainfall data
    logger.info(f"Downloading {satellite_name} Full Disk (RRQPEF) rainfall data...")
    success, failed = await download_and_process_rainfall(
        satellite_name, "Full Disk", test_date, test_hour, minutes=["00", "10"]
    )
    satellite_results["RRQPEF"] = {"success": success, "failed": failed}

    results[satellite_name] = satellite_results

    # Print summary
    logger.info("\n=== Download and Processing Summary ===")

    for satellite, products in results.items():
        logger.info(f"\n{satellite}:")

        total_success = 0
        total_failed = 0

        for product_type, counts in products.items():
            if product_type == "CMIPM":
                # Special handling for Mesoscale
                m1_success = counts.get("M1_success", 0)
                m2_success = counts.get("M2_success", 0)
                logger.info(
                    f"  Mesoscale ({product_type}): M1 success: {m1_success}, M2 success: {m2_success}"
                )
                total_success += m1_success + m2_success
            else:
                success = counts.get("success", 0)
                failed = counts.get("failed", 0)
                logger.info(
                    f"  {product_type}: {success}/{success + failed} files processed successfully"
                )
                total_success += success
                total_failed += failed

        logger.info(
            f"  Total: {total_success}/{total_success + total_failed} files processed successfully"
        )

    logger.info(f"\nAll downloads completed. Files saved to: {DOWNLOAD_DIR}")
    logger.info(
        "Check the subdirectories for pre-processed PNG images extracted from the NetCDF files"
    )


if __name__ == "__main__":
    asyncio.run(main())
