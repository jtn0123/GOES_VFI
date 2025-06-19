#!/usr/bin/env python3
"""
Improved GOES imagery processor that correctly handles:
    1. Single - band CMIP files for IR and individual bands
2. Multi - channel MCMIP files for pre - processed true color
3. CDN access for quick - look JPEGs
4. Proper band naming and wildcard patterns

This provides multiple pathways to obtain the imagery, with fallbacks.
"""
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import numpy as np
import requests
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config
from PIL import Image

# Standard temperature ranges for IR bands
TEMP_RANGES = {
    7: (200, 380),  # Fire detection
    8: (190, 258),  # Upper-level water vapor
    9: (190, 265),  # Mid-level water vapor
    10: (190, 280),  # Lower-level water vapor
    11: (190, 320),  # Cloud-top phase
    12: (210, 290),  # Ozone
    13: (190, 330),  # Clean IR longwave
    14: (190, 330),  # IR longwave
    15: (190, 320),  # Dirty IR longwave
    16: (190, 295),  # CO2 longwave
}

# Check if arrays have the same shape
shapes = [data.shape for data in band_data]
if len(set(shapes)) > 1:
     pass
print(f" Bands have different shapes: {shapes}")
print(" Resizing to match smallest dimensions...")

# Find the smallest dimensions
min_height = min(shape[0] for shape in shapes)
min_width = min(shape[1] for shape in shapes)

# Resize all bands to the smallest shape
resized_bands = []
for i, data in enumerate(band_data):
     if data.shape[0] == min_height and data.shape[1] == min_width:
         pass
     pass
resized_bands.append(data)
else:
     # Use PIL for resizing
img = Image.fromarray((data * 255).astype(np.uint8))
resized = img.resize((min_width, min_height), Image.LANCZOS)
resized_bands.append(np.array(resized) / 255.0)

band_data = resized_bands

# Apply gamma correction for more natural appearance
gamma = 2.2
r = np.power(np.clip(band_data[0], 0, 1), 1 / gamma)
g = np.power(np.clip(band_data[1], 0, 1), 1 / gamma)
b = np.power(np.clip(band_data[2], 0, 1), 1 / gamma)

# Optional contrast enhancement
contrast = 1.5
r = np.clip(r * contrast, 0, 1)
g = np.clip(g * contrast, 0, 1)
b = np.clip(b * contrast, 0, 1)

# Stack RGB channels
rgb = np.stack([r, g, b], axis=2)

# Convert to 8 - bit
rgb_uint8 = (rgb * 255).astype(np.uint8)

# Replace NaN with black
rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0)

# Save as RGB image
Image.fromarray(rgb_uint8, "RGB").save(output_path)
print(f" Saved true color image to {output_path}")

return True, output_path

except Exception as e:
     pass
print(f" Error creating true color image: {e}")
return False, None


def process_rrqpe(file_path, output_path, base_ir_path=None):
    """Process rain rate data from RRQPE file."""
print(f"Processing rain rate data from {os.path.basename(file_path)}")

try:
     with xr.open_dataset(file_path) as ds:
     # Check for RRQPE variable
if "RRQPE" not in ds.variables:
     pass
print(" No RRQPE variable found")
return False, None

# Extract rain rate data (mm / h)
rr_data = ds["RRQPE"].values

# Print value range
min_val = np.nanmin(rr_data)
max_val = np.nanmax(rr_data)
print(f" Rain rate range: {min_val:.3f} - {max_val:.3f} mm / h")

# Scale to 0 - 255 (0 - 125 mm / h is a typical range)
scale_factor = 255 / 125 # 255 = 125 mm / h
rr_scaled = np.clip(rr_data * scale_factor, 0, 255).astype(np.uint8)

# Replace NaN with 0 (no rain)
rr_scaled = np.nan_to_num(rr_scaled, nan=0)

# Apply radar colormap with alpha channel
rgba = RADAR_LUT[rr_scaled]

# Save as standalone RGBA image
Image.fromarray(rgba, "RGBA").save(output_path)
print(f" Saved rain rate image to {output_path}")

# If base IR path provided, overlay the rain rate on it
if base_ir_path and os.path.exists(base_ir_path):
     pass
overlay_path = output_path.with_suffix(".overlay.png")

# Open base image and convert to RGBA
base_img = Image.open(base_ir_path).convert("RGBA")

# Open radar image
radar_img = Image.fromarray(rgba, "RGBA")

# Resize radar to match base if needed
if base_img.size != radar_img.size:
     pass
radar_img = radar_img.resize(base_img.size, Image.LANCZOS)

# Composite the images (alpha blending)
base_img.alpha_composite(radar_img)

# Save the result
base_img.save(overlay_path)
print(f" Saved rain rate overlay to {overlay_path}")

return True, overlay_path

return True, output_path

except Exception as e:
     pass
print(f" Error processing rain rate data: {e}")
return False, None


def build_cdn_url(satellite, sector, product, date, resolution):
    """Build URL for GOES imagery on NOAA CDN."""
# Format product type for CDN URL
product_map = {
"truecolor": "TRUECOLOR",
"geocolor": "GEOCOLOR",
"ir": "13",
"band13": "13",
"band09": "09",
"band07": "07",
"wv": "09",
"swir": "07",
"fire": "FIRE",
}
product_code = product_map.get(product.lower(), product.upper())

# Format sector for CDN URL
sector_map = {
"full_disk": "FD",
"conus": "C",
"mesoscale1": "M1",
"mesoscale2": "M2",
}
sector_code = sector_map.get(sector.lower(), sector)

# Format date for URL
date_obj = date if isinstance(date, datetime) else datetime.strptime(date, "%Y % j")
date_str = date_obj.strftime("%Y % m % d")

# Base URL format:
     pass
# https://cdn.star.nesdis.noaa.gov / GOES18 / ABI / FD / GEOCOLOR / 20250508 / 222021_GOES18 - ABI - FD - GEOCOLOR - 5424x5424.jpg
base_url = f"{CDN_BASE_URL}/{satellite}/ABI/{sector_code}/{product_code}/{date_str}"

return base_url, date_str


def check_cdn_url(url):
    """Check if a URL is accessible, bypassing HEAD request."""
# Use curl to check if URL is accessible, as CDN blocks HEAD requests
try:
     pass
cmd = f"curl -o /dev / null -s -w '%{{http_code}}' {url}"
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
status_code = result.stdout.strip()

return status_code == "200"
except Exception as e:
     pass
print(f" Error checking URL: {e}")
return False


def download_cdn_image(url, output_path):
    """Download an image from a URL."""
try:
     response = requests.get(url, stream=True, timeout=10)

if response.status_code == 200:
     pass
# Ensure parent directories exist
output_path.parent.mkdir(parents=True, exist_ok=True)

# Save the image
with open(output_path, "wb") as f:
     for chunk in response.iter_content(1024 * 1024):
         pass
     f.write(chunk)

print(f" Downloaded to {output_path}")
return True, output_path
else:
     print(f" Failed to download: HTTP {response.status_code}")
return False, None

except Exception as e:
     pass
print(f" Error downloading {url}: {e}")
return False, None


def find_latest_cdn_image(satellite, sector, product, resolution, days_back=15):
    """Find the latest available image on the CDN."""
print(f"Looking for latest {satellite} {sector} {product} image on CDN...")

now = datetime.now()

# Try each day, working backwards
for days in range(days_back):
     date = now - timedelta(days=days)

# Build base URL for this date
base_url, date_str = build_cdn_url(satellite, sector, product, date, resolution)

# Check if the date directory exists
try:
     pass
print(f" Checking date: {date_str}")

# Try to list files in the date directory
url = f"{base_url}/"
if check_cdn_url(url):
     pass
print(f" Found images for date: {date_str}")

# For now, just try a default time
# For a more comprehensive approach, we would need to list and parse the directory
default_times = ["180000", "190000", "200000", "210000", "220000"]

for time_str in default_times:
     # Try constructing a URL with this time
img_url = f"{base_url}/{time_str}_{satellite}-ABI-{sector}-{product}-{resolution}.jpg"

if check_cdn_url(img_url):
     pass
print(f" Found image with timestamp: {time_str}")
return True, img_url, f"{date_str}_{time_str}"

except Exception as e:
     pass
print(f" Error checking date {date_str}: {e}")

print(f" No images found in the last {days_back} days")
return False, None, None


def get_goes_image(
satellite, sector, product, year=None, doy=None, hour=None, output_dir=None
):
    """
Get GOES satellite imagery using the most appropriate source.

This function tries multiple sources in order:
     1. CDN for pre - processed JPEGs (recent dates only)
2. MCMIP for pre - processed multi - channel data
3. CMIP for individual bands to process manually
4. L1b / Rad data as a fallback

Parameters:
     satellite: Satellite name ('GOES16' or 'GOES18')
sector: Sector name ('full_disk', 'conus', 'mesoscale1', 'mesoscale2')
product: Product type ('truecolor', 'ir', 'band13', etc.)
year: Year (YYYY)
doy: Day of year (1 - 366)
hour: Hour of day (0 - 23)
output_dir: Directory to save output images

Returns:
     success: True if successful, False otherwise
image_path: Path to the output image if successful
"""
# Set up output directory
if output_dir is None:
     pass
output_dir = IMAGE_DIR
else:
     output_dir = Path(output_dir)
output_dir.mkdir(parents=True, exist_ok=True)

# Check if date / time is provided
date_provided = year is not None and doy is not None

# Bucket for S3 access
bucket = f"noaa-{satellite.lower()}"

# Resolution for CDN images
if sector.lower() == "full_disk":
     pass
resolution = "1808x1808" # Medium resolution for full disk
elif sector.lower() == "conus":
     pass
resolution = "1200x1200" # Medium resolution for CONUS
else:
     resolution = "1000x1000" # Medium resolution for mesoscale

# Determine S3 products and file patterns
if product.lower() in ["ir", "band13"]:
     pass
band = 13
s3_product = "ABI - L2 - CMIP"
elif product.lower() in ["wv", "band09"]:
     pass
band = 9
s3_product = "ABI - L2 - CMIP"
elif product.lower() in ["swir", "band07"]:
     pass
band = 7
s3_product = "ABI - L2 - CMIP"
elif product.lower() == "truecolor":
     pass
band = None
s3_product = "ABI - L2 - MCMIP" # Try MCMIP first for true color
elif product.lower() == "rain":
     pass
band = None
s3_product = "ABI - L2 - RRQPE"
else:
     # Unknown product
print(f"Unknown product: {product}")
return False, None

# Part 1: Try CDN for recent dates
if not date_provided or (
year >= datetime.now().year and doy >= datetime.now().timetuple().tm_yday - 15
):
     pass
print(f"\nTrying CDN source for {satellite} {sector} {product}...")

# If date / time is provided, use it, otherwise look for latest
if date_provided:
     pass
# Convert to datetime for CDN URL
date_str = f"{year}{doy:03d}"
date_obj = datetime.strptime(date_str, "%Y % j")

# Build URL
base_url, date_str = build_cdn_url(
satellite, sector, product, date_obj, resolution
)

# For now, just try the specified hour
if hour is not None:
     pass
time_str = f"{hour:02d}0000"
img_url = f"{base_url}/{time_str}_{satellite}-ABI-{sector}-{product.upper()}-{resolution}.jpg"

if check_cdn_url(img_url):
     pass
print(f" Found CDN image for {date_str} at {hour:02d}:00")

# Download the image
output_path = (
output_dir
/ f"{satellite}_{sector}_{product}_{date_str}_{time_str}_cdn.jpg"
)
success, downloaded_path = download_cdn_image(img_url, output_path)

if success:
     pass
return True, downloaded_path
else:
     # Try to find the latest image
success, img_url, timestamp = find_latest_cdn_image(
satellite, sector, product.upper(), resolution
)

if success and img_url:
     pass
# Download the image
output_path = (
output_dir / f"{satellite}_{sector}_{product}_{timestamp}_cdn.jpg"
)
success, downloaded_path = download_cdn_image(img_url, output_path)

if success:
     pass
return True, downloaded_path

# If date / time not provided, we can't continue with S3 methods
if not date_provided or hour is None:
     pass
print(
"Date and hour are required for S3 access. Please provide year, doy, and hour."
)
return False, None

# Part 2: Try S3 buckets with appropriate products
print(f"\nTrying S3 source for {satellite} {sector} {product}...")

if s3_product == "ABI - L2 - MCMIP":
     pass
# Try MCMIP for true color
wildcard_patterns = build_s3_mcmip_wildcard(satellite, sector, year, doy, hour)
prefix = build_s3_prefix(
"ABI - L2 - MCMIP" + get_sector_code(sector), year, doy, hour
)

mcmip_files = find_s3_files(bucket, prefix, wildcard_patterns)

if mcmip_files:
     pass
# Download the first matching file
mcmip_file = mcmip_files[0]
nc_path = download_s3_file(bucket, mcmip_file)

if nc_path:
     pass
# Extract timestamp for filename
timestamp = (
extract_timestamp(os.path.basename(mcmip_file))
or f"{year}{doy:03d}{hour:02d}0000"
)
output_path = (
output_dir / f"{satellite}_{sector}_truecolor_{timestamp}_mcmip.png"
)

# Process the MCMIP file
success, image_path = process_mcmip_truecolor(nc_path, output_path)

if success:
     pass
return True, image_path

# Try CMIP for single bands
if band is not None:
     pass
# Try CMIP for individual bands
wildcard_patterns = build_s3_cmip_wildcard(
satellite, sector, band, year, doy, hour
)
prefix = build_s3_prefix(
"ABI - L2 - CMIP" + get_sector_code(sector), year, doy, hour
)

cmip_files = find_s3_files(bucket, prefix, wildcard_patterns)

if cmip_files:
     pass
# Download the first matching file
cmip_file = cmip_files[0]
nc_path = download_s3_file(bucket, cmip_file)

if nc_path:
     pass
# Extract timestamp for filename
timestamp = (
extract_timestamp(os.path.basename(cmip_file))
or f"{year}{doy:03d}{hour:02d}0000"
)

if band == 13:
     pass
# Process IR image with Sánchez colorization
output_path = (
output_dir / f"{satellite}_{sector}_ir_{timestamp}_sanchez.png"
)
success, gray_path, color_path = process_ir_cmip(
nc_path, output_path
)

if success:
     pass
# If rain data is requested, try to get that too
if product.lower() == "rain":
     pass
# Try to find and process RRQPE data
rrqpe_patterns = build_s3_rrqpe_wildcard(
satellite, sector, year, doy, hour
)
rrqpe_prefix = build_s3_prefix(
"ABI - L2 - RRQPE" + get_sector_code(sector),
year,
doy,
hour,
)

rrqpe_files = find_s3_files(
bucket, rrqpe_prefix, rrqpe_patterns
)

if rrqpe_files:
     pass
# Download the first matching file
rrqpe_file = rrqpe_files[0]
rrqpe_path = download_s3_file(bucket, rrqpe_file)

if rrqpe_path:
     pass
# Process rain rate data and overlay on IR image
rain_path = (
output_dir
/ f"{satellite}_{sector}_rain_{timestamp}.png"
)
success, overlay_path = process_rrqpe(
rrqpe_path, rain_path, color_path
)

if success:
     pass
return True, overlay_path

return True, color_path
else:
     # Other bands just return as is
output_path = (
output_dir / f"{satellite}_{sector}_band{band}_{timestamp}.png"
)

# Just save the grayscale image
with xr.open_dataset(nc_path) as ds:
     # Extract the CMI data
data = ds["CMI"].values

# Scale to 0 - 255
if np.nanmax(data) <= 1.0:
     pass
data_uint8 = (data * 255).astype(np.uint8)
else:
     data_uint8 = data.astype(np.uint8)

# Replace NaN with black
data_uint8 = np.nan_to_num(data_uint8, nan=0)

# Save grayscale image
Image.fromarray(data_uint8, "L").save(output_path)
print(f" Saved Band {band} image to {output_path}")

return True, output_path

# If we're looking for true color, try manual composition
if product.lower() == "truecolor":
     pass
# Try to get Bands 1, 2, and 3
band_files = {}
for band in [1, 2, 3]:
     wildcard_patterns = build_s3_cmip_wildcard(
satellite, sector, band, year, doy, hour
)
prefix = build_s3_prefix(
"ABI - L2 - CMIP" + get_sector_code(sector), year, doy, hour
)

files = find_s3_files(bucket, prefix, wildcard_patterns)

if files:
     pass
# Get the files for this band
band_files[band] = files

# Check if we have all bands
if len(band_files) == 3:
     pass
# Find files with common timestamps
timestamps = {}

for band, files in band_files.items():
     for file in files:
         pass
     timestamp = extract_timestamp(file)
if timestamp:
     pass
if timestamp not in timestamps:
     pass
timestamps[timestamp] = {}
timestamps[timestamp][band] = file

# Find timestamps that have all bands
complete_timestamps = []
for timestamp, bands in timestamps.items():
     if len(bands) == 3:
         pass
     pass
complete_timestamps.append(timestamp)

if complete_timestamps:
     pass
# Sort and pick the timestamp closest to the requested hour
target_minute = 0 # Use 00 minutes as target
target_time = int(f"{hour:02d}{target_minute:02d}")

# Find closest timestamp
closest_timestamp = sorted(
complete_timestamps, key=lambda x: abs(int(x[8:12]) - target_time)
)[0]

print(f" Found common timestamp: {closest_timestamp}")

# Download the files
downloaded_files = []
for band in [1, 2, 3]:
     file_key = timestamps[closest_timestamp][band]
nc_path = download_s3_file(bucket, file_key)
if nc_path:
     pass
downloaded_files.append(nc_path)

if len(downloaded_files) == 3:
     pass
# Process true color image
output_path = (
output_dir
/ f"{satellite}_{sector}_truecolor_{closest_timestamp}_manual.png"
)
success, image_path = process_manual_truecolor(
downloaded_files, output_path
)

if success:
     pass
return True, image_path

# If all else fails, we could try L1b data, but that's more complex
print("\nUnable to find or process the requested imagery.")
return False, None


def main():
    pass
"""Main function to demonstrate usage of the improved processor."""
import argparse

parser = argparse.ArgumentParser(
description="Download and process GOES satellite imagery"
)
parser.add_argument(
"--satellite",
choices=["GOES16", "GOES18"],
default="GOES18",
help="Satellite to use (default: GOES18)",
)
parser.add_argument(
"--sector",
choices=["full_disk", "conus", "mesoscale1", "mesoscale2"],
default="full_disk",
help="Sector to download (default: full_disk)",
)
parser.add_argument(
"--product",
choices=["truecolor", "ir", "band13", "wv", "band09", "swir", "band07", "rain"],
default="truecolor",
help="Product to download (default: truecolor)",
)
parser.add_argument("--year", type=int, help="Year (YYYY)")
parser.add_argument("--doy", type=int, help="Day of year (1 - 366)")
parser.add_argument("--hour", type=int, help="Hour of day (0 - 23)")
parser.add_argument(
"--output - dir",
default=None,
help="Directory to save output images (default: ~/Downloads / goes_improved / images)",
)
parser.add_argument(
"--use - cdn", action="store_true", help="Try CDN first (for recent dates)"
)
args = parser.parse_args()

# If year / doy not provided, use current date
if args.year is None or args.doy is None:
     pass
now = datetime.now()
args.year = now.year
args.doy = now.timetuple().tm_yday

# If hour not provided, use current hour
if args.hour is None:
     pass
args.hour = datetime.now().hour

# Download and process the imagery
success, image_path = get_goes_image(
args.satellite,
args.sector,
args.product,
args.year,
args.doy,
args.hour,
args.output_dir,
)

if success:
     pass
print("\nSuccessfully processed GOES imagery:")
print(f"Image saved to: {image_path}")
else:
     print("\nFailed to process GOES imagery.")


if __name__ == "__main__":
    pass
main()
