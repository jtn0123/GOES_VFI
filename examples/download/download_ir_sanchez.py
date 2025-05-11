#!/usr/bin/env python3
"""
Download and process GOES infrared (Band 13) imagery with Sánchez colorization.
This script demonstrates proper handling of IR data with intuitive colorization.
"""
import argparse
import os
import re
from datetime import datetime
from pathlib import Path

import boto3
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config
from PIL import Image

# Configure boto3 for anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)

# Default output directories
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_ir"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_doy(date_str):
    """Convert YYYY-MM-DD to day of year."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return date_obj.timetuple().tm_yday


def create_sanchez_colormap():
    """Create a Sánchez-style colormap for IR temperatures."""
    # Define colors for different temperature ranges
    colors = [
        (0.0, (0, 0, 0)),  # Black for space/very cold
        (0.2, (80, 0, 120)),  # Purple for very cold clouds
        (0.3, (0, 0, 255)),  # Blue for cold high clouds
        (0.4, (0, 255, 255)),  # Cyan for mid-level clouds
        (0.55, (0, 255, 0)),  # Green for lower clouds
        (0.65, (255, 255, 0)),  # Yellow for very low clouds
        (0.75, (255, 150, 0)),  # Orange for warm areas
        (0.9, (255, 0, 0)),  # Red for hot areas
        (1.0, (255, 255, 255)),  # White for very hot areas
    ]

    # Create a colormap
    cmap_name = "sanchez_ir"
    cm = mcolors.LinearSegmentedColormap.from_list(cmap_name, colors)
    return cm


# Create the Sánchez colormap
SANCHEZ_CMAP = create_sanchez_colormap()


def build_s3_cmip_pattern(sector, band, satellite_num):
    """
    Build the correct pattern for CMIP files on S3.

    Key insight: Band number is part of file pattern as C{band:02d}
    """
    # IMPORTANT: Band number is included in filename pattern
    pattern = f"OR_ABI-L2-CMIP{sector}-M6C{band:02d}_G{satellite_num}_s"
    return pattern


def build_s3_prefix(product, year, doy, hour):
    """Build the correct S3 prefix for listing files."""
    # Format: product/year/doy/hour
    # Example: ABI-L2-CMIPF/2023/121/19/
    return f"{product}/{year}/{doy:03d}/{hour:02d}/"


def find_s3_files(bucket, prefix, pattern):
    """Find files in S3 bucket matching pattern."""
    print(f"Looking for files in {bucket}/{prefix} matching: {pattern}")

    matching_files = []

    try:
        # List objects with the given prefix
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        # Check each object against the pattern
        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                if pattern in key and key.endswith(".nc"):
                    matching_files.append(key)

        print(f"  Found {len(matching_files)} matching files")
        return matching_files

    except Exception as e:
        print(f"Error listing files in S3: {e}")
        return []


def download_s3_file(bucket, key, output_dir=DOWNLOAD_DIR):
    """Download a file from S3."""
    filename = os.path.basename(key)
    output_path = output_dir / filename

    if output_path.exists():
        print(f"  File already exists: {output_path}")
        return output_path

    print(f"  Downloading {filename}...")
    try:
        s3.download_file(bucket, key, str(output_path))
        print(f"  Downloaded to {output_path}")
        return output_path
    except Exception as e:
        print(f"  Error downloading {key}: {e}")
        return None


def extract_timestamp(filename):
    """Extract timestamp from GOES filename."""
    match = re.search(r"s(\d{14})", filename)
    if match:
        return match.group(1)
    return None


def process_ir_image(file_path, output_path, min_temp=180, max_temp=320):
    """
    Process IR image from a CMIP file with Sánchez colorization.

    Key insights:
    1. IR data is in brightness temperature (K)
    2. Typical range is 180K-320K
    3. Invert so cold clouds are bright (visualization standard)
    4. Use Sánchez colormap for intuitive colorization
    """
    print(f"Processing IR image from {os.path.basename(file_path)}")

    try:
        with xr.open_dataset(file_path) as ds:
            # Extract the CMI data (IR temperature)
            ir_data = ds["CMI"].values

            # Get temperature range and print diagnostic info
            actual_min = np.nanmin(ir_data)
            actual_max = np.nanmax(ir_data)
            print(f"  Temperature range: {actual_min:.1f}K - {actual_max:.1f}K")

            # If not temperature values (K), detect and handle accordingly
            if actual_min < 100 or actual_max > 350:
                print("  Data not in Kelvin, skipping temperature normalization")
                ir_norm = np.clip(ir_data, 0, 1)
            else:
                # Normalize temperature to 0-1 range with inversion
                # (cold->bright is standard for IR imagery)
                ir_norm = 1.0 - ((ir_data - min_temp) / (max_temp - min_temp))
                ir_norm = np.clip(ir_norm, 0, 1)

            # Create grayscale image
            gray_path = output_path.with_suffix(".gray.png")
            gray_data = (ir_norm * 255).astype(np.uint8)
            gray_data = np.nan_to_num(gray_data, nan=0)
            Image.fromarray(gray_data, "L").save(gray_path)
            print(f"  Saved grayscale image to {gray_path}")

            # Create Sánchez colorized image using matplotlib
            plt.figure(figsize=(10, 10), dpi=300)
            plt.imshow(ir_norm, cmap=SANCHEZ_CMAP)
            plt.axis("off")
            plt.tight_layout(pad=0)
            plt.savefig(output_path, bbox_inches="tight", pad_inches=0)
            plt.close()
            print(f"  Saved Sánchez colorized image to {output_path}")

            return output_path

    except Exception as e:
        print(f"  Error processing IR image: {e}")
        return None


def download_and_process_ir(
    date_str, hour, satellite="GOES16", sector="F", output_dir=None
):
    """
    Main function to download and process GOES IR imagery.

    Args:
        date_str: Date in YYYY-MM-DD format
        hour: Hour of day (0-23)
        satellite: Satellite name (GOES16 or GOES18)
        sector: Sector code (F=Full Disk, C=CONUS, M1/M2=Mesoscale)
        output_dir: Directory to save output files

    Returns:
        Path to the processed IR image if successful, None otherwise
    """
    # Parse satellite number
    satellite_num = satellite[-2:]

    # Parse date to year/doy
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    year = date_obj.year
    doy = date_obj.timetuple().tm_yday

    # Set up output directory
    if output_dir:
        output_dir = Path(output_dir)
    else:
        output_dir = DOWNLOAD_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # S3 bucket name
    bucket = f"noaa-{satellite.lower()}"

    # Base product name (without sector)
    base_product = "ABI-L2-CMIP"

    # Full product name with sector
    product = f"{base_product}{sector}"

    print(
        f"Downloading GOES IR (Band 13) imagery for {date_str} (DoY {doy}) {hour:02d}:00 UTC"
    )
    print(f"  Satellite: {satellite} ({bucket})")
    print(f"  Product: {product} (sector: {sector})")

    # Build S3 prefix
    prefix = build_s3_prefix(product, year, doy, hour)

    # Band 13 for clean IR
    band = 13

    # Build pattern for this band
    pattern = build_s3_cmip_pattern(sector, band, satellite_num)

    # Find files matching pattern
    files = find_s3_files(bucket, prefix, pattern)

    if not files:
        print(f"  No files found for Band {band}")
        return None

    # Sort files by name and pick the first one
    files.sort()
    selected_file = files[0]
    print(f"  Selected file: {os.path.basename(selected_file)}")

    # Extract timestamp for filename
    timestamp = extract_timestamp(selected_file) or f"{year}{doy:03d}{hour:02d}0000"

    # Download the file
    nc_path = download_s3_file(bucket, selected_file, output_dir)
    if not nc_path:
        print("  Failed to download file")
        return None

    # Process IR image with Sánchez colorization
    output_path = output_dir / f"{satellite}_{sector}_ir_sanchez_{timestamp}.png"
    result = process_ir_image(nc_path, output_path)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Download and process GOES IR imagery with Sánchez colorization"
    )
    parser.add_argument(
        "--date",
        type=str,
        default="2023-05-01",
        help="Date in YYYY-MM-DD format (default: 2023-05-01)",
    )
    parser.add_argument(
        "--hour", type=int, default=19, help="Hour of day in UTC (default: 19)"
    )
    parser.add_argument(
        "--satellite",
        choices=["GOES16", "GOES18"],
        default="GOES16",
        help="Satellite to use (default: GOES16)",
    )
    parser.add_argument(
        "--sector",
        choices=["F", "C", "M1", "M2"],
        default="F",
        help="Sector code (F=Full Disk, C=CONUS, M1/M2=Mesoscale) (default: F)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save output files (default: ~/Downloads/goes_ir)",
    )
    args = parser.parse_args()

    # Download and process
    result = download_and_process_ir(
        args.date, args.hour, args.satellite, args.sector, args.output_dir
    )

    if result:
        print(f"\nSuccess! IR imagery processed and saved to:")
        print(f"  {result}")
    else:
        print(f"\nFailed to process IR imagery")


if __name__ == "__main__":
    main()
