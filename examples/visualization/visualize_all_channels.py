#!/usr/bin/env python3
"""
Visualize all 16 GOES ABI channels from downloaded NetCDF files.
This script processes and creates images from each channel with appropriate visualization techniques.
"""
import os
from pathlib import Path
import xarray as xr
import numpy as np
from PIL import Image
import glob
import argparse
from matplotlib import cm

def process_visible_channel(file_path, output_path, gamma=2.2, contrast=1.5):
    """Process a visible/near-IR channel (reflectance data)"""
    print(f"Processing visible/near-IR: {os.path.basename(file_path)}")
    
    try:
        with xr.open_dataset(file_path) as ds:
            # Extract the CMI data (reflectance)
            data = ds["CMI"].values
            
            # Get actual range
            valid_data = data[~np.isnan(data)]
            actual_min = np.min(valid_data)
            actual_max = np.max(valid_data)
            print(f"  Value range: {actual_min:.3f} - {actual_max:.3f}")
            
            # Normalize and apply gamma correction
            data_norm = np.clip(data, 0, 1)  # Clip to 0-1 range
            data_gamma = np.power(data_norm, 1/gamma)
            
            # Apply contrast enhancement
            data_contrast = np.clip(data_gamma * contrast, 0, 1)
            
            # Convert to 8-bit for image
            data_uint8 = (data_contrast * 255).astype(np.uint8)
            
            # Replace NaNs with black
            data_uint8 = np.nan_to_num(data_uint8, nan=0)
            
            # Save as grayscale image
            Image.fromarray(data_uint8, "L").save(output_path)
            print(f"  Saved to: {output_path}")
            
            return True
    except Exception as e:
        print(f"  Error processing {file_path}: {e}")
        return False

def process_ir_channel(file_path, output_path, min_temp=180, max_temp=320, colormap=None):
    """Process an IR channel (brightness temperature data)"""
    print(f"Processing IR: {os.path.basename(file_path)}")
    
    try:
        with xr.open_dataset(file_path) as ds:
            # Extract the CMI data (brightness temperature)
            data = ds["CMI"].values
            
            # Get actual range
            valid_data = data[~np.isnan(data)]
            actual_min = np.min(valid_data)
            actual_max = np.max(valid_data)
            print(f"  Temperature range: {actual_min:.1f}K - {actual_max:.1f}K")
            
            # If max_temp looks too low for this data, adjust it
            if actual_max > max_temp + 30:
                adjusted_max = min(actual_max, 400)  # Cap at 400K to handle fires
                print(f"  Adjusting max temp from {max_temp}K to {adjusted_max}K")
                max_temp = adjusted_max
            
            # Normalize temperature to 0-1 range (invert: cold=bright, warm=dark for standard IR)
            # Cold clouds = bright white, warm surface = dark for standard IR
            data_norm = 1.0 - ((data - min_temp) / (max_temp - min_temp))
            data_norm = np.clip(data_norm, 0, 1)
            
            # Replace NaNs with 0
            data_norm = np.nan_to_num(data_norm, nan=0)
            
            if colormap:
                # Use matplotlib colormap
                try:
                    cmap = cm.get_cmap(colormap)
                    colored_data = cmap(data_norm)
                    
                    # Convert to 8-bit for PNG
                    colored_uint8 = (colored_data[:, :, :3] * 255).astype(np.uint8)
                    
                    # Save as RGB image
                    Image.fromarray(colored_uint8, "RGB").save(output_path)
                except Exception as e:
                    print(f"  Error applying colormap: {e}")
                    # Fall back to grayscale
                    data_uint8 = (data_norm * 255).astype(np.uint8)
                    Image.fromarray(data_uint8, "L").save(output_path)
            else:
                # Standard grayscale
                data_uint8 = (data_norm * 255).astype(np.uint8)
                Image.fromarray(data_uint8, "L").save(output_path)
                
            print(f"  Saved to: {output_path}")
            
            return True
    except Exception as e:
        print(f"  Error processing {file_path}: {e}")
        return False

def get_band_from_filename(filename):
    """Extract the band number from GOES filename."""
    import re
    match = re.search(r'C(\d{2})_', filename)
    if match:
        return int(match.group(1))
    return None

def create_true_color(bands_path, output_path):
    """Create a true color image from bands 1, 2, 3."""
    print("Creating true color image from bands 1, 2, 3")
    
    # Find the band files
    band_files = {}
    for band_num in [1, 2, 3]:
        pattern = f"*C{band_num:02d}_*.nc"
        matches = list(Path(bands_path).glob(pattern))
        if matches:
            band_files[band_num] = matches[0]
    
    if len(band_files) != 3:
        print(f"  Error: Could not find all three RGB bands. Found: {band_files.keys()}")
        return False
    
    # Process true color
    try:
        # Load the three band data arrays
        band_data = []
        band_shapes = []
        
        for band, file_path in sorted(band_files.items()):
            with xr.open_dataset(file_path) as ds:
                data = ds["CMI"].values
                band_data.append(data)
                band_shapes.append(data.shape)
                print(f"  Loaded Band {band} from {file_path.name}")
                print(f"    Shape: {data.shape}, Range: {np.nanmin(data):.3f} - {np.nanmax(data):.3f}")
        
        # Check if arrays have the same shape
        if len(set(tuple(shape) for shape in band_shapes)) > 1:
            print(f"  Bands have different shapes: {band_shapes}")
            print("  Resizing to match smallest dimensions...")
            
            # Find the smallest dimensions
            min_height = min(shape[0] for shape in band_shapes)
            min_width = min(shape[1] for shape in band_shapes)
            
            # Resize all bands to the smallest shape
            resized_bands = []
            for i, data in enumerate(band_data):
                if data.shape[0] == min_height and data.shape[1] == min_width:
                    resized_bands.append(data)
                else:
                    # Use simple resize method
                    h_ratio = min_height / data.shape[0]
                    w_ratio = min_width / data.shape[1]
                    
                    # Convert to 8-bit for PIL resizing
                    img = Image.fromarray(np.clip(data, 0, 1) * 255).convert('L')
                    img = img.resize((min_width, min_height), Image.LANCZOS)
                    
                    # Convert back to 0-1 range
                    resized = np.array(img).astype(float) / 255.0
                    resized_bands.append(resized)
            
            band_data = resized_bands
        
        # Apply Rayleigh scattering correction
        rayleigh_optical_depth = [0.059, 0.026, 0.016]
        sun_zenith = 45  # Approximate sun zenith angle
        air_mass = 1.0 / np.cos(np.radians(sun_zenith))
        
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
        
        # Apply gamma correction and color balance
        gamma = 2.2
        r_gain, g_gain, b_gain = 1.0, 0.97, 0.93  # Adjusted color balance
        
        r = np.power(np.clip(corrected_data[0], 0, 1), 1/gamma) * r_gain
        g = np.power(np.clip(corrected_data[1], 0, 1), 1/gamma) * g_gain
        b = np.power(np.clip(corrected_data[2], 0, 1), 1/gamma) * b_gain
        
        # Apply contrast enhancement
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
        print(f"  Saved true color image to {output_path}")
        
        return True
    
    except Exception as e:
        print(f"  Error creating true color image: {e}")
        return False

def create_derived_products(bands_path, output_dir):
    """Create specialized RGB composites and other derived products."""
    # Directory for derived products
    derived_dir = Path(output_dir) / "derived_products"
    derived_dir.mkdir(exist_ok=True)
    
    products = {
        "true_color": {
            "bands": [1, 2, 3],
            "description": "True Color (Bands 1-2-3)",
            "function": create_true_color
        },
        # Add more specialized products here
    }
    
    for name, info in products.items():
        print(f"\nCreating {name}: {info['description']}")
        output_path = derived_dir / f"{name}.png"
        if info["function"] == create_true_color:
            info["function"](bands_path, output_path)
        # Add more specialized product functions as needed

def visualize_all_channels(input_dir, output_dir=None):
    """
    Process and visualize all ABI channels found in the input directory.
    
    Args:
        input_dir: Directory containing the .nc files
        output_dir: Directory to save output images
    """
    # Configure output directory
    if not output_dir:
        output_dir = Path(input_dir) / "visualized"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all .nc files
    nc_files = list(Path(input_dir).glob("*.nc"))
    
    if not nc_files:
        print(f"No .nc files found in {input_dir}")
        return
    
    print(f"Found {len(nc_files)} NetCDF files")
    
    # Process each file
    for file_path in sorted(nc_files):
        try:
            # Extract band number from filename
            band = None
            filename = file_path.name
            
            # Try different patterns to identify band number
            if "M6C" in filename:
                band = int(filename.split("M6C")[1][:2])
            else:
                continue  # Skip if we can't identify the band
            
            if not band:
                print(f"Couldn't determine band for {filename}, skipping")
                continue
            
            # Different processing based on band type
            # Band 1-6: Visible/Near-IR (Reflectance)
            # Band 7-16: IR (Brightness Temperature)
            
            # Base output filename
            base_output = output_dir / f"band_{band:02d}"
            
            if 1 <= band <= 6:
                # Visible/Near-IR processing
                output_path = f"{base_output}_vis.png"
                process_visible_channel(file_path, output_path)
                
            elif 7 <= band <= 16:
                # IR processing (grayscale)
                output_path = f"{base_output}_ir.png"
                process_ir_channel(file_path, output_path)
                
                # Also create a colored version for IR bands
                if band in [7, 8, 9, 10, 13]:  # Selected bands for colorized versions
                    colormap = "jet"  # Standard colormap for most bands
                    
                    # Band-specific colormaps
                    if band == 7:  # Fire detection (hot spots)
                        colormap = "inferno"
                    elif band == 8:  # Water vapor
                        colormap = "turbo"
                    elif band == 9:  # Water vapor
                        colormap = "plasma" 
                    elif band == 10:  # Water vapor
                        colormap = "viridis"
                        
                    output_path = f"{base_output}_color.png"
                    process_ir_channel(file_path, output_path, colormap=colormap)
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    # Create derived products
    create_derived_products(input_dir, output_dir)
    
    print(f"\nAll files processed. Results saved to {output_dir}")

def main():
    parser = argparse.ArgumentParser(description="Visualize all GOES ABI channels")
    parser.add_argument("--input-dir", type=str, default="/Users/justin/Downloads/goes_channels",
                      help="Directory containing NetCDF files")
    parser.add_argument("--output-dir", type=str, default=None,
                      help="Directory to save output images (default: input_dir/visualized)")
    args = parser.parse_args()
    
    visualize_all_channels(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()