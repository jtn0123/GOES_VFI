#!/usr/bin/env python3
"""
GOES imagery processor that uses Satpy for advanced processing.
This provides the best quality for true color imagery and other composites.
"""
import argparse
import os
import re
from pathlib import Path

import boto3
import numpy as np
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config
from PIL import Image

# Try to import satpy
try:
    from satpy import Scene

from satpy.writers import (  # Configure boto3 for anonymous access s3_config = Config(signature_version=UNSIGNED, region_name="us - east - 1") s3 = boto3.client("s3", config=s3_config) # Output directories; Define Sánchez color table for IR images (temperature to RGB mapping) def create_sanchez_lut(): """Create a Sánchez - style colormap for IR temperatures.""" # Define colors for different temperature ranges colors = [ [0, 0, 0], # Black for space / very cold [80, 0, 120], # Purple for very cold clouds [0, 0, 255], # Blue for cold high clouds [0, 255, 255], # Cyan for mid - level clouds [0, 255, 0], # Green for lower clouds [255, 255, 0], # Yellow for very low clouds [255, 150, 0], # Orange for warm areas [255, 0, 0], # Red for hot areas [255, 255, 255], # White for very hot areas ] # Create a 256 - entry lookup table lut = np.zeros((256, 3), dtype=np.uint8) # Interpolate colors across the 0 - 255 range num_colors = len(colors) for i in range(256): # Find position in color scale (0 to num_colors - 1) position = i / 255 * (num_colors - 1) # Find the two colors to interpolate between idx1 = int(position) idx2 = min(idx1 + 1, num_colors - 1) frac = position - idx1 # Interpolate lut[i] = np.round( np.array(colors[idx1]) * (1 - frac) + np.array(colors[idx2]) * frac ).astype(np.uint8) return lut # Create the Sánchez LUT SANCHEZ_LUT = create_sanchez_lut() def get_sector_code(sector): """Convert sector name to code used in filenames.""" sector_map = { "full_disk": "F", "fd": "F", "conus": "C", "mesoscale1": "M1", "mesoscale2": "M2", "mesoscale": "M", # Generic mesoscale } return sector_map.get(sector.lower(), "F") def build_s3_cmip_wildcard(satellite, sector, band, year, doy, hour): """Build wildcard pattern for CMIP files on S3.""" satellite_num = satellite[-2:] sector_code = get_sector_code(sector) # For mesoscale, we might need to try both M1 and M2 if sector_code == "M": sector_codes = ["M1", "M2"] else: sector_codes = [sector_code] patterns = [] for code in sector_codes: # Single - band CMIP wildcard pattern pattern = ( f"OR_ABI - L2 - CMIP{code}-M6C{band:02d}_G{satellite_num}" f"_s{year}{doy:03d}{hour:02d}*.nc" ) patterns.append(pattern) return patterns def build_s3_prefix(product, year, doy, hour): """Build S3 prefix for listing files.""" # Format: product / year / doy / hour return f"{product}/{year}/{doy:03d}/{hour:02d}/" def find_s3_files(bucket, prefix, patterns): """Find files in S3 bucket matching wildcard patterns.""" print(f"Looking for files in {bucket}/{prefix} with patterns: {patterns}") matching_files = [] try: # List objects with the given prefix paginator = s3.get_paginator("list_objects_v2") pages = paginator.paginate(Bucket=bucket, Prefix=prefix) # Check each object against the wildcard patterns for page in pages: if "Contents" not in page: continue for obj in page["Contents"]: key = obj["Key"] if any( re.search(pattern.replace("*", ".*"), key) for pattern in patterns ): matching_files.append(key) print(f" Found {len(matching_files)} matching files") return matching_files except Exception as e: print(f"Error listing files in S3: {e}") return [] def download_s3_file(bucket, key, output_dir=DOWNLOAD_DIR): """Download a file from S3.""" filename = os.path.basename(key) output_path = output_dir / filename if output_path.exists(): print(f" File already exists: {output_path}") return output_path print(f" Downloading {filename}...") try: s3.download_file(bucket, key, str(output_path)) print(f" Downloaded to {output_path}") return output_path except Exception as e: print(f" Error downloading {key}: {e}") return None def extract_timestamp(filename): """Extract timestamp from GOES filename.""" match = re.search(r"s(\d{14})", filename) if match: return match.group(1) return None def process_ir_image(file_path, output_path): """Process IR image with Sánchez colorization.""" print(f"Processing IR image from {os.path.basename(file_path)}") try: with xr.open_dataset(file_path) as ds: # Extract the CMI data (IR temperature) ir_data = ds["CMI"].values # Get temperature range min_temp = np.nanmin(ir_data) max_temp = np.nanmax(ir_data) print(f" Temperature range: {min_temp:.1f}K - {max_temp:.1f}K") # Normalize to 0 - 255 range ir_norm = 1.0 - ((ir_data - 180) / (320 - 180)) ir_norm = np.clip(ir_norm, 0, 1) ir_uint8 = (ir_norm * 255).astype(np.uint8) # Replace NaN with black ir_uint8 = np.nan_to_num(ir_uint8, nan=0) # Save grayscale version gray_path = output_path.with_suffix(".gray.png") Image.fromarray(ir_uint8, "L").save(gray_path) print(f" Saved grayscale image to {gray_path}") # Apply Sánchez colormap colored = SANCHEZ_LUT[ir_uint8] Image.fromarray(colored, "RGB").save(output_path) print(f" Saved Sánchez IR image to {output_path}") return True, gray_path, output_path except Exception as e: print(f" Error processing IR image: {e}") return False, None, None def process_true_color_with_satpy(band_files, output_path): """Process true color image using Satpy.""" if not SATPY_AVAILABLE: print(" Satpy is not available. Cannot process with Satpy.") return False, None print(f"Processing true color image with Satpy from {len(band_files)} files") try: # Create a Scene with the CMIP files filenames = [str(f) for f in band_files] scn = Scene(reader="abi_l2_cmip", filenames=filenames) # Available products available_composites = scn.available_composite_names() available_datasets = scn.available_dataset_names() print(f" Available composites: {available_composites}") print(f" Available datasets: {available_datasets}") # Load the true_color composite if "true_color" in available_composites: scn.load(["true_color"]) # Convert to image and save img = to_image(scn["true_color"]) img.save(output_path) print(f" Saved true color image to {output_path}") return True, output_path else: print(" 'true_color' composite not available from these files") # Try manual composition if set(["C01", "C02", "C03"]).issubset(set(available_datasets)): print(" Loading individual bands for manual composition") scn.load(["C01", "C02", "C03"]) # Create RGB composite rgb = scn.images["true_color"] img = to_image(rgb) img.save(output_path) print(f" Saved manually composed true color image to {output_path}") return True, output_path return False, None except Exception as e: print(f" Error processing with Satpy: {e}") return False, None def process_true_color_manually(file_paths, output_path): """Create true color image by manually combining bands 1, 2, and 3.""" print(f"Manually processing true color image from {len(file_paths)} files") try: # Check if we have all three bands if len(file_paths) != 3: print(f" Expected 3 files for RGB, got {len(file_paths)}") return False, None # Load the three band data arrays band_data = [] for i, file_path in enumerate(file_paths): band_num = i + 1 with xr.open_dataset(file_path) as ds: data = ds["CMI"].values band_data.append(data) print( f" Loaded Band {band_num} from {os.path.basename(file_path)}, shape: {data.shape}"
    DOWNLOAD_DIR,
    IMAGE_DIR,
    SATPY_AVAILABLE,
    DOWNLOAD_DIR.mkdir,
    False,
    IMAGE_DIR.mkdir,
    ImportError:,
    Path,
    Satpy,
    Some,
    True,
    "images",
    "To,
    "Warning:,
    "~/Downloads,
    /,
    =,
    be,
    except,
    exist_ok=True,
    features,
    goes_satpy",
    install,
    installed.,
    is,
    limited.",
    not,
    os.path.expanduser,
    parents=True,
    pip,
    print,
    run:,
    satpy,
    satpy",
    to_image,
    will,
)

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
img = Image.fromarray(
np.clip(data, 0, 1).astype(np.float32), mode="F"
)
resized = img.resize((min_width, min_height), Image.LANCZOS)
resized_bands.append(np.array(resized))

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
rgb = np.dstack([r, g, b])

# Convert to 8 - bit
rgb_uint8 = (rgb * 255).astype(np.uint8)

# Replace NaN with black
rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0)

# Save as RGB image
Image.fromarray(rgb_uint8, "RGB").save(output_path)
print(f" Saved manually composed true color image to {output_path}")

return True, output_path

except Exception as e:
     pass
print(f" Error creating true color image: {e}")
return False, None


def get_goes_image(satellite, sector, product, year, doy, hour, output_dir=None):
    """
Get GOES satellite imagery using S3 and process with Satpy if available.

Parameters:
     pass
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

# Bucket for S3 access
bucket = f"noaa-{satellite.lower()}"

# Determine S3 products and file patterns based on product
if product.lower() in ["ir", "band13"]:
     pass
# IR imagery (Band 13)
band = 13
required_bands = [band]
elif product.lower() in ["wv", "band09"]:
     pass
# Water vapor (Band 9)
band = 9
required_bands = [band]
elif product.lower() in ["swir", "band07"]:
     pass
# Shortwave IR (Band 7)
band = 7
required_bands = [band]
elif product.lower() == "truecolor":
     pass
# True color requires bands 1, 2, and 3
required_bands = [1, 2, 3]
else:
     # Unknown product
print(f"Unknown product: {product}")
return False, None

# Find and download required band files
band_files = {}
downloaded_files = {}

for band in required_bands:
     # Build S3 prefix and wildcard patterns
wildcard_patterns = build_s3_cmip_wildcard(
satellite, sector, band, year, doy, hour
)

sector_code = get_sector_code(sector)
if sector_code == "M":
     pass
# Try both M1 and M2 for mesoscale
prefixes = [
build_s3_prefix("ABI - L2 - CMIPM1", year, doy, hour),
build_s3_prefix("ABI - L2 - CMIPM2", year, doy, hour),
]
else:
     # For full disk or CONUS
prefix = build_s3_prefix(f"ABI - L2 - CMIP{sector_code}", year, doy, hour)
prefixes = [prefix]

# Check each prefix
for prefix in prefixes:
     files = find_s3_files(bucket, prefix, wildcard_patterns)
if files:
     pass
band_files[band] = files
break

# Check if we have all required bands
if set(required_bands) != set(band_files.keys()):
     pass
print(f"Could not find all required bands. Found: {list(band_files.keys())}")
return False, None

# Find common timestamps across all bands
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

# Find timestamps that have all required bands
complete_timestamps = []
for timestamp, bands in timestamps.items():
     if set(required_bands) == set(bands.keys()):
         pass
     pass
complete_timestamps.append(timestamp)

if not complete_timestamps:
     pass
print("No common timestamps found for all required bands")
return False, None

# Sort and pick the timestamp closest to the requested hour
target_minute = 0 # Use 00 minutes as target
target_time = int(f"{hour:02d}{target_minute:02d}")

# Find closest timestamp
closest_timestamp = sorted(
complete_timestamps, key=lambda x: abs(int(x[8:12]) - target_time)
)[0]

print(f"Selected timestamp: {closest_timestamp}")

# Download the files
downloaded_files = []
for band in required_bands:
     file_key = timestamps[closest_timestamp][band]
nc_path = download_s3_file(bucket, file_key)
if nc_path:
     pass
downloaded_files.append(nc_path)

if len(downloaded_files) != len(required_bands):
     pass
print("Failed to download all required files")
return False, None

# Process the files based on the requested product
if product.lower() in ["ir", "band13"]:
     pass
# Process IR image with Sánchez colorization
output_path = (
output_dir / f"{satellite}_{sector}_ir_{closest_timestamp}_sanchez.png"
)
success, gray_path, color_path = process_ir_image(
downloaded_files[0], output_path
)

if success:
     pass
return True, color_path

elif product.lower() == "truecolor":
     pass
# Process true color imagery
output_path = (
output_dir / f"{satellite}_{sector}_truecolor_{closest_timestamp}.png"
)

# Try Satpy first if available
if SATPY_AVAILABLE:
     pass
success, image_path = process_true_color_with_satpy(
downloaded_files, output_path
)
if success:
     pass
return True, image_path

# Fall back to manual processing
success, image_path = process_true_color_manually(downloaded_files, output_path)
if success:
     pass
return True, image_path

elif product.lower() in ["wv", "band09", "swir", "band07"]:
     pass
# Process other bands as grayscale
band_name = product.lower()
output_path = (
output_dir / f"{satellite}_{sector}_{band_name}_{closest_timestamp}.png"
)

# Simple grayscale processing
with xr.open_dataset(downloaded_files[0]) as ds:
     data = ds["CMI"].values

# Scale to 0 - 255
if np.nanmax(data) <= 1.0:
     pass
# 0 - 1 range (reflectance)
data_uint8 = (data * 255).astype(np.uint8)
else:
     # Temperature range, normalize
data_norm = (data - np.nanmin(data)) / (
np.nanmax(data) - np.nanmin(data)
)
data_uint8 = (data_norm * 255).astype(np.uint8)

# Replace NaN with black
data_uint8 = np.nan_to_num(data_uint8, nan=0)

# Save grayscale image
Image.fromarray(data_uint8, "L").save(output_path)
print(f"Saved {band_name} image to {output_path}")

return True, output_path

# If we get here, processing failed
print("Processing failed")
return False, None


def main():
    """Main function to demonstrate usage."""
parser = argparse.ArgumentParser(
description="Download and process GOES satellite imagery with Satpy"
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
choices=["truecolor", "ir", "band13", "wv", "band09", "swir", "band07"],
default="truecolor",
help="Product to download (default: truecolor)",
)
parser.add_argument("--year", type=int, default=2023, help="Year (default: 2023)")
parser.add_argument(
"--doy", type=int, default=121, help="Day of year (default: 121 for May 1)"
)
parser.add_argument(
"--hour", type=int, default=19, help="Hour of day UTC (default: 19)"
)
parser.add_argument(
"--output - dir",
default=None,
help="Directory to save output images (default: ~/Downloads / goes_satpy / images)",
)
args = parser.parse_args()

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
