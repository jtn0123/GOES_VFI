#!/usr/bin/env python3
"""
Discover and analyze all available GOES ABI channels/bands.
This script checks for the availability of all 16 ABI bands and provides details on each.
"""
import argparse
import os
from datetime import datetime
from pathlib import Path

import boto3
import numpy as np
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config
from tabulate import tabulate

# Configure boto3 for anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)

# Default output directories
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_channels"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ABI band information
ABI_BANDS = {
    1: {
        "name": "Blue",
        "wavelength": "0.47 μm",
        "type": "Visible",
        "resolution": "1 km",
        "primary_use": "Daytime aerosol detection, smoke, haze",
    },
    2: {
        "name": "Red",
        "wavelength": "0.64 μm",
        "type": "Visible",
        "resolution": "0.5 km",
        "primary_use": "Daytime cloud and surface features",
    },
    3: {
        "name": "Veggie",
        "wavelength": "0.86 μm",
        "type": "Near-IR",
        "resolution": "1 km",
        "primary_use": "Daytime vegetation, burn scars, aerosol",
    },
    4: {
        "name": "Cirrus",
        "wavelength": "1.37 μm",
        "type": "Near-IR",
        "resolution": "2 km",
        "primary_use": "Daytime cirrus cloud detection",
    },
    5: {
        "name": "Snow/Ice",
        "wavelength": "1.6 μm",
        "type": "Near-IR",
        "resolution": "2 km",
        "primary_use": "Daytime cloud phase, snow detection",
    },
    6: {
        "name": "Cloud Particle",
        "wavelength": "2.2 μm",
        "type": "Near-IR",
        "resolution": "2 km",
        "primary_use": "Daytime land/cloud properties, particle size",
    },
    7: {
        "name": "Shortwave Window",
        "wavelength": "3.9 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "Fire detection, night fog, winds",
    },
    8: {
        "name": "Upper-Level Water Vapor",
        "wavelength": "6.2 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "High-level atmospheric water vapor, winds",
    },
    9: {
        "name": "Mid-Level Water Vapor",
        "wavelength": "6.9 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "Mid-level atmospheric water vapor, winds",
    },
    10: {
        "name": "Lower-level Water Vapor",
        "wavelength": "7.3 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "Lower-level water vapor, winds",
    },
    11: {
        "name": "Cloud-Top Phase",
        "wavelength": "8.4 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "Total water, cloud phase, dust",
    },
    12: {
        "name": "Ozone",
        "wavelength": "9.6 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "Ozone detection, turbulence",
    },
    13: {
        "name": "Clean IR Longwave",
        "wavelength": "10.3 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "Surface and cloud features, cloud top",
    },
    14: {
        "name": "IR Longwave",
        "wavelength": "11.2 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "Clouds, nighttime fog, volcanic ash",
    },
    15: {
        "name": "Dirty IR Longwave",
        "wavelength": "12.3 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "Volcanic ash, dust, sea surface temperature",
    },
    16: {
        "name": "CO2 IR Longwave",
        "wavelength": "13.3 μm",
        "type": "IR",
        "resolution": "2 km",
        "primary_use": "Air temperature, cloud heights",
    },
}


def build_s3_cmip_pattern(sector, band, satellite_num):
    """Build the correct pattern for CMIP files on S3."""
    if sector in ["M1", "M2"]:
        pattern = f"OR_ABI-L2-CMIPM{sector[-1]}-M6C{band:02d}_G{satellite_num}_s"
    elif sector == "M":
        pattern = f"C{band:02d}_G{satellite_num}_s"
    else:
        pattern = f"OR_ABI-L2-CMIP{sector}-M6C{band:02d}_G{satellite_num}_s"
    return pattern


def build_s3_prefix(product, year, doy, hour):
    """Build the correct S3 prefix for listing files."""
    return f"{product}/{year}/{doy:03d}/{hour:02d}/"


def find_s3_files(bucket, prefix, pattern):
    """Find files in S3 bucket matching pattern."""
    print(f"Looking for files matching: {pattern}")

    matching_files = []

    try:
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                if pattern in key and key.endswith(".nc"):
                    matching_files.append(key)

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


def analyze_channel_content(file_path, band_num):
    """Analyze the content of a channel file."""
    result = {"band": band_num}
    result.update(ABI_BANDS[band_num])

    try:
        with xr.open_dataset(file_path) as ds:
            # Get basic stats for this band
            data = ds["CMI"].values
            valid_data = data[~np.isnan(data)]

            result["min_value"] = float(np.min(valid_data))
            result["max_value"] = float(np.max(valid_data))
            result["mean_value"] = float(np.mean(valid_data))
            result["shape"] = data.shape

            # Extract more specific metadata if available
            if "wavelength" in ds.variables:
                result["actual_wavelength"] = float(ds.wavelength)

            if "band_id" in ds.variables:
                result["band_id"] = int(ds.band_id)

            if "esun" in ds.variables:
                result["esun"] = float(ds.esun)

            if "kappa0" in ds.variables:
                result["kappa0"] = float(ds.kappa0)

            # Determine if this is a reflectance or brightness temperature product
            # Usually bands 1-6 are reflectance, 7-16 are brightness temperature
            if band_num <= 6:
                result["value_type"] = "Reflectance"
                result["units"] = "unitless"
            else:
                result["value_type"] = "Brightness Temperature"
                result["units"] = "Kelvin"

            # Add file name
            result["filename"] = os.path.basename(file_path)

            return result
    except Exception as e:
        print(f"  Error analyzing Band {band_num}: {e}")
        result["error"] = str(e)
        return result


def discover_available_channels(date_str, hour, satellite="GOES16", sector="F"):
    """Find and analyze all available ABI channels for the given parameters."""
    # Parse satellite number
    satellite_num = satellite[-2:]

    # Parse date to year/doy
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    year = date_obj.year
    doy = date_obj.timetuple().tm_yday

    # S3 bucket name
    bucket = f"noaa-{satellite.lower()}"

    # Base product name
    base_product = "ABI-L2-CMIP"

    # Full product name with sector
    product = f"{base_product}{sector}"

    print(f"Discovering available GOES ABI channels for:")
    print(f"  Date: {date_str} (DoY {doy})")
    print(f"  Hour: {hour:02d}:00 UTC")
    print(f"  Satellite: {satellite} ({bucket})")
    print(f"  Product: {product} (sector: {sector})")

    # Build S3 prefix
    prefix = build_s3_prefix(product, year, doy, hour)

    # Check all 16 ABI bands
    available_channels = []
    downloaded_files = []

    # First, find all available channels
    for band in range(1, 17):
        pattern = build_s3_cmip_pattern(sector, band, satellite_num)
        files = find_s3_files(bucket, prefix, pattern)

        if files:
            print(
                f"  Band {band} ({ABI_BANDS[band]['name']}): {len(files)} files available"
            )
            available_channels.append(band)

            # Download one file for each band for analysis
            file_path = download_s3_file(bucket, files[0])
            if file_path:
                downloaded_files.append((band, file_path))

    # Analyze the downloaded files
    channel_data = []
    for band, file_path in downloaded_files:
        info = analyze_channel_content(file_path, band)
        channel_data.append(info)

    return channel_data


def print_channel_info(channel_data):
    """Print detailed information about all discovered channels."""
    # Basic table with most important info
    basic_table = []
    for ch in sorted(channel_data, key=lambda x: x["band"]):
        if "error" in ch:
            basic_table.append(
                [
                    ch["band"],
                    ch["name"],
                    ch["wavelength"],
                    ch["type"],
                    "ERROR: " + ch["error"],
                ]
            )
        else:
            value_range = (
                f"{ch.get('min_value', 'N/A'):.3f} - {ch.get('max_value', 'N/A'):.3f}"
            )
            if ch.get("value_type") == "Brightness Temperature":
                value_range += " K"
            basic_table.append(
                [
                    ch["band"],
                    ch["name"],
                    ch["wavelength"],
                    ch["type"],
                    ch.get("value_type", "Unknown"),
                    value_range,
                    f"{ch.get('shape', (0, 0))[0]} x {ch.get('shape', (0, 0))[1]}",
                    ch["primary_use"],
                ]
            )

    print("\n=== GOES ABI CHANNELS INFORMATION ===")
    print(
        tabulate(
            basic_table,
            headers=[
                "Band",
                "Name",
                "Wavelength",
                "Type",
                "Value Type",
                "Value Range",
                "Resolution",
                "Primary Use",
            ],
            tablefmt="grid",
        )
    )

    # Detailed information for each channel
    print("\n=== DETAILED CHANNEL INFORMATION ===")
    for ch in sorted(channel_data, key=lambda x: x["band"]):
        print(f"\nBand {ch['band']}: {ch['name']} ({ch['wavelength']})")
        print(f"  Type: {ch['type']}")
        print(f"  Primary use: {ch['primary_use']}")
        if "error" in ch:
            print(f"  ERROR: {ch['error']}")
            continue

        print(f"  File: {ch.get('filename', 'Unknown')}")
        print(f"  Shape: {ch.get('shape', 'Unknown')}")
        print(
            f"  Value type: {ch.get('value_type', 'Unknown')} ({ch.get('units', 'Unknown')})"
        )
        print(
            f"  Value range: {ch.get('min_value', 'N/A'):.3f} - {ch.get('max_value', 'N/A'):.3f} (mean: {ch.get('mean_value', 'N/A'):.3f})"
        )

        if "actual_wavelength" in ch:
            print(f"  Actual wavelength: {ch['actual_wavelength']}")
        if "esun" in ch:
            print(f"  Solar irradiance (ESUN): {ch['esun']}")
        if "kappa0" in ch:
            print(f"  Kappa0: {ch['kappa0']}")


def main():
    parser = argparse.ArgumentParser(
        description="Discover and analyze available GOES ABI channels"
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
        choices=["F", "C", "M", "M1", "M2"],
        default="F",
        help="Sector code (F=Full Disk, C=CONUS, M=Generic Mesoscale, M1/M2=Specific Mesoscale) (default: F)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save downloaded files (default: ~/Downloads/goes_channels)",
    )
    args = parser.parse_args()

    # Set output directory if specified
    if args.output_dir:
        global DOWNLOAD_DIR
        DOWNLOAD_DIR = Path(args.output_dir)
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Discover and analyze channels
    channel_data = discover_available_channels(
        args.date, args.hour, args.satellite, args.sector
    )

    # Print channel information
    print_channel_info(channel_data)

    print(f"\nDiscovered {len(channel_data)} of 16 possible ABI channels")
    print(f"Channel details saved to files in: {DOWNLOAD_DIR}")


if __name__ == "__main__":
    main()
