#!/usr/bin/env python3
"""
Download and process GOES Level-2 CMIP files into usable images.
Focuses on both true color and IR imagery from ABI-L2-CMIP products.
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
from PIL import Image

import boto3
from botocore import UNSIGNED
from botocore.config import Config
import xarray as xr

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("goes_cmip_processor")

# Configuration
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_processed"))
IMAGE_DIR = DOWNLOAD_DIR / "images"
SATELLITES = {
    "GOES-16": "noaa-goes16",
    "GOES-18": "noaa-goes18"
}

# Product types
PRODUCT_TYPES = {
    "Full Disk": "CMIPF",   # 10-minute interval
    "CONUS": "CMIPC",       # 5-minute interval
    "Mesoscale": "CMIPM"    # 1-minute interval
}

# Rain rate products
RAIN_PRODUCTS = {
    "Full Disk": "RRQPEF",
    "CONUS": "RRQPEC",
    "Mesoscale": "RRQPEM"
}

# Create directories
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# Configure S3 client with anonymous access
s3_config = Config(
    signature_version=UNSIGNED,
    region_name="us-east-1"
)


async def list_cmip_files(bucket, product, year, doy, hour):
    """List CMIP files for a specific product, date and hour."""
    s3 = boto3.client("s3", config=s3_config)
    
    # Construct the prefix
    prefix = f"ABI-L2-{product}/{year}/{doy}/{hour}/"
    
    # Files by band
    files_by_band = {}
    
    # Get all files in this directory
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    
    # Process each page of results
    for page in pages:
        if "Contents" not in page:
            continue
            
        for obj in page["Contents"]:
            key = obj["Key"]
            filename = os.path.basename(key)
            
            # Check if this is a valid CMIP file with band info
            if filename.startswith("OR_ABI-L2-") and filename.endswith(".nc"):
                # Extract the band number from M6C## pattern
                band_match = filename.split("-M6C")[1].split("_")[0]
                if band_match and band_match.isdigit():
                    band = int(band_match)
                    if band not in files_by_band:
                        files_by_band[band] = []
                    files_by_band[band].append(key)
    
    return files_by_band


async def download_file(bucket, key, local_path):
    """Download a file from S3."""
    s3 = boto3.client("s3", config=s3_config)
    try:
        logger.info(f"Downloading {bucket}/{key} to {local_path}")
        s3.download_file(bucket, key, str(local_path))
        file_size = local_path.stat().st_size
        logger.info(f"Downloaded {local_path.name} ({file_size:,} bytes)")
        return True
    except Exception as e:
        logger.error(f"Failed to download {key}: {e}")
        return False


def process_ir_image(nc_path, output_path):
    """
    Process IR image from CMIP file (pre-scaled 0-255).
    For this example, we'll create a grayscale image directly.
    In a real application, you would apply the Sánchez colormap here.
    """
    try:
        with xr.open_dataset(nc_path) as ds:
            # For Level-2 CMIP files, the CMI variable is already scaled 0-255
            ir_data = ds["CMI"].values
            ir_data = ir_data.astype(np.uint8)
            
            # Save as grayscale image
            # In a real application, you would apply a colormap here
            Image.fromarray(ir_data, "L").save(output_path)
            logger.info(f"Saved IR image to {output_path}")
            return True
    except Exception as e:
        logger.error(f"Error processing IR image: {e}")
        return False


def process_true_color(nc_paths, output_path):
    """
    Process true color image from CMIP files.
    Requires 3 files for bands 1, 2, and 3.
    """
    if len(nc_paths) != 3:
        logger.error(f"Expected 3 files for true color, got {len(nc_paths)}")
        return False
    
    try:
        # Open all three files and extract the data
        with xr.open_dataset(nc_paths[0]) as ds1, \
             xr.open_dataset(nc_paths[1]) as ds2, \
             xr.open_dataset(nc_paths[2]) as ds3:
            
            # Combine into RGB array
            rgb = np.stack([
                ds1["CMI"].values,
                ds2["CMI"].values,
                ds3["CMI"].values
            ], axis=2)
            
            # Ensure data is scaled 0-255
            if rgb.max() <= 1.0:
                rgb = (rgb * 255).astype(np.uint8)
            else:
                rgb = rgb.astype(np.uint8)
            
            # Save as RGB image
            Image.fromarray(rgb, "RGB").save(output_path)
            logger.info(f"Saved true color image to {output_path}")
            return True
    except Exception as e:
        logger.error(f"Error processing true color image: {e}")
        return False


def has_true_color_composite(nc_path):
    """Check if the file has a pre-combined true color composite."""
    try:
        with xr.open_dataset(nc_path) as ds:
            return "CMI_C01_C02_C03" in ds.variables
    except Exception:
        return False


def process_true_color_composite(nc_path, output_path):
    """Process pre-combined true color composite from CMIP file."""
    try:
        with xr.open_dataset(nc_path) as ds:
            # Extract the pre-combined RGB data
            rgb = ds["CMI_C01_C02_C03"].values
            
            # Transpose to H,W,3 order
            rgb = rgb.transpose(1, 2, 0)
            
            # Ensure data is scaled 0-255
            if rgb.max() <= 1.0:
                rgb = (rgb * 255).astype(np.uint8)
            else:
                rgb = rgb.astype(np.uint8)
            
            # Save as RGB image
            Image.fromarray(rgb, "RGB").save(output_path)
            logger.info(f"Saved true color composite to {output_path}")
            return True
    except Exception as e:
        logger.error(f"Error processing true color composite: {e}")
        return False


async def download_and_process(satellite, product_type, year, doy, hour, bands_to_process=None):
    """Download and process CMIP files for the specified satellite and product."""
    bucket = SATELLITES[satellite]
    product = PRODUCT_TYPES[product_type]
    satellite_dir = DOWNLOAD_DIR / satellite.replace("-", "") / product
    satellite_dir.mkdir(parents=True, exist_ok=True)
    
    # Also create image directory
    image_dir = IMAGE_DIR / satellite.replace("-", "") / product
    image_dir.mkdir(parents=True, exist_ok=True)
    
    # Default to processing IR (band 13) and true color (bands 1, 2, 3)
    if bands_to_process is None:
        bands_to_process = [1, 2, 3, 13]  # True color + IR
    
    # List all CMIP files
    files_by_band = await list_cmip_files(bucket, product, year, doy, hour)
    
    if not files_by_band:
        logger.warning(f"No CMIP files found for {satellite} {product_type} at {year}/{doy}/{hour}")
        return False
    
    # Download and process each band
    downloaded_files = {}
    
    for band in bands_to_process:
        if band not in files_by_band:
            logger.warning(f"No files found for band {band}")
            continue
        
        # Take the first file for each band
        s3_key = files_by_band[band][0]
        filename = os.path.basename(s3_key)
        local_path = satellite_dir / filename
        
        # Download the file if it doesn't exist
        if not local_path.exists():
            success = await download_file(bucket, s3_key, local_path)
            if not success:
                continue
        else:
            logger.info(f"File already exists: {local_path}")
        
        downloaded_files[band] = local_path
    
    # Process IR image (band 13)
    if 13 in downloaded_files:
        ir_file = downloaded_files[13]
        ir_image_path = image_dir / f"{satellite.replace('-', '')}_{product}_{doy}_{hour}_IR.png"
        process_ir_image(ir_file, ir_image_path)
    
    # Process true color image (bands 1, 2, 3)
    if all(band in downloaded_files for band in [1, 2, 3]):
        # First check if band 1 file has a pre-combined true color composite
        if has_true_color_composite(downloaded_files[1]):
            # Use the pre-combined composite
            tc_image_path = image_dir / f"{satellite.replace('-', '')}_{product}_{doy}_{hour}_TrueColor.png"
            process_true_color_composite(downloaded_files[1], tc_image_path)
        else:
            # Combine the three bands manually
            tc_files = [downloaded_files[1], downloaded_files[2], downloaded_files[3]]
            tc_image_path = image_dir / f"{satellite.replace('-', '')}_{product}_{doy}_{hour}_TrueColor_manual.png"
            process_true_color(tc_files, tc_image_path)
    
    return True


async def main():
    """Main function to download and process GOES Level-2 CMIP files."""
    # Use most recent data from 2025/128
    year = "2025"
    doy = "128"
    hour = "00"
    
    logger.info("Starting GOES Level-2 CMIP download and processing")
    
    # Process for GOES-18
    satellite = "GOES-18"
    
    # Download and process Full Disk
    logger.info(f"Processing {satellite} Full Disk data")
    await download_and_process(satellite, "Full Disk", year, doy, hour)
    
    # Download and process CONUS
    logger.info(f"Processing {satellite} CONUS data")
    await download_and_process(satellite, "CONUS", year, doy, hour)
    
    # Download and process Mesoscale
    logger.info(f"Processing {satellite} Mesoscale data")
    await download_and_process(satellite, "Mesoscale", year, doy, hour)
    
    logger.info(f"All processing complete. Images saved to {IMAGE_DIR}")


if __name__ == "__main__":
    asyncio.run(main())