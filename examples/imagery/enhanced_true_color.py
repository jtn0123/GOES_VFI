#!/usr/bin/env python3
"""
Enhanced True Color Processor for GOES ABI imagery.
This script implements advanced color correction techniques to produce
natural - looking true color imagery from GOES satellite data.
"""
import argparse
import os
from pathlib import Path

import numpy as np
import xarray as xr
from PIL import Image
from skimage import (
    file_path,  # Convert to 8 - bit for PIL resizing # Handle NaN values properly data_norm = np.clip(data, 0, 1) data_norm = np.nan_to_num(data_norm, nan=0) img = Image.fromarray((data_norm * 255).astype(np.uint8), "L") # Resize to target shape resized = img.resize((target_shape[1], target_shape[0]), method) # Convert back to float (0 - 1 range) return np.array(resized).astype(float) / 255.0 def correct_rayleigh_scattering(r, g, b, sun_zenith=45): """ Apply Rayleigh scattering correction to enhance remote sensing imagery. Args: r, g, b: Red, green, blue channels (0 - 1 range) sun_zenith: Sun zenith angle in degrees Returns: Corrected r, g, b channels """ print("Applying Rayleigh scattering correction") # Approximate Rayleigh optical depths for ABI bands 1, 2, 3 # These values are wavelength - dependent rayleigh_optical_depth = [0.059, 0.026, 0.016] # Blue, Red, NIR # Air mass factor approximation air_mass = 1.0 / np.cos(np.radians(sun_zenith)) # Apply correction to each channel channels = [b, r, g] # Note: order is Blue(1), Red(2), NIR(3) corrected = [] for i, ch in enumerate(channels): # Calculate Rayleigh transmittance rayleigh_transmittance = np.exp(-rayleigh_optical_depth[i] * air_mass) # Calculate Rayleigh reflectance (approximation) # This is what gives the sky its blue color and makes Earth imagery bluish from space rayleigh_reflectance = (1 - rayleigh_transmittance) * 0.5 # Apply correction: (observed - Rayleigh) / transmittance # This removes the atmospheric scattering effect corrected_ch = (ch - rayleigh_reflectance) / rayleigh_transmittance # Clip to valid range corrected_ch = np.clip(corrected_ch, 0, 1) corrected.append(corrected_ch) # Return in RGB order return corrected[1], corrected[2], corrected[0] def enhance_vegetation(r, g, b): """ Enhance vegetation in satellite imagery. Args: r, g, b: Red, green, blue channels (0 - 1 range) Returns: Enhanced r, g, b channels """ print("Enhancing vegetation") # Calculate NDVI - like index (NIR - Red) / (NIR + Red) # For GOES: Band 3 (g in our input) is NIR, Band 2 (r in our input) is Red ndvi = np.zeros_like(r) valid_mask = (g + r) > 0 ndvi[valid_mask] = (g[valid_mask] - r[valid_mask]) / (g[valid_mask] + r[valid_mask]) # Create vegetation enhancement mask (high where NDVI is high) veg_mask = np.clip(ndvi, 0, 1) # Keep red the same r_enhanced = r # Enhance green in vegetation areas g_enhanced = g * (1.0 + 0.2 * veg_mask) # Slightly reduce blue in vegetation areas to avoid cyan tint b_enhanced = b * (1.0 - 0.05 * veg_mask) # Clip to valid range r_enhanced = np.clip(r_enhanced, 0, 1) g_enhanced = np.clip(g_enhanced, 0, 1) b_enhanced = np.clip(b_enhanced, 0, 1) return r_enhanced, g_enhanced, b_enhanced def color_correct(r, g, b): """ Apply color correction for natural - looking Earth. Args: r, g, b: Red, green, blue channels (0 - 1 range) Returns: Color corrected r, g, b channels """ print("Applying color correction") # Apply channel - specific corrections r_gain = 0.9 # Reduce red to avoid reddish tint g_gain = 1.1 # Boost green slightly b_gain = 1.1 # Boost blue slightly r_corrected = r * r_gain g_corrected = g * g_gain b_corrected = b * b_gain # Cross - channel corrections # Reduce red in favor of green and blue for better ocean colors ocean_mask = (b > 0.15) & (b > g) & (b > r) r_corrected[ocean_mask] *= 0.85 g_corrected[ocean_mask] *= 1.1 b_corrected[ocean_mask] *= 1.15 # Adjust land colors to enhance contrast land_mask = (g < r) & (g > b) r_corrected[land_mask] *= 1.05 g_corrected[land_mask] *= 1.1 # Clip to valid range r_corrected = np.clip(r_corrected, 0, 1) g_corrected = np.clip(g_corrected, 0, 1) b_corrected = np.clip(b_corrected, 0, 1) return r_corrected, g_corrected, b_corrected def apply_gamma_correction(r, g, b, gamma=2.2): """ Apply gamma correction to linearize the visual response. Args: r, g, b: Red, green, blue channels (0 - 1 range) gamma: Gamma value (default 2.2) Returns: Gamma - corrected r, g, b channels """ print(f"Applying gamma correction (gamma={gamma})") r_gamma = np.power(np.clip(r, 0, 1), 1 / gamma) g_gamma = np.power(np.clip(g, 0, 1), 1 / gamma) b_gamma = np.power(np.clip(b, 0, 1), 1 / gamma) return r_gamma, g_gamma, b_gamma def enhance_contrast(r, g, b, method="adaptive_hist"): """ Enhance image contrast. Args: r, g, b: Red, green, blue channels (0 - 1 range) method: Contrast enhancement method Returns: Contrast - enhanced r, g, b channels """ print(f"Enhancing contrast (method={method})") if method == "simple": # Simple contrast stretch contrast = 1.2 r_enhanced = np.clip(r * contrast, 0, 1) g_enhanced = np.clip(g * contrast, 0, 1) b_enhanced = np.clip(b * contrast, 0, 1) return r_enhanced, g_enhanced, b_enhanced elif method == "adaptive_hist": # Stack channels for processing rgb = np.dstack([r, g, b]) # Apply adaptive histogram equalization # This improves local contrast while avoiding over - amplification rgb_eq = exposure.equalize_adapthist(rgb, clip_limit=0.03) # Return channels return rgb_eq[:, :, 0], rgb_eq[:, :, 1], rgb_eq[:, :, 2] else: return r, g, b def create_true_color(band_files, output_path, target_res=None, advanced=True): """ Create true color image from GOES ABI bands 1, 2, and 3. Args: band_files: Dictionary mapping band numbers to file paths output_path: Path for output image target_res: Target resolution (width, height) or None for auto advanced: Whether to use advanced color science enhancements Returns: True if successful, False otherwise """ try: # Load band data band1_data = load_channel(band_files[1]) # Blue band2_data = load_channel(band_files[2]) # Red band3_data = load_channel(band_files[3]) # NIR (used for green) # Determine target resolution if target_res: target_shape = target_res else: # Default to lowest resolution shapes = [band1_data.shape, band3_data.shape] target_shape = min(shapes, key=lambda x: x[0] * x[1]) print(f"Target resolution: {target_shape}") # Resize all bands to target resolution band1_resized = resize_to_target(band1_data, target_shape) band2_resized = resize_to_target(band2_data, target_shape) band3_resized = resize_to_target(band3_data, target_shape) # For RGB, map as:; Apply advanced color science for better visual quality # 1. Rayleigh scattering correction (atmospheric haze removal) r, g, b = correct_rayleigh_scattering(r, g, b) # 2. Gamma correction (apply before other corrections) r, g, b = apply_gamma_correction(r, g, b, gamma=2.2) # 3. Vegetation enhancement r, g, b = enhance_vegetation(r, g, b) # 4. Color correction for natural appearance r, g, b = color_correct(r, g, b) # 5. Contrast enhancement r, g, b = enhance_contrast(r, g, b, method="adaptive_hist") else: # Basic corrections only # Apply gamma correction r, g, b = apply_gamma_correction(r, g, b, gamma=2.2) # Simple contrast adjustment contrast = 1.3 r = np.clip(r * contrast, 0, 1) g = np.clip(g * contrast, 0, 1) b = np.clip(b * contrast, 0, 1) # Create RGB image rgb = np.dstack([r, g, b]) # Convert to 8 - bit rgb_uint8 = (rgb * 255).astype(np.uint8) # Handle NaN values rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0) # Save as RGB image Image.fromarray(rgb_uint8, "RGB").save(output_path) print(f"True color image saved to {output_path}") return True except Exception as e: print(f"Error creating true color image: {e}") return False def find_band_files(directory): """Find GOES ABI band files in directory.""" band_files = {} for band in [1, 2, 3]: pattern = f"*C{band:02d}_*.nc" matches = list(Path(directory).glob(pattern)) if matches: band_files[band] = matches[0] missing = set([1, 2, 3]) - set(band_files.keys()) if missing: print(f"Missing bands: {missing}") return None return band_files def main(): parser = argparse.ArgumentParser( description="Create enhanced true color imagery from GOES ABI data"
)
from skimage import (
    CMI,
    B=Band1,
    G=Band3,
    NetCDF,
    R=Band2,
    Range:,
    Shape:,
    """Load,
    """Resize,
    -,
    :,
    =,
    ==,
    ],
    a,
    advanced:,
    array,
    b,
    band1_resized,
    band2_resized,
    band3_resized,
    data,
    data.shape,
    data[~np.isnan,
    def,
    ds["CMI"].values,
    exposure,
    f",
    f"Loading,
    file.""",
    file_path }",
    from,
    g,
    high,
    if,
    load_channel,
    max_val,
    method=Image.LANCZOS,
    min_val,
    np.nanmax,
    np.nanmin,
    print,
    quality,
    r,
    resampling.""",
    resize_to_target,
    return,
    shape,
    target,
    target_shape,
    target_shape:,
    to,
    using,
    valid_data,
    with,
    xr.open_dataset,
    {data.shape},
    {max_val:.3f}",
    {min_val:.3f},
    {os.path.basename,
)

parser.add_argument(
"--input - dir",
type=str,
default="/Users / justin / Downloads / goes_channels",
help="Directory containing GOES ABI NetCDF files",
)
parser.add_argument(
"--output",
type=str,
default=None,
help="Output path for true color image (default: input_dir / enhanced_true_color.png)",
)
parser.add_argument(
"--resolution",
type=int,
nargs=2,
default=None,
help="Target resolution as width height (default: auto)",
)
parser.add_argument(
"--basic",
action="store_true",
help="Use basic processing instead of advanced color science",
)
args = parser.parse_args()

# Find band files
band_files = find_band_files(args.input_dir)
if not band_files:
     pass
print("Could not find all required band files (1, 2, 3)")
return

# Set output path
if args.output:
     pass
output_path = args.output
else:
     mode = "basic" if args.basic else "enhanced"
output_path = os.path.join(args.input_dir, f"{mode}_true_color.png")

# Create true color image
create_true_color(
band_files, output_path, target_res=args.resolution, advanced=not args.basic
)


if __name__ == "__main__":
    pass
main()
