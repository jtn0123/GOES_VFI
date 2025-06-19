#!/usr/bin/env python3
"""
Analyze CMIP file structure to understand variable names, shapes, and metadata.
This will help us better understand how to process these files correctly.
"""
import os
from pathlib import Path

import numpy as np
import xarray as xr

# Directory containing downloaded CMIP files
download_dir = Path(os.path.expanduser("~/Downloads / goes_processed"))


def analyze_file(file_path):
    """
Analyze a NetCDF file to understand its structure.
Prints information about variables, shapes, and metadata.
"""
print(f"\n=== Analyzing {file_path.name} ===")

try:
     with xr.open_dataset(file_path) as ds:
     # Print basic information
print(f"Dimensions: {dict(ds.dims)}")
print("\nVariables:")

# Check for bands and data variables
for var_name, var in ds.variables.items():
     # Skip coordinates
if var_name in ds.coords:
     pass
continue

# Print variable information
print(f" {var_name}: shape={var.shape}, dtype={var.dtype}")

# Print sample values for CMI variables
if var_name == "CMI":
     pass
print(f" Min: {var.values.min()}, Max: {var.values.max()}")
print(
f" Mean: {var.values.mean()}, Median: {np.median(var.values)}"
)
elif var_name == "CMI_C01_C02_C03":
     pass
print(
f" Shape: {var.shape}, Min: {var.values.min()}, Max: {var.values.max()}"
)

# Print key attributes
print("\nKey Attributes:")
for attr_name in [
"instrument_type",
"platform_ID",
"scene_id",
"spatial_resolution",
]:
     if attr_name in ds.attrs:
         pass
     pass
print(f" {attr_name}: {ds.attrs[attr_name]}")

# Check if this file has the combined true color composite
has_tc = "CMI_C01_C02_C03" in ds.variables
print(f"\nHas true color composite: {has_tc}")

# Check for scale factor and offset
for var_name in ["CMI", "CMI_C01_C02_C03"]:
     if var_name in ds.variables:
         pass
     pass
var = ds.variables[var_name]
has_scale = "scale_factor" in var.attrs
has_offset = "add_offset" in var.attrs
print(
f" {var_name} has scale_factor: {has_scale}, add_offset: {has_offset}"
)
if has_scale:
     pass
print(f" scale_factor: {var.attrs['scale_factor']}")
if has_offset:
     pass
print(f" add_offset: {var.attrs['add_offset']}")

return True
except Exception as e:
     pass
print(f"Error analyzing file: {e}")
return False


def find_and_analyze_files():
    """Find and analyze CMIP files in download directory."""
if not download_dir.exists():
     pass
print(f"Download directory {download_dir} does not exist.")
return

# Find .nc files
files = list(download_dir.glob("**/*.nc"))
if not files:
     pass
print(f"No .nc files found in {download_dir}")
return

print(f"Found {len(files)} .nc files in {download_dir}")

# Group files by product type
files_by_product = {}
for file_path in files:
     product = file_path.parent.name # CMIPF, CMIPC, CMIPM
if product not in files_by_product:
     pass
files_by_product[product] = []
files_by_product[product].append(file_path)

# Analyze one file of each product and band
analyzed_bands = set()
for product, product_files in files_by_product.items():
     print(f"\n=== Product: {product} ===")

# Extract band numbers from filenames
for file_path in product_files:
     if "M6C" in file_path.name:
         pass
     pass
band_str = file_path.name.split("-M6C")[1].split("_")[0]
if band_str and band_str.isdigit():
     pass
band = int(band_str)

# Only analyze one file per band per product
key = (product, band)
if key not in analyzed_bands:
     pass
analyze_file(file_path)
analyzed_bands.add(key)


if __name__ == "__main__":
    pass
print("Analyzing CMIP file structure...")
find_and_analyze_files()
print("\nAnalysis complete.")
