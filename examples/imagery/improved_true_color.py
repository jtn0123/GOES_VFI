#!/usr/bin/env python3
"""
Improved GOES true color imagery processor with enhanced color science.
This script provides more natural-looking true color imagery using:
- Improved Rayleigh scattering correction
- Better color balance
- Advanced gamma and contrast handling
"""
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import os
from pathlib import Path
import xarray as xr
from PIL import Image
import numpy as np
import re
from datetime import datetime
import argparse
from skimage import exposure

# Configure boto3 for anonymous access
s3_config = Config(
    signature_version=UNSIGNED,
    region_name="us-east-1"
)

s3 = boto3.client("s3", config=s3_config)

# Default output directories
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_true_color"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

def get_doy(date_str):
    """Convert YYYY-MM-DD to day of year."""
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
        pattern = f"OR_ABI-L2-CMIPM{sector[-1]}-M6C{band:02d}_G{satellite_num}_s"
    elif sector == "M":
        # Generic mesoscale (could be either M1 or M2)
        # Just search for the band number, we'll find either M1 or M2
        pattern = f"C{band:02d}_G{satellite_num}_s"
    else:
        # Regular case (F for Full Disk, C for CONUS)
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
        paginator = s3.get_paginator('list_objects_v2')
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
    match = re.search(r's(\d{14})', filename)
    if match:
        return match.group(1)
    return None

def find_common_timestamp(files_by_band):
    """Find common timestamp across multiple bands."""
    # Extract timestamps for each band
    timestamps_by_band = {}
    for band, files in files_by_band.items():
        timestamps_by_band[band] = {}
        for file in files:
            timestamp = extract_timestamp(file)
            if timestamp:
                timestamps_by_band[band][timestamp] = file
    
    # Find timestamps common to all bands
    common_timestamps = set(timestamps_by_band[list(timestamps_by_band.keys())[0]].keys())
    for band in timestamps_by_band:
        common_timestamps &= set(timestamps_by_band[band].keys())
    
    if not common_timestamps:
        return None, {}
    
    # Pick the first common timestamp
    timestamp = sorted(common_timestamps)[0]
    
    # Get files for this timestamp
    files = {}
    for band in timestamps_by_band:
        files[band] = timestamps_by_band[band][timestamp]
    
    return timestamp, files

def correct_rayleigh_scattering(band_data, sun_zenith=45):
    """
    Apply Rayleigh scattering correction to make images more natural.
    
    Args:
        band_data: List of reflectance data for bands 1, 2, 3
        sun_zenith: Sun zenith angle in degrees (approximation)
    
    Returns:
        Corrected band data
    """
    print("  Applying Rayleigh scattering correction")
    
    # Approximate Rayleigh optical depths for ABI bands 1, 2, 3
    # These values are wavelength-dependent
    rayleigh_optical_depth = [0.059, 0.026, 0.016]
    
    # Air mass factor approximation
    air_mass = 1.0 / np.cos(np.radians(sun_zenith))
    
    # Correction factors
    corrected_data = []
    for i, data in enumerate(band_data):
        # Calculate Rayleigh transmittance
        rayleigh_transmittance = np.exp(-rayleigh_optical_depth[i] * air_mass)
        
        # Calculate Rayleigh reflectance (approximation)
        rayleigh_reflectance = (1 - rayleigh_transmittance) * 0.5
        
        # Apply correction: (measured - rayleigh) / transmittance
        corrected = (data - rayleigh_reflectance) / rayleigh_transmittance
        
        # Clip to valid range
        corrected = np.clip(corrected, 0, 1)
        
        corrected_data.append(corrected)
    
    return corrected_data

def adjust_color_balance(r, g, b):
    """
    Adjust color balance for more natural Earth appearance.
    
    Args:
        r, g, b: Red, green, blue channel data (0-1 range)
    
    Returns:
        Color-balanced r, g, b data
    """
    print("  Applying color balance adjustment")
    
    # Channel-specific gains for better color balance
    # These values are tuned for GOES-R ABI
    r_gain = 1.0
    g_gain = 0.97
    b_gain = 0.93
    
    # Apply gains
    r_balanced = np.clip(r * r_gain, 0, 1)
    g_balanced = np.clip(g * g_gain, 0, 1)
    b_balanced = np.clip(b * b_gain, 0, 1)
    
    return r_balanced, g_balanced, b_balanced

def enhance_contrast_and_vibrance(r, g, b):
    """
    Enhance image contrast and vibrance with advanced algorithms.
    
    Args:
        r, g, b: Red, green, blue channel data (0-1 range)
    
    Returns:
        Enhanced r, g, b data
    """
    print("  Enhancing contrast and vibrance")
    
    # Stack RGB for processing
    rgb = np.dstack([r, g, b])
    
    # Adaptive histogram equalization for better contrast
    # This works better than a simple contrast stretch
    rgb_eq = exposure.equalize_adapthist(rgb, clip_limit=0.03)
    
    # Split channels
    r_eq, g_eq, b_eq = rgb_eq[:,:,0], rgb_eq[:,:,1], rgb_eq[:,:,2]
    
    # Vibrance adjustment (increases saturation while protecting skin tones)
    # Compute luminance
    lum = 0.299 * r_eq + 0.587 * g_eq + 0.114 * b_eq
    
    # Compute saturation
    sat = np.maximum.reduce([r_eq - lum, g_eq - lum, b_eq - lum])
    
    # Apply vibrance (more to less saturated pixels)
    vibrance = 0.15  # Vibrance amount
    sat_mask = 1 - sat
    
    r_vib = r_eq + (r_eq - lum) * sat_mask * vibrance
    g_vib = g_eq + (g_eq - lum) * sat_mask * vibrance
    b_vib = b_eq + (b_eq - lum) * sat_mask * vibrance
    
    # Clip to valid range
    r_vib = np.clip(r_vib, 0, 1)
    g_vib = np.clip(g_vib, 0, 1)
    b_vib = np.clip(b_vib, 0, 1)
    
    return r_vib, g_vib, b_vib

def process_improved_true_color(band_files, output_path, advanced_enhancements=True):
    """
    Process true color image with improved color science for more natural appearance.
    
    Key improvements:
    1. Rayleigh scattering correction for atmospheric effects
    2. Proper color balance for Earth-like appearance
    3. Advanced contrast and vibrance enhancements
    4. Adaptive histogram equalization for better dynamic range
    """
    print(f"Processing improved true color image from band files")
    
    try:
        # Load the three band data arrays
        band_data = []
        band_shapes = []
        
        for band, file_path in sorted(band_files.items()):
            with xr.open_dataset(file_path) as ds:
                data = ds["CMI"].values
                band_data.append(data)
                band_shapes.append(data.shape)
                print(f"  Loaded Band {band} from {os.path.basename(file_path)}")
                print(f"    Shape: {data.shape}, Range: {np.nanmin(data):.3f} - {np.nanmax(data):.3f}")
        
        # Check if arrays have the same shape
        if len(set(tuple(shape) for shape in band_shapes)) > 1:
            print(f"  Bands have different shapes: {band_shapes}")
            print("  Resizing to match smallest dimensions...")
            
            # Find the smallest dimensions (typically Bands 1 and 3)
            min_height = min(shape[0] for shape in band_shapes)
            min_width = min(shape[1] for shape in band_shapes)
            
            # Resize all bands to the smallest shape
            resized_bands = []
            for i, data in enumerate(band_data):
                if data.shape[0] == min_height and data.shape[1] == min_width:
                    resized_bands.append(data)
                else:
                    # Use PIL for resizing
                    # Convert to 8-bit for resizing (float32 not supported by PIL)
                    img = Image.fromarray((np.clip(data, 0, 1) * 255).astype(np.uint8))
                    resized = img.resize((min_width, min_height), Image.Resampling.LANCZOS)
                    # Convert back to 0-1 range
                    resized_bands.append(np.array(resized).astype(float) / 255.0)
            
            band_data = resized_bands
        
        if advanced_enhancements:
            # Apply Rayleigh scattering correction
            band_data = correct_rayleigh_scattering(band_data)
        
        # Apply gamma correction (pre-color balance)
        gamma = 2.2
        r = np.power(np.clip(band_data[0], 0, 1), 1/gamma)
        g = np.power(np.clip(band_data[1], 0, 1), 1/gamma)
        b = np.power(np.clip(band_data[2], 0, 1), 1/gamma)
        
        if advanced_enhancements:
            # Apply color balance for more natural appearance
            r, g, b = adjust_color_balance(r, g, b)
            
            # Apply advanced contrast and vibrance enhancements
            r, g, b = enhance_contrast_and_vibrance(r, g, b)
        else:
            # Basic contrast adjustment (simpler alternative)
            contrast = 1.3
            r = np.clip(r * contrast, 0, 1)
            g = np.clip(g * contrast, 0, 1)
            b = np.clip(b * contrast, 0, 1)
        
        # Stack RGB channels
        rgb = np.dstack([r, g, b])
        
        # Convert to 8-bit
        rgb_uint8 = (rgb * 255).astype(np.uint8)
        
        # Replace NaN with black
        rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0)
        
        # Save as RGB image
        Image.fromarray(rgb_uint8, "RGB").save(output_path)
        print(f"  Saved improved true color image to {output_path}")
        
        return True
    
    except Exception as e:
        print(f"  Error creating true color image: {e}")
        return False

def download_and_process_true_color(date_str, hour, satellite="GOES16", sector="F", 
                                  output_dir=None, advanced=True):
    """
    Main function to download and process improved GOES true color imagery.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        hour: Hour of day (0-23)
        satellite: Satellite name (GOES16 or GOES18)
        sector: Sector code (F=Full Disk, C=CONUS, M=Generic Mesoscale, M1/M2=Specific Mesoscale)
        output_dir: Directory to save output files
        advanced: Whether to use advanced color enhancements
    
    Returns:
        Path to the processed true color image if successful, None otherwise
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
    
    print(f"Downloading GOES true color imagery for {date_str} (DoY {doy}) {hour:02d}:00 UTC")
    print(f"  Satellite: {satellite} ({bucket})")
    print(f"  Product: {product} (sector: {sector})")
    
    # Build S3 prefix
    prefix = build_s3_prefix(product, year, doy, hour)
    
    # We need bands 1, 2, and 3 for true color
    required_bands = [1, 2, 3]
    files_by_band = {}
    
    # Find and download files for each band
    for band in required_bands:
        # Build pattern for this band
        pattern = build_s3_cmip_pattern(sector, band, satellite_num)
        
        # Find files matching pattern
        files = find_s3_files(bucket, prefix, pattern)
        
        if not files:
            print(f"  No files found for Band {band}")
            continue
        
        files_by_band[band] = files
    
    # Check if we have all required bands
    if not all(band in files_by_band for band in required_bands):
        print("  Could not find all required bands for true color")
        return None
    
    # Find a common timestamp across all bands
    timestamp, files_for_timestamp = find_common_timestamp(files_by_band)
    
    if not timestamp:
        print("  No common timestamp found across bands")
        return None
    
    print(f"  Found common timestamp: {timestamp}")
    
    # Download the files
    downloaded_files = {}
    for band, file_key in files_for_timestamp.items():
        file_path = download_s3_file(bucket, file_key, output_dir)
        if file_path:
            downloaded_files[band] = file_path
    
    # Check if we have all files
    if not all(band in downloaded_files for band in required_bands):
        print("  Could not download all required files")
        return None
    
    # Process true color image with improved color science
    mode = "enhanced" if advanced else "standard"
    output_path = output_dir / f"{satellite}_{sector}_truecolor_{mode}_{timestamp}.png"
    success = process_improved_true_color(downloaded_files, output_path, advanced_enhancements=advanced)
    
    if success:
        return output_path
    else:
        return None

def main():
    parser = argparse.ArgumentParser(description="Download and process improved GOES true color imagery")
    parser.add_argument("--date", type=str, default="2023-05-01",
                      help="Date in YYYY-MM-DD format (default: 2023-05-01)")
    parser.add_argument("--hour", type=int, default=19,
                      help="Hour of day in UTC (default: 19)")
    parser.add_argument("--satellite", choices=["GOES16", "GOES18"], default="GOES16",
                      help="Satellite to use (default: GOES16)")
    parser.add_argument("--sector", choices=["F", "C", "M", "M1", "M2"], default="F",
                      help="Sector code (F=Full Disk, C=CONUS, M=Generic Mesoscale, M1/M2=Specific Mesoscale) (default: F)")
    parser.add_argument("--output-dir", type=str, default=None,
                      help="Directory to save output files (default: ~/Downloads/goes_true_color)")
    parser.add_argument("--standard", action="store_true",
                      help="Use standard processing without advanced color enhancements")
    args = parser.parse_args()
    
    # Download and process
    result = download_and_process_true_color(
        args.date,
        args.hour,
        args.satellite,
        args.sector,
        args.output_dir,
        advanced=not args.standard
    )
    
    if result:
        print(f"\nSuccess! Improved true color image saved to:")
        print(f"  {result}")
    else:
        print(f"\nFailed to create true color image")

if __name__ == "__main__":
    main()