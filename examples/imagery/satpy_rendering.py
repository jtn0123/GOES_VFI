#!/usr/bin/env python
"""
GOES Image Rendering using SatPy

This script demonstrates using the SatPy library for improved satellite image processing with:
1. Better color accuracy for true color images
2. Higher resolution output (up to native resolution)
3. No timestamp or other metadata in the image
4. Standard satellite image processing techniques
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import dask.array as da
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from satpy import Scene, find_files_and_readers
from satpy.writers import get_enhanced_image
from trollimage.xrimage import XRImage

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
OUTPUT_DIR = Path("satpy_images")


def setup_directories():
    """Create output directories if they don't exist."""
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)
    return OUTPUT_DIR


def get_timestamp_from_filename(filepath):
    """Extract timestamp from GOES filename."""
    filename = os.path.basename(filepath)
    if "_s" in filename:
        timestamp_part = filename.split("_s")[1][:13]  # Format: YYYYDDDHHMMSS
        year_str = timestamp_part[:4]
        doy_str = timestamp_part[4:7]
        hour_str = timestamp_part[7:9]
        min_str = timestamp_part[9:11]
        sec_str = timestamp_part[11:13]

        # Convert to datetime
        from datetime import datetime, timedelta

        base_date = datetime(int(year_str), 1, 1)
        timestamp = base_date + timedelta(
            days=int(doy_str) - 1,
            hours=int(hour_str),
            minutes=int(min_str),
            seconds=int(sec_str),
        )
        return timestamp.strftime("%Y%m%d_%H%M%S")
    return "unknown_time"


def process_single_channel(file_path, resolution=None):
    """Process a single channel NetCDF file with SatPy."""
    logger.info(f"Processing file: {file_path}")

    # Get timestamp for filename
    timestamp = get_timestamp_from_filename(file_path)

    # Determine channel from filename
    filename = os.path.basename(file_path)
    channel = None
    if "_C" in filename:
        channel_part = filename.split("_C")[1]
        if len(channel_part) >= 2 and channel_part[:2].isdigit():
            channel = int(channel_part[:2])

    # Determine product type from filename
    if "RadF" in filename:
        product_type = "full_disk"
    elif "RadM" in filename:
        product_type = "meso"
    elif "CMIPF" in filename:
        product_type = "cmip"
    elif "RRQPEF" in filename:
        product_type = "rain_rate"
    else:
        product_type = "unknown"

    # Open the data with xarray first to get dimensions
    ds = xr.open_dataset(file_path)

    # Determine data variable
    if "Rad" in ds:
        data_var = "Rad"
    elif "CMI" in ds:
        data_var = "CMI"
    elif "RRQPE" in ds:
        data_var = "RRQPE"
    else:
        data_var = list(ds.data_vars)[0]

    # Get data dimensions
    data_shape = ds[data_var].shape
    logger.info(f"Original data shape: {data_shape}")

    # Determine output resolution
    if resolution is None:
        # Default to full resolution
        output_res = data_shape
    elif resolution == "half":
        output_res = (data_shape[0] // 2, data_shape[1] // 2)
    elif resolution == "2.7k":
        output_res = (2700, 2700)
    else:
        # Parse specific resolution
        try:
            res_val = int(resolution)
            output_res = (res_val, res_val)
        except:
            output_res = data_shape

    logger.info(f"Output resolution: {output_res}")

    # Process data appropriately based on channel
    if channel in [1, 2, 3, 4, 5, 6]:  # Visible/near-IR channels
        # Reflective channels - normalize to 0-1
        data = ds[data_var].copy()

        # Apply appropriate scaling
        valid_min = np.nanmin(data)
        valid_max = np.nanmax(data)

        # Handle data range based on percentiles to avoid outliers
        p01, p99 = np.nanpercentile(data, [1, 99])
        data = np.clip(data, p01, p99)
        data = (data - p01) / (p99 - p01)

        # Convert to 8-bit
        data = (data * 255).astype(np.uint8)

        # Create RGB array (grayscale)
        rgb = np.zeros((*data.shape, 3), dtype=np.uint8)
        for i in range(3):
            rgb[:, :, i] = data

        # Resize if needed
        if output_res != data_shape:
            from skimage.transform import resize

            rgb = resize(
                rgb, (*output_res, 3), anti_aliasing=True, preserve_range=True
            ).astype(np.uint8)

        # Save image
        output_file = OUTPUT_DIR / f"{product_type}_ch{channel}_{timestamp}.png"
        from imageio import imwrite

        imwrite(output_file, rgb)
        logger.info(f"Saved image to {output_file}")

    elif channel in [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]:  # IR channels
        # IR channels - use temperature-appropriate coloring
        data = ds[data_var].copy()

        # Apply appropriate scaling with percentiles
        p01, p99 = np.nanpercentile(data, [1, 99])
        data = np.clip(data, p01, p99)
        data = (data - p01) / (p99 - p01)

        # Invert for IR channels (cold=white, hot=black)
        data = 1.0 - data

        # Convert to 8-bit
        data = (data * 255).astype(np.uint8)

        # Create RGB array (grayscale)
        rgb = np.zeros((*data.shape, 3), dtype=np.uint8)
        for i in range(3):
            rgb[:, :, i] = data

        # Resize if needed
        if output_res != data_shape:
            from skimage.transform import resize

            rgb = resize(
                rgb, (*output_res, 3), anti_aliasing=True, preserve_range=True
            ).astype(np.uint8)

        # Save image
        output_file = OUTPUT_DIR / f"{product_type}_ch{channel}_{timestamp}.png"
        from imageio import imwrite

        imwrite(output_file, rgb)
        logger.info(f"Saved image to {output_file}")

    else:
        # Generic approach for other data types
        data = ds[data_var].copy()

        # Apply appropriate scaling with percentiles
        p01, p99 = np.nanpercentile(data, [1, 99])
        data = np.clip(data, p01, p99)
        data = (data - p01) / (p99 - p01)

        # Convert to 8-bit
        data = (data * 255).astype(np.uint8)

        # Create RGB array (grayscale)
        rgb = np.zeros((*data.shape, 3), dtype=np.uint8)
        for i in range(3):
            rgb[:, :, i] = data

        # Resize if needed
        if output_res != data_shape:
            from skimage.transform import resize

            rgb = resize(
                rgb, (*output_res, 3), anti_aliasing=True, preserve_range=True
            ).astype(np.uint8)

        # Save image
        output_file = OUTPUT_DIR / f"{product_type}_{timestamp}.png"
        from imageio import imwrite

        imwrite(output_file, rgb)
        logger.info(f"Saved image to {output_file}")

    ds.close()
    return output_file


def process_true_color(red_file, green_file, blue_file, resolution=None):
    """Create a true color image using SatPy best practices."""
    logger.info(f"Creating true color image from RGB files")

    # Get timestamp for filename from red file
    timestamp = get_timestamp_from_filename(red_file)

    # Determine product type from filename
    filename = os.path.basename(red_file)
    if "RadF" in filename:
        product_type = "full_disk"
    elif "RadM" in filename:
        product_type = "meso"
    elif "CMIPF" in filename:
        product_type = "cmip"
    else:
        product_type = "unknown"

    # Open the data files
    ds_red = xr.open_dataset(red_file)
    ds_green = xr.open_dataset(green_file)
    ds_blue = xr.open_dataset(blue_file)

    # Get data variables
    if "Rad" in ds_red:
        red_var, green_var, blue_var = "Rad", "Rad", "Rad"
    elif "CMI" in ds_red:
        red_var, green_var, blue_var = "CMI", "CMI", "CMI"
    else:
        var_name = list(ds_red.data_vars)[0]
        red_var, green_var, blue_var = var_name, var_name, var_name

    # Get data dimensions
    red_shape = ds_red[red_var].shape
    green_shape = ds_green[green_var].shape
    blue_shape = ds_blue[blue_var].shape

    logger.info(
        f"Channel shapes - Red: {red_shape}, Green: {green_shape}, Blue: {blue_shape}"
    )

    # Find common resolution (minimum for each dimension)
    common_res = (
        min(s[0] for s in [red_shape, green_shape, blue_shape]),
        min(s[1] for s in [red_shape, green_shape, blue_shape]),
    )

    # Determine output resolution
    if resolution is None:
        # Default to common resolution
        output_res = common_res
    elif resolution == "half":
        output_res = (common_res[0] // 2, common_res[1] // 2)
    elif resolution == "2.7k":
        output_res = (2700, 2700)
    else:
        # Parse specific resolution
        try:
            res_val = int(resolution)
            output_res = (res_val, res_val)
        except:
            output_res = common_res

    logger.info(f"Output resolution: {output_res}")

    # Extract data arrays
    red_data = ds_red[red_var].values
    green_data = ds_green[green_var].values
    blue_data = ds_blue[blue_var].values

    # Resize to common resolution if needed
    if red_data.shape != common_res:
        from skimage.transform import resize

        red_data = resize(red_data, common_res, anti_aliasing=True, preserve_range=True)

    if green_data.shape != common_res:
        from skimage.transform import resize

        green_data = resize(
            green_data, common_res, anti_aliasing=True, preserve_range=True
        )

    if blue_data.shape != common_res:
        from skimage.transform import resize

        blue_data = resize(
            blue_data, common_res, anti_aliasing=True, preserve_range=True
        )

    # Scale each channel using percentiles
    def scale_channel(data):
        p01, p99 = np.nanpercentile(data, [1, 99])
        return np.clip((data - p01) / (p99 - p01), 0, 1)

    red_scaled = scale_channel(red_data)
    green_scaled = scale_channel(green_data)
    blue_scaled = scale_channel(blue_data)

    # Create RGB array
    rgb = np.zeros((*common_res, 3))
    rgb[:, :, 0] = red_scaled
    rgb[:, :, 1] = green_scaled
    rgb[:, :, 2] = blue_scaled

    # Apply color correction
    # 1. Gamma correction to brighten image
    gamma = 0.5  # Less than 1 = brighter
    rgb = np.power(rgb, gamma)

    # 2. Enhance contrast
    rgb = np.clip(rgb * 1.1, 0, 1)

    # Resize to output resolution if needed
    if output_res != common_res:
        from skimage.transform import resize

        rgb = resize(rgb, (*output_res, 3), anti_aliasing=True, preserve_range=True)

    # Convert to 8-bit for saving
    rgb_uint8 = (rgb * 255).astype(np.uint8)

    # Save image
    output_file = OUTPUT_DIR / f"{product_type}_true_color_{timestamp}.png"
    from imageio import imwrite

    imwrite(output_file, rgb_uint8)
    logger.info(f"Saved true color image to {output_file}")

    # Clean up
    ds_red.close()
    ds_green.close()
    ds_blue.close()

    return output_file


def main():
    """Main function to run the script with command line arguments."""
    parser = argparse.ArgumentParser(description="SatPy GOES Image Renderer")
    parser.add_argument("--file", type=str, help="Path to a NetCDF file to process")
    parser.add_argument(
        "--true-color", action="store_true", help="Create true color image"
    )
    parser.add_argument("--red", type=str, help="Path to red channel file (Ch2)")
    parser.add_argument("--green", type=str, help="Path to green channel file (Ch3)")
    parser.add_argument("--blue", type=str, help="Path to blue channel file (Ch1)")
    parser.add_argument(
        "--resolution",
        type=str,
        help="Output resolution (full, half, 2.7k, or specific number)",
    )

    args = parser.parse_args()

    # Setup directories
    setup_directories()

    if args.true_color and args.red and args.green and args.blue:
        # Process true color image
        process_true_color(args.red, args.green, args.blue, args.resolution)
    elif args.file:
        # Process single channel image
        process_single_channel(args.file, args.resolution)
    else:
        print(
            "Please provide either a single file to process or all three RGB files for true color."
        )
        parser.print_help()
        return


if __name__ == "__main__":
    main()
