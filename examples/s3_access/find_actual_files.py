#!/usr/bin/env python3
"""
Find actual files available in the target hour.
This script examines the exact structure and minute directories.
"""
import os
from pathlib import Path

import boto3
import numpy as np
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config
from PIL import Image

# Configure boto3 for anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us - east - 1")

s3 = boto3.client("s3", config=s3_config)

# Target date and hour
TEST_DATE = "2023 / 121"
TEST_HOUR = "19" # 19:00 UTC (noon Pacific)

# Product types to check
PRODUCT_TYPES = [
"ABI - L2 - CMIPF", # Full Disk
"ABI - L2 - CMIPC", # CONUS
"ABI - L2 - CMIPM", # Mesoscale
]

# Band to check
BAND = 13 # IR band

# Download directory
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads / goes_noontime"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR = DOWNLOAD_DIR / "images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def find_band_files(bucket, product, date, hour, band):
    pass
"""Find files for a specific band directly in the hour directory."""
prefix = f"{product}/{date}/{hour}/"
print(f"Looking for Band {band} files in {bucket}/{prefix}...")

# List all objects with this prefix
paginator = s3.get_paginator("list_objects_v2")
pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

# Filter for the specific band
band_str = f"C{band:02d}"
band_files = []

for page in pages:
     if "Contents" not in page:
         pass
     pass
continue

for obj in page["Contents"]:
     key = obj["Key"]
if band_str in key and key.endswith(".nc"):
     pass
band_files.append(key)

print(f" Found {len(band_files)} Band {band} files")
return band_files


def download_and_process(bucket, key, product_type):
    """Download and process a file to create an IR image."""
# Create output path
product = product_type.split("-")[-1] # CMIPF, CMIPC, CMIPM
file_name = os.path.basename(key)

# Extract timestamp from filename
timestamp = ""
if "_s" in file_name:
     pass
timestamp = file_name.split("_s")[1].split("_")[0]

nc_path = DOWNLOAD_DIR / f"{product}_{timestamp}_{file_name}"
img_path = IMAGE_DIR / f"{product}_{timestamp}_IR.png"

# Download the file
print(f" Downloading {key} to {nc_path}...")
try:
     s3.download_file(bucket, key, str(nc_path))

# Process the file
print(" Processing file to create IR image...")
process_ir_image(nc_path, img_path)

return True
except Exception as e:
     pass
print(f" Error: {e}")
return False


def process_ir_image(file_path, output_path):
    """Process IR image from a CMIP file."""
try:
     with xr.open_dataset(file_path) as ds:
     # Extract the CMI data
ir_data = ds["CMI"].values

# Normalize brightness temperature to 0 - 255 range
min_temp = np.nanmin(ir_data)
max_temp = np.nanmax(ir_data)

# If temperature values, use reasonable defaults for GOES IR
if min_temp > 150 and max_temp < 350:
     pass
print(f" Temperature range: {min_temp:.1f}K - {max_temp:.1f}K")
# Invert so cold (high) clouds are white
ir_norm = 1.0 - ((ir_data - 180) / (320 - 180))
ir_norm = np.clip(ir_norm, 0, 1)
else:
     # If reflectance values (0 - 1), keep as is
print(f" Value range: {min_temp:.3f} - {max_temp:.3f}")
ir_norm = ir_data

# Scale to 0 - 255
ir_uint8 = (ir_norm * 255).astype(np.uint8)

# Replace NaN values with 0
ir_uint8 = np.nan_to_num(ir_uint8, nan=0).astype(np.uint8)

# Save as grayscale image
Image.fromarray(ir_uint8, "L").save(output_path)
print(f" Saved IR image to {output_path}")

return True
except Exception as e:
     pass
print(f"Error processing IR image: {e}")
return False


def main():
    """Main function to find and download files from noon Pacific time."""
bucket = "noaa - goes16"

print(
f"Checking {bucket} for data at noon Pacific time ({TEST_DATE} {TEST_HOUR}:xx UTC)"
)
print("-" * 70)

for product in PRODUCT_TYPES:
     print(f"\nProduct: {product}")

# Find Band 13 files directly in the hour directory
band_files = find_band_files(bucket, product, TEST_DATE, TEST_HOUR, BAND)

if not band_files:
     pass
print(f" No Band {BAND} files found for {product}")
continue

# Download and process the first file (noon Pacific)
# We'll take the closest file to noon Pacific which is around the 19:00 mark
target_time = "1900" # 19:00 UTC

# Sort files by how close they are to our target time
sorted_files = sorted(
band_files,
key=lambda x: abs(
int(x.split("s")[1].split("_")[0][8:12]) - int(target_time)
),
)

first_file = sorted_files[0]
print(f" Selected file: {os.path.basename(first_file)}")

success = download_and_process(bucket, first_file, product)

if success:
     pass
print(" Successfully downloaded and processed file")
else:
     print(" Failed to download and process file")

print("\nCompleted. Files downloaded to:")
print(f" NetCDF files: {DOWNLOAD_DIR}")
print(f" Images: {IMAGE_DIR}")


if __name__ == "__main__":
    pass
main()
