#!/usr/bin/env python
"""
Test script for downloading and processing GOES NetCDF files from S3.

This script demonstrates how to:
1. Download specific NetCDF files from the NOAA GOES S3 buckets
2. Extract and process individual channels from the NetCDF files
3. Save the extracted data as PNG images

Usage:
    python test_netcdf_channel_extraction.py
"""

import logging
import sys
import tempfile
from pathlib import Path

import boto3
import botocore
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configure S3 client without credentials (for public bucket access)
s3_client = boto3.client(
    "s3",
    region_name="us-east-1",
    config=botocore.config.Config(signature_version=botocore.UNSIGNED),
)


def download_file_from_s3(bucket: str, key: str, local_path: Path) -> Path:
    """
    Download a file from S3 to a local path.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        local_path: Local path to save the file

    Returns:
        Path to the downloaded file
    """
    logger.info("Downloading s3://%s/%s to %s", bucket, key, local_path)

    # Create directory if it doesn't exist
    local_path.parent.mkdir(parents=True, exist_ok=True)

    # Download the file
    s3_client.download_file(bucket, key, str(local_path))

    if local_path.exists():
        logger.info(
            f"Download successful: {local_path} ({local_path.stat().st_size} bytes)"
        )
        return local_path
    raise FileNotFoundError(f"Downloaded file not found: {local_path}")


def extract_channel_from_netcdf(
    netcdf_path: Path, channel_var: str = "Rad"
) -> np.ndarray:
    """
    Extract channel data from a NetCDF file.

    Args:
        netcdf_path: Path to the NetCDF file
        channel_var: Variable name for the channel data (default: "Rad" for radiance)

    Returns:
        NumPy array containing the channel data
    """
    logger.info(f"Extracting channel '{channel_var}' from {netcdf_path}")

    with xr.open_dataset(netcdf_path) as ds:
        # Log available variables for debugging
        logger.info("Available variables: %s", list(ds.variables.keys()))

        if channel_var in ds.variables:
            # Get the data
            data = ds[channel_var].values

            # Log data shape and type
            logger.info("Data shape: %s, dtype: %s", data.shape, data.dtype)

            # Check for fill values or NaNs
            if np.isnan(data).any():
                logger.info("Data contains NaN values: %s", np.isnan(data).sum())

            # Extract metadata if available
            metadata = {}
            for attr in [
                "band_id",
                "band_wavelength",
                "instrument_type",
                "platform_ID",
            ]:
                if attr in ds.attrs:
                    metadata[attr] = ds.attrs[attr]

            logger.info("Extracted metadata: %s", metadata)

            return data
        raise ValueError(f"Variable '{channel_var}' not found in dataset")


def process_and_save_image(
    data: np.ndarray,
    output_path: Path,
    colormap: str = "gray",
    invert: bool = True,
    min_val: float = None,
    max_val: float = None,
    scale_factor: float = 0.25,
) -> Path:
    """
    Process channel data and save as an image.

    Args:
        data: NumPy array with channel data
        output_path: Path to save the image
        colormap: Matplotlib colormap name
        invert: Whether to invert the data (typical for IR bands)
        min_val: Minimum value for normalization (default: data.min())
        max_val: Maximum value for normalization (default: data.max())
        scale_factor: Scale factor for resizing the image (default: 0.25 = 25%)

    Returns:
        Path to the saved image
    """
    logger.info("Processing and saving image to %s", output_path)

    # Set min/max values if not provided
    if min_val is None:
        min_val = np.nanmin(data)
    if max_val is None:
        max_val = np.nanmax(data)

    logger.info("Data range: %s to %s", min_val, max_val)

    # Clip data to the specified range
    data_clipped = np.clip(data, min_val, max_val)

    # Normalize to 0-1 range
    data_norm = (data_clipped - min_val) / (max_val - min_val)

    # Invert if requested (common for IR bands where cold = bright)
    if invert:
        data_norm = 1 - data_norm

    # Downsample the data to make the images smaller
    # Use simple stride-based downsampling for speed
    if scale_factor < 1.0:
        stride = int(1 / scale_factor)
        data_small = data_norm[::stride, ::stride]
        logger.info("Downsampled data from %s to %s", data_norm.shape, data_small.shape)
    else:
        data_small = data_norm

    # Create a figure with appropriate size
    dpi = 100
    fig_width = data_small.shape[1] / dpi
    fig_height = data_small.shape[0] / dpi

    fig = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    # Apply colormap
    cmap = plt.get_cmap(colormap)

    # Plot the image
    ax.imshow(data_small, cmap=cmap, aspect="auto")

    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0)
    plt.close(fig)

    logger.info("Image saved: %s", output_path)
    return output_path


def explore_netcdf_structure(netcdf_path: Path) -> dict:
    """
    Explore the structure of a NetCDF file and return detailed information.

    Args:
        netcdf_path: Path to the NetCDF file

    Returns:
        Dictionary with information about the file structure
    """
    logger.info("Exploring NetCDF structure: %s", netcdf_path)

    try:
        with xr.open_dataset(netcdf_path) as ds:
            # Get global attributes
            global_attrs = dict(ds.attrs)

            # Get variables and their attributes
            variables = {}
            for var_name, var in ds.variables.items():
                var_info = {
                    "shape": var.shape,
                    "dtype": str(var.dtype),
                    "attrs": dict(var.attrs),
                    "dims": var.dims,
                }

                # Add sample data if variable is small
                if np.prod(var.shape) < 100:  # Only for small variables
                    var_info["data"] = var.values.tolist()

                variables[var_name] = var_info

            # Get dimensions
            dimensions = {dim: ds.dims[dim] for dim in ds.dims}

            return {
                "global_attributes": global_attrs,
                "variables": variables,
                "dimensions": dimensions,
                "file_size": netcdf_path.stat().st_size,
            }
    except Exception as e:
        logger.error("Error exploring NetCDF structure: %s", e)
        return {"error": str(e)}


def detect_channel_from_filename(filename: str) -> int:
    """
    Extract the channel number from an ABI filename.

    Args:
        filename: Filename to parse

    Returns:
        Channel number as integer
    """
    # Look for pattern like C01, C02, etc. in the filename
    import re

    match = re.search(r"C(\d{2})", filename)
    if match:
        return int(match.group(1))
    return None


def process_channel_data(ds, channel_num, temp_dir):
    """
    Process data for a specific channel from a NetCDF dataset.

    Args:
        ds: xarray Dataset containing the NetCDF data
        channel_num: Channel number (1-16)
        temp_dir: Directory to save output files

    Returns:
        Dictionary with processing results
    """
    output_dir = Path(temp_dir) / "output"
    output_dir.mkdir(exist_ok=True)

    # Determine channel type (visible or IR)
    is_ir_channel = 7 <= channel_num <= 16
    is_visible_channel = 1 <= channel_num <= 6

    # Get appropriate variable (Rad, CMI, etc.)
    var_name = "Rad"  # Default

    if var_name in ds.variables:
        # Extract data
        data = ds[var_name].values

        # Handle different channel types
        if is_visible_channel:
            # For visible channels, direct rendering
            colormap = "viridis"
            invert = False
            min_val = np.nanmin(data)
            max_val = np.nanmax(data)
        elif is_ir_channel:
            # For IR channels, convert to brightness temperature if needed
            colormap = "inferno"
            invert = True  # IR channels are typically inverted (cold=bright)

            # Convert radiance to brightness temperature if coefficients exist
            if all(
                k in ds.attrs
                for k in ["planck_fk1", "planck_fk2", "planck_bc1", "planck_bc2"]
            ):
                fk1 = ds.attrs["planck_fk1"]
                fk2 = ds.attrs["planck_fk2"]
                bc1 = ds.attrs["planck_bc1"]
                bc2 = ds.attrs["planck_bc2"]

                # Apply Planck function for brightness temperature
                temp_data = (
                    fk2 / np.log((fk1 / np.maximum(data, 0.0001)) + 1) - bc1
                ) / bc2

                # Use temperature for IR channels, with appropriate range
                data = temp_data
                min_val = 180.0  # K (very cold)
                max_val = 320.0  # K (warm)
            else:
                # If no coefficients, just use the raw data
                min_val = np.nanmin(data)
                max_val = np.nanmax(data)
        else:
            # Default for unknown channel types
            colormap = "viridis"
            invert = False
            min_val = np.nanmin(data)
            max_val = np.nanmax(data)

        # Process and save the image
        output_path = output_dir / f"channel_{channel_num:02d}_{var_name.lower()}.png"

        # Use robust min/max to handle outliers
        robust_min = np.nanpercentile(data, 1)
        robust_max = np.nanpercentile(data, 99)

        logger.info(
            f"Channel {channel_num}: Min={min_val}, Max={max_val}, Robust Min={robust_min}, Robust Max={robust_max}"
        )

        # Process with both regular and robust ranges
        process_and_save_image(
            data,
            output_path,
            colormap=colormap,
            invert=invert,
            min_val=min_val,
            max_val=max_val,
        )

        # Also save with robust range
        robust_output_path = (
            output_dir / f"channel_{channel_num:02d}_{var_name.lower()}_robust.png"
        )
        process_and_save_image(
            data,
            robust_output_path,
            colormap=colormap,
            invert=invert,
            min_val=robust_min,
            max_val=robust_max,
        )

        # Create a side-by-side comparison view - using matplotlib which handles large images better
        comparison_path = output_dir / f"channel_{channel_num:02d}_comparison.png"
        try:
            # Create a figure for the comparison
            plt.figure(figsize=(16, 8))

            # Create two subplots
            plt.subplot(1, 2, 1)
            plt.title("Full Range")
            plt.imshow(plt.imread(str(output_path)))
            plt.axis("off")

            plt.subplot(1, 2, 2)
            plt.title("Robust Range (1-99%)")
            plt.imshow(plt.imread(str(robust_output_path)))
            plt.axis("off")

            # Add a main title
            plt.suptitle(
                f"Channel {channel_num} - Comparison of Dynamic Ranges", fontsize=16
            )

            # Save with tight layout
            plt.tight_layout()
            plt.savefig(comparison_path)
            plt.close()

            logger.info("Comparison saved to %s", comparison_path)
        except Exception as e:
            logger.error("Error creating comparison image: %s", e)

        return {
            "channel": channel_num,
            "variable": var_name,
            "shape": data.shape,
            "min_val": float(min_val),
            "max_val": float(max_val),
            "robust_min": float(robust_min),
            "robust_max": float(robust_max),
            "output_path": str(output_path),
            "robust_output_path": str(robust_output_path),
            "comparison_path": (
                str(comparison_path) if "comparison_path" in locals() else None
            ),
        }
    else:
        return {
            "channel": channel_num,
            "error": f"Variable '{var_name}' not found in dataset",
        }


def test_download_and_process_channels():
    """
    Test downloading NetCDF files for different channels and processing them.

    This test downloads files for multiple channels and processes them to verify
    we can target individual channels.
    """
    # Base parameters
    bucket = "noaa-goes18"

    # Test different channels
    # We'll use a search approach to find available files rather than specifying exact paths
    # This is more flexible as the exact filenames might change

    # Function to find a file for a specific channel
    def find_channel_file(bucket, prefix, channel_num):
        # Use a more general prefix and then filter by channel
        general_prefix = "ABI-L1b-RadF/2024/362/00/"

        try:
            # Search for files with this channel pattern
            channel_pattern = f"C{channel_num:02d}"

            # List objects with prefix
            response = s3_client.list_objects_v2(
                Bucket=bucket, Prefix=general_prefix, MaxKeys=100
            )

            # Check for matching files
            if "Contents" in response:
                # Filter for files containing the channel pattern
                matching_files = [
                    obj["Key"]
                    for obj in response["Contents"]
                    if channel_pattern in obj["Key"]
                ]

                # Sort to get the latest file (if multiple)
                if matching_files:
                    matching_files.sort()
                    return matching_files[0]

            logger.warning(
                f"No files found for channel {channel_num} in {general_prefix}"
            )
            return None

        except Exception as e:
            logger.error("Error searching for channel %s file: %s", channel_num, e)
            return None

    # Try to find files for different channels
    channel_nums = [1, 2, 13]  # Channels we want to test
    channel_tests = []

    for channel_num in channel_nums:
        file_key = find_channel_file(bucket, "ABI-L1b-RadF/2024/362/00/", channel_num)
        if file_key:
            channel_tests.append((file_key, channel_num))
            logger.info("Found file for channel %s: %s", channel_num, file_key)
        else:
            logger.warning(
                f"Could not find file for channel {channel_num}, will be skipped"
            )

    # If we couldn't find any files, use the known channel 1 file as fallback
    if not channel_tests:
        logger.warning("Falling back to known Channel 1 file")
        channel_tests = [
            (
                "ABI-L1b-RadF/2024/362/00/OR_ABI-L1b-RadF-M6C01_G18_s20243620000208_e20243620009516_c20243620009561.nc",
                1,
            )
        ]

    # Create a temporary directory for test files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        permanent_output = Path(__file__).parent / "test_output"
        permanent_output.mkdir(exist_ok=True)

        # Dictionary to store results for each channel
        channel_results = {}

        # Download and process each file
        for file_key, expected_channel in channel_tests:
            try:
                # Create a unique filename based on the channel
                channel_num = detect_channel_from_filename(file_key)
                if channel_num is None:
                    channel_num = expected_channel

                netcdf_path = temp_path / f"channel_{channel_num:02d}.nc"

                # Step 1: Download the NetCDF file
                logger.info(
                    "Downloading file for channel %s: %s", channel_num, file_key
                )
                try:
                    download_file_from_s3(bucket, file_key, netcdf_path)
                except Exception as e:
                    logger.error("Failed to download %s: %s", file_key, e)
                    continue

                # Step 2: Explore the NetCDF structure
                logger.info("Analyzing NetCDF structure for channel %s", channel_num)
                explore_netcdf_structure(netcdf_path)

                # Check if this file has the band_id attribute to confirm channel
                with xr.open_dataset(netcdf_path) as ds:
                    if "band_id" in ds.variables:
                        actual_channel = ds["band_id"].values.item()
                        logger.info("File reports band_id = %s", actual_channel)

                        # Double-check against expected channel
                        if actual_channel != expected_channel:
                            logger.warning(
                                f"Expected channel {expected_channel} but found {actual_channel}"
                            )

                    # Step 3: Process the channel data
                    logger.info("Processing data for channel %s", channel_num)
                    result = process_channel_data(ds, channel_num, temp_path)
                    channel_results[channel_num] = result

                # Save the visualizations to the permanent output directory
                output_dir = Path(temp_dir) / "output"
                for img_path in output_dir.glob(f"channel_{channel_num:02d}*.*"):
                    # Copy the file
                    dest_path = permanent_output / img_path.name
                    try:
                        # We'll use matplotlib which can read and resize large images
                        plt.figure(figsize=(12, 12))
                        img_data = plt.imread(str(img_path))
                        plt.imshow(img_data)
                        plt.axis("off")
                        plt.tight_layout(pad=0)
                        plt.savefig(dest_path)
                        plt.close()
                        logger.info("Saved %s", dest_path)
                    except Exception as e:
                        logger.error("Error saving %s: %s", img_path, e)

            except Exception as e:
                logger.exception("Error processing channel %s: %s", expected_channel, e)
                channel_results[expected_channel] = {"error": str(e)}

        # Save a summary report
        summary_path = permanent_output / "channel_processing_summary.txt"
        with open(summary_path, "w") as f:
            f.write("# GOES Channel Processing Summary\n\n")

            for channel, result in sorted(channel_results.items()):
                f.write(f"## Channel {channel}\n\n")

                if "error" in result:
                    f.write(f"Error: {result['error']}\n\n")
                else:
                    f.write(f"- Variable: {result['variable']}\n")
                    f.write(f"- Data shape: {result['shape']}\n")
                    f.write(
                        f"- Value range: {result['min_val']} to {result['max_val']}\n"
                    )
                    f.write(
                        f"- Robust range (1-99%): {result['robust_min']} to {result['robust_max']}\n"
                    )
                    f.write("- Output files:\n")
                    f.write(f"  - Full range: {Path(result['output_path']).name}\n")
                    f.write(
                        f"  - Robust range: {Path(result['robust_output_path']).name}\n"
                    )
                    if result["comparison_path"]:
                        f.write(
                            f"  - Comparison: {Path(result['comparison_path']).name}\n"
                        )
                    f.write("\n")

        logger.info("Summary saved to %s", summary_path)
        return True


if __name__ == "__main__":
    logger.info("Starting NetCDF channel extraction test")
    success = test_download_and_process_channels()

    if success:
        logger.info("Test completed successfully!")
        sys.exit(0)
    else:
        logger.error("Test failed!")
        sys.exit(1)
