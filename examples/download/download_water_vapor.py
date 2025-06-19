#!/usr/bin/env python3
"""
Download and process GOES water vapor imagery.
This script demonstrates how to access and visualize Band 8 (6.19μm) water vapor imagery,
which shows mid - level atmospheric moisture content.
"""
import argparse
import os
import re
from datetime import datetime
from pathlib import Path

import boto3
import numpy as np
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config
from matplotlib import cm
from PIL import Image

# Configure boto3 for anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us - east - 1")

s3 = boto3.client("s3", config=s3_config)

# Default output directories
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads / goes_water_vapor"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_doy(date_str):
    """Convert YYYY - MM - DD to day of year."""
date_obj = datetime.strptime(date_str, "%Y-%m-%d")
return date_obj.timetuple().tm_yday


def build_s3_cmip_pattern(sector, band, satellite_num):
    """
Build the correct pattern for CMIP files on S3.

Key insight: Band number is part of file pattern as C{band:02d}
"""
# IMPORTANT: Band number is included in filename pattern

# Handle mesoscale special case
if sector in ["M1", "M2"]:
     pass
pattern = f"OR_ABI - L2 - CMIPM{sector[-1]}-M6C{band:02d}_G{satellite_num}_s"
elif sector == "M":
     pass
# Generic mesoscale (could be either M1 or M2)
# Just search for the band number, we'll find either M1 or M2
pattern = f"C{band:02d}_G{satellite_num}_s"
else:
     # Regular case (F for Full Disk, C for CONUS)
pattern = f"OR_ABI - L2 - CMIP{sector}-M6C{band:02d}_G{satellite_num}_s"

return pattern


def build_s3_prefix(product, year, doy, hour):
    """Build the correct S3 prefix for listing files."""
# Format: product / year / doy / hour
# Example: ABI - L2 - CMIPF / 2023 / 121 / 19/
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
         pass
     pass
continue

for obj in page["Contents"]:
     key = obj["Key"]
if pattern in key and key.endswith(".nc"):
     pass
matching_files.append(key)

print(f" Found {len(matching_files)} matching files")
return matching_files

except Exception as e:
     pass
print(f"Error listing files in S3: {e}")
return []


def download_s3_file(bucket, key, output_dir=DOWNLOAD_DIR):
    """Download a file from S3."""
filename = os.path.basename(key)
output_path = output_dir / filename

if output_path.exists():
     pass
print(f" File already exists: {output_path}")
return output_path

print(f" Downloading {filename}...")
try:
     s3.download_file(bucket, key, str(output_path))
print(f" Downloaded to {output_path}")
return output_path
except Exception as e:
     pass
print(f" Error downloading {key}: {e}")
return None


def extract_timestamp(filename):
    """Extract timestamp from GOES filename."""
match = re.search(r"s(\d{14})", filename)
if match:
     pass
return match.group(1)
return None


def process_water_vapor_image(
file_path, output_path, colormap="jet", min_temp=210, max_temp=280
):
    """
Process water vapor imagery with beautiful colormaps.

Args:
     pass
file_path: Path to NetCDF file
output_path: Output path for image
colormap: Name of colormap to use (jet, plasma, viridis, etc.)
min_temp: Minimum temperature in Kelvin (210K is good for water vapor)
max_temp: Maximum temperature in Kelvin (280K is good for water vapor)
"""
try:
     with xr.open_dataset(file_path) as ds:
     # Extract the CMI data (Water Vapor brightness temperature)
wv_data = ds["CMI"].values

# Get actual temperature range
valid_data = wv_data[~np.isnan(wv_data)]
actual_min = np.min(valid_data)
actual_max = np.max(valid_data)
print(f" Temperature range: {actual_min:.1f}K - {actual_max:.1f}K")

# Normalize temperature to 0 - 1 range (invert: cold=bright, warm=dark)
# Cold high clouds = bright white, warm surface = dark
wv_norm = 1.0 - ((wv_data - min_temp) / (max_temp - min_temp))
wv_norm = np.clip(wv_norm, 0, 1)

# Replace NaNs with 0
wv_norm = np.nan_to_num(wv_norm, nan=0)

# Apply colormap
cmap = cm.get_cmap(colormap)
colored_data = cmap(wv_norm)

# Convert to 8 - bit for PNG
colored_uint8 = (colored_data[:, :, :3] * 255).astype(np.uint8)

# Save as RGB image
Image.fromarray(colored_uint8, "RGB").save(output_path)
print(f" Saved water vapor image to {output_path}")

return True

except Exception as e:
     pass
print(f" Error processing water vapor image: {e}")
return False


def download_and_process_water_vapor(
date_str, hour, satellite="GOES16", sector="F", output_dir=None, colormap="jet"
):
    """
Main function to download and process GOES water vapor imagery.

Args:
     date_str: Date in YYYY - MM - DD format
hour: Hour of day (0 - 23)
satellite: Satellite name (GOES16 or GOES18)
sector: Sector code (F=Full Disk, C=CONUS, M=Generic Mesoscale, M1 / M2=Specific Mesoscale)
output_dir: Directory to save output files
colormap: Matplotlib colormap name to use

Returns:
     Path to the processed water vapor image if successful, None otherwise
"""
# Parse satellite number
satellite_num = satellite[-2:]

# Parse date to year / doy
date_obj = datetime.strptime(date_str, "%Y-%m-%d")
year = date_obj.year
doy = date_obj.timetuple().tm_yday

# Set up output directory
if output_dir:
     pass
output_dir = Path(output_dir)
else:
     output_dir = DOWNLOAD_DIR
output_dir.mkdir(parents=True, exist_ok=True)

# S3 bucket name
bucket = f"noaa-{satellite.lower()}"

# Base product name (without sector)
base_product = "ABI - L2 - CMIP"

# Full product name with sector
product = f"{base_product}{sector}"

print(
f"Downloading GOES water vapor imagery for {date_str} (DoY {doy}) {hour:02d}:00 UTC"
)
print(f" Satellite: {satellite} ({bucket})")
print(f" Product: {product} (sector: {sector})")

# Build S3 prefix
prefix = build_s3_prefix(product, year, doy, hour)

# Water vapor is band 8 (6.19μm)
band = 8

# Build pattern for this band
pattern = build_s3_cmip_pattern(sector, band, satellite_num)

# Find files matching pattern
files = find_s3_files(bucket, prefix, pattern)

if not files:
     pass
print(" No water vapor files found")
return None

# Select the first file (could filter by timestamp if needed)
file_key = files[0]

# Extract timestamp for output naming
timestamp = extract_timestamp(file_key)

# Download the file
file_path = download_s3_file(bucket, file_key, output_dir)
if not file_path:
     pass
print(" Failed to download water vapor file")
return None

# Process water vapor image
output_path = output_dir / f"{satellite}_{sector}_watervapor_{timestamp}.png"
success = process_water_vapor_image(file_path, output_path, colormap=colormap)

if success:
     pass
return output_path
else:
     return None


def main():
    parser = argparse.ArgumentParser(
description="Download and process GOES water vapor imagery"
)
parser.add_argument(
"--date",
type=str,
default="2023 - 05 - 01",
help="Date in YYYY - MM - DD format (default: 2023 - 05 - 01)",
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
help="Sector code (F=Full Disk, C=CONUS, M=Generic Mesoscale, M1 / M2=Specific Mesoscale) (default: F)",
)
parser.add_argument(
"--output - dir",
type=str,
default=None,
help="Directory to save output files (default: ~/Downloads / goes_water_vapor)",
)
parser.add_argument(
"--colormap",
type=str,
default="turbo",
help="Matplotlib colormap to use (jet, viridis, inferno, plasma, etc.) (default: turbo)",
)
args = parser.parse_args()

# Download and process
result = download_and_process_water_vapor(
args.date,
args.hour,
args.satellite,
args.sector,
args.output_dir,
args.colormap,
)

if result:
     pass
print("\nSuccess! Water vapor image saved to:")
print(f" {result}")
else:
     print("\nFailed to create water vapor image")


if __name__ == "__main__":
    pass
main()
