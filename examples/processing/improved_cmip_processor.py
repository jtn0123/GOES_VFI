#!/usr/bin/env python3
"""
Improved CMIP processor that handles different bands correctly.
This script processes GOES Level-2 CMIP files into usable images.
"""
import os
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Configuration
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_processed"))
IMAGE_DIR = Path(os.path.expanduser("~/Downloads/goes_images"))
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# Sánchez colormap (LUT) - simple grayscale to color mapping
# In a real application, you would use the actual Sánchez colormap
def create_sanchez_lut():
    """Create a simple Sánchez-like colormap for IR imagery."""
    # This is a simplified version - the real Sánchez colormap is more complex
    colors = [
        [255, 255, 255],  # White (cold)
        [150, 150, 255],  # Light Blue
        [100, 100, 255],  # Blue
        [0, 0, 255],      # Deep Blue
        [0, 255, 255],    # Cyan
        [0, 255, 0],      # Green
        [255, 255, 0],    # Yellow
        [255, 140, 0],    # Orange
        [255, 0, 0],      # Red
        [130, 0, 0]       # Dark Red (hot)
    ]
    
    # Create a 256-entry lookup table
    lut = np.zeros((256, 3), dtype=np.uint8)
    
    # Interpolate colors across the 0-255 range
    num_colors = len(colors)
    for i in range(256):
        # Find position in color scale (0 to num_colors-1)
        position = i / 255 * (num_colors - 1)
        
        # Find the two colors to interpolate between
        idx1 = int(position)
        idx2 = min(idx1 + 1, num_colors - 1)
        frac = position - idx1
        
        # Interpolate
        lut[i] = np.round(np.array(colors[idx1]) * (1 - frac) + np.array(colors[idx2]) * frac).astype(np.uint8)
    
    return lut

# Create the Sánchez LUT
SANCHEZ_LUT = create_sanchez_lut()

def process_ir_image(file_path, output_path):
    """
    Process IR image (Band 13) from a CMIP file.
    
    Args:
        file_path: Path to the NetCDF file
        output_path: Path to save the processed image
    """
    print(f"Processing IR image from {file_path}")
    
    try:
        with xr.open_dataset(file_path) as ds:
            # Extract the CMI data
            ir_data = ds["CMI"].values
            
            # Normalize brightness temperature to 0-255 range
            # Typical IR temperature range is 180K to 320K
            min_temp = np.nanmin(ir_data)
            max_temp = np.nanmax(ir_data)
            
            # If temperature values, use reasonable defaults for GOES IR
            if min_temp > 150 and max_temp < 350:
                print(f"  Temperature range: {min_temp:.1f}K - {max_temp:.1f}K")
                # Invert so cold (high) clouds are white
                ir_norm = 1.0 - ((ir_data - 180) / (320 - 180))
                ir_norm = np.clip(ir_norm, 0, 1)
            else:
                # If reflectance values (0-1), keep as is
                print(f"  Value range: {min_temp:.3f} - {max_temp:.3f}")
                ir_norm = ir_data
            
            # Scale to 0-255
            ir_uint8 = (ir_norm * 255).astype(np.uint8)
            
            # Replace NaN values with 0
            ir_uint8 = np.nan_to_num(ir_uint8, nan=0).astype(np.uint8)
            
            # Create grayscale image
            gray_image = Image.fromarray(ir_uint8, "L")
            gray_image.save(output_path.with_suffix(".gray.png"))
            print(f"  Saved grayscale image to {output_path.with_suffix('.gray.png')}")
            
            # Apply Sánchez colormap
            colored = SANCHEZ_LUT[ir_uint8]
            color_image = Image.fromarray(colored, "RGB")
            color_image.save(output_path)
            print(f"  Saved colorized image to {output_path}")
            
            return True
    except Exception as e:
        print(f"Error processing IR image: {e}")
        return False


def resize_to_match(arrays):
    """
    Resize arrays to match the smallest dimensions.
    This handles the case where different bands have different resolutions.
    """
    # Find minimum dimensions
    min_shape = min(arr.shape for arr in arrays)
    
    # Resize all arrays to match
    resized = []
    for arr in arrays:
        if arr.shape == min_shape:
            resized.append(arr)
        else:
            # Calculate the scaling factor
            y_scale = min_shape[0] / arr.shape[0]
            x_scale = min_shape[1] / arr.shape[1]
            
            # Use PIL for resizing
            img = Image.fromarray(arr.astype(np.float32), mode="F")
            resized_img = img.resize(
                (min_shape[1], min_shape[0]), 
                resample=Image.BILINEAR
            )
            resized.append(np.array(resized_img))
    
    return resized


def process_true_color(file_paths, output_path):
    """
    Process true color image by combining bands 1, 2, and 3.
    
    Args:
        file_paths: Paths to the NetCDF files for bands 1, 2, and 3
        output_path: Path to save the true color image
    """
    if len(file_paths) != 3:
        print(f"Expected 3 files for RGB, got {len(file_paths)}")
        return False
    
    print(f"Processing true color image from 3 files")
    
    try:
        # Load the three band data arrays
        band_data = []
        for file_path in file_paths:
            with xr.open_dataset(file_path) as ds:
                data = ds["CMI"].values
                band_data.append(data)
                print(f"  Loaded {file_path.name}, shape: {data.shape}")
        
        # Resize bands to match (different bands may have different resolutions)
        print("  Resizing bands to match...")
        resized_bands = resize_to_match(band_data)
        
        # Combine into RGB array
        print("  Combining bands into RGB...")
        rgb = np.stack(resized_bands, axis=2)
        
        # Check if values are in reflectance range (0-1)
        if np.nanmax(rgb) <= 1.0:
            # Scale to 0-255
            rgb = (rgb * 255).astype(np.uint8)
        else:
            # Already in 0-255 range
            rgb = rgb.astype(np.uint8)
        
        # Replace NaN values with 0
        rgb = np.nan_to_num(rgb, nan=0).astype(np.uint8)
        
        # Save as RGB image
        Image.fromarray(rgb, "RGB").save(output_path)
        print(f"  Saved true color image to {output_path}")
        
        return True
    except Exception as e:
        print(f"Error processing true color image: {e}")
        return False


def check_for_true_color_composite(file_path):
    """Check if the file has a pre-combined true color composite variable."""
    try:
        with xr.open_dataset(file_path) as ds:
            return "CMI_C01_C02_C03" in ds.variables
    except Exception as e:
        print(f"Error checking for true color composite: {e}")
        return False


def process_true_color_composite(file_path, output_path):
    """
    Process pre-combined true color composite from a CMIP file.
    
    Args:
        file_path: Path to the NetCDF file
        output_path: Path to save the true color image
    """
    print(f"Processing pre-combined true color image from {file_path}")
    
    try:
        with xr.open_dataset(file_path) as ds:
            # Check if the variable exists
            if "CMI_C01_C02_C03" in ds.variables:
                # Extract the RGB data
                rgb = ds["CMI_C01_C02_C03"].values
                
                # Transpose to get H,W,3 format
                if rgb.shape[0] == 3:
                    rgb = rgb.transpose(1, 2, 0)
                
                # Scale if in reflectance range
                if np.nanmax(rgb) <= 1.0:
                    rgb = (rgb * 255).astype(np.uint8)
                else:
                    rgb = rgb.astype(np.uint8)
                
                # Replace NaN values with 0
                rgb = np.nan_to_num(rgb, nan=0).astype(np.uint8)
                
                # Save as RGB image
                Image.fromarray(rgb, "RGB").save(output_path)
                print(f"  Saved true color image to {output_path}")
                
                return True
            else:
                print("  No true color composite found in file")
                return False
    except Exception as e:
        print(f"Error processing true color composite: {e}")
        return False


def find_files_by_band(directory):
    """
    Find CMIP files in the specified directory and group them by band.
    
    Args:
        directory: Directory containing CMIP files
        
    Returns:
        Dictionary mapping band numbers to file paths
    """
    files_by_band = {}
    
    for product_dir in directory.glob("GOES*/*/"):
        print(f"Scanning {product_dir}")
        
        for file_path in product_dir.glob("*.nc"):
            # Extract band number from filename
            if "M6C" in file_path.name:
                band_str = file_path.name.split("-M6C")[1].split("_")[0]
                if band_str and band_str.isdigit():
                    band = int(band_str)
                    if band not in files_by_band:
                        files_by_band[band] = []
                    files_by_band[band].append(file_path)
    
    # Print summary
    if files_by_band:
        print("\nFiles found by band:")
        for band, files in sorted(files_by_band.items()):
            print(f"  Band {band}: {len(files)} files")
    else:
        print("No files found")
    
    return files_by_band


def main():
    """Process all downloaded CMIP files into images."""
    print(f"Processing CMIP files from {DOWNLOAD_DIR}")
    
    # Find files by band
    files_by_band = find_files_by_band(DOWNLOAD_DIR)
    
    # Process IR images (Band 13)
    if 13 in files_by_band:
        print("\nProcessing IR images (Band 13):")
        for file_path in files_by_band[13]:
            # Create output path
            product = file_path.parent.name
            satellite = file_path.parent.parent.name
            output_dir = IMAGE_DIR / satellite / product
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract timestamp from filename
            if "_s" in file_path.name:
                timestamp = file_path.name.split("_s")[1].split("_")[0]
                output_name = f"{satellite}_{product}_{timestamp}_IR_sanchez.png"
            else:
                output_name = f"{satellite}_{product}_IR_sanchez.png"
            
            output_path = output_dir / output_name
            process_ir_image(file_path, output_path)
    
    # Process true color images (Bands 1, 2, 3)
    bands_for_true_color = [1, 2, 3]
    if all(band in files_by_band for band in bands_for_true_color):
        print("\nProcessing true color images:")
        
        # Group files by product and timestamp
        product_groups = {}
        
        for band in bands_for_true_color:
            for file_path in files_by_band[band]:
                product = file_path.parent.name
                satellite = file_path.parent.parent.name
                
                # Extract timestamp from filename
                if "_s" in file_path.name:
                    timestamp = file_path.name.split("_s")[1].split("_")[0]
                    key = (satellite, product, timestamp)
                    
                    if key not in product_groups:
                        product_groups[key] = {}
                    
                    product_groups[key][band] = file_path
        
        # Process each group
        for (satellite, product, timestamp), band_files in product_groups.items():
            # Check if we have all bands
            if all(band in band_files for band in bands_for_true_color):
                output_dir = IMAGE_DIR / satellite / product
                output_dir.mkdir(parents=True, exist_ok=True)
                
                output_name = f"{satellite}_{product}_{timestamp}_TrueColor.png"
                output_path = output_dir / output_name
                
                # Get files in band order
                files = [band_files[band] for band in bands_for_true_color]
                process_true_color(files, output_path)
    
    print("\nAll processing complete. Images saved to:")
    print(IMAGE_DIR)


if __name__ == "__main__":
    main()