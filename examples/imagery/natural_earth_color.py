#!/usr/bin/env python3
"""
Natural Earth Color Processor for GOES ABI imagery.
This script creates true-to-life Earth colors from GOES ABI data
using specialized color science techniques used by NASA and NOAA.
"""
import argparse
import os
from pathlib import Path

import numpy as np
import xarray as xr
from PIL import Image
from skimage import color, exposure


def load_channel(file_path):
    """Load CMI data from a NetCDF file."""
    print(f"Loading {os.path.basename(file_path)}")
    with xr.open_dataset(file_path) as ds:
        data = ds["CMI"].values
        valid_data = data[~np.isnan(data)]
        min_val = np.nanmin(valid_data)
        max_val = np.nanmax(valid_data)
        print(f"  Shape: {data.shape}, Range: {min_val:.3f} - {max_val:.3f}")
        return data


def resize_array(data, target_shape):
    """Resize data array with high quality resampling."""
    if data.shape == target_shape:
        return data

    # Handle NaN values
    data_clean = np.nan_to_num(data, nan=0)

    # Convert to 8-bit for PIL
    data_norm = np.clip(data_clean, 0, 1) * 255
    img = Image.fromarray(data_norm.astype(np.uint8), "L")

    # Resize with LANCZOS for better quality
    img_resized = img.resize((target_shape[1], target_shape[0]), Image.LANCZOS)

    # Convert back to float 0-1 range
    return np.array(img_resized).astype(float) / 255.0


def preprocess_bands(r_data, g_data, b_data, target_shape=None):
    """
    Preprocess and resize bands to common dimensions.

    Args:
        r_data, g_data, b_data: Band data arrays
        target_shape: Target shape or None to use smallest shape

    Returns:
        Preprocessed r, g, b arrays at consistent dimensions
    """
    # Determine target shape if not specified
    if target_shape is None:
        shapes = [r_data.shape, g_data.shape, b_data.shape]
        target_shape = min(shapes, key=lambda x: x[0] * x[1])

    print(f"Resizing bands to {target_shape}")

    # Resize all bands to target shape
    r_resized = resize_array(r_data, target_shape)
    g_resized = resize_array(g_data, target_shape)
    b_resized = resize_array(b_data, target_shape)

    return r_resized, g_resized, b_resized


def corrected_reflectance(data, band_num):
    """
    Apply band-specific corrections to raw reflectance data.

    Args:
        data: Raw reflectance data
        band_num: Band number (1=Blue, 2=Red, 3=NIR)

    Returns:
        Corrected reflectance data
    """
    # Clip to standard reflectance range
    data_clipped = np.clip(data, 0, 1.0)

    # Apply band-specific scale adjustment for better histogram
    scale_factor = 1.0
    if band_num == 1:  # Blue
        scale_factor = 0.9  # Slightly reduce blue
    elif band_num == 2:  # Red
        scale_factor = 0.9  # Slightly reduce red
    elif band_num == 3:  # NIR (used for green)
        scale_factor = 1.1  # Boost green

    return data_clipped * scale_factor


def correct_atmosphere(r, g, b):
    """
    Apply atmospheric correction based on NASA imagery techniques.

    Args:
        r, g, b: Red, green, blue channels (0-1 range)

    Returns:
        Atmosphere-corrected r, g, b channels
    """
    print("Applying NASA-style atmospheric correction")

    # Rayleigh scattering correction constants
    # These values are approximated from empirical corrections used in Earth imaging
    blue_correction = 0.08  # Stronger correction for blue
    red_correction = 0.02  # Minimal correction for red
    green_correction = 0.03  # Light correction for NIR-based green

    # Apply corrections by subtracting scattering component
    # This effectively removes the atmospheric haze
    r_corr = np.maximum(0, r - red_correction)
    g_corr = np.maximum(0, g - green_correction)
    b_corr = np.maximum(0, b - blue_correction)

    # Renormalize after correction
    r_max = np.nanmax(r_corr)
    g_max = np.nanmax(g_corr)
    b_max = np.nanmax(b_corr)

    if r_max > 0:
        r_corr = r_corr / r_max
    if g_max > 0:
        g_corr = g_corr / g_max
    if b_max > 0:
        b_corr = b_corr / b_max

    return r_corr, g_corr, b_corr


def make_realistic_green(r, nir):
    """
    Create realistic green channel from red and NIR bands.

    This simulates the green vegetation response that the ABI sensor
    doesn't directly measure with its band selection.

    Args:
        r: Red band data (Band 2)
        nir: Near-IR band data (Band 3)

    Returns:
        Synthetic green channel
    """
    print("Creating realistic green channel from Red+NIR")

    # The green channel is a weighted combination of NIR and Red
    # This approach is similar to how EPIC and other Earth-observing instruments
    # create green channels when they don't have a dedicated green band

    # NDVI-based weight (higher NDVI = more plant influence)
    ndvi = np.zeros_like(r)
    valid_mask = (nir + r) > 0
    ndvi[valid_mask] = (nir[valid_mask] - r[valid_mask]) / (
        nir[valid_mask] + r[valid_mask]
    )

    # Normalize NDVI to 0-1 and create weighted sum
    ndvi_norm = np.clip((ndvi + 1) / 2, 0, 1)

    # Green channel is primarily NIR for vegetation and otherwise influenced by red
    green = 0.45 * nir + 0.1 * r + 0.45 * ndvi_norm

    # Normalize output
    return np.clip(green, 0, 1)


def apply_earth_color_balance(r, g, b):
    """
    Apply Earth-specific color balance to make oceans, land, and clouds look natural.

    Args:
        r, g, b: Red, green, blue channels (0-1 range)

    Returns:
        Color-balanced r, g, b channels
    """
    print("Applying Earth-specific color balance")

    # Create masks for different surface types
    # These are approximate based on simple spectral properties

    # Water (high in blue, low in others)
    water_mask = (b > 0.2) & (b > r * 1.5) & (b > g * 1.2)

    # Vegetation (high in green, higher in NIR/green than red)
    veg_mask = (g > 0.2) & (g > r * 1.2) & (g > b * 1.3)

    # Land (mid-range in red and green, lower in blue)
    land_mask = (r > 0.2) & (g > 0.2) & (r > b * 1.2) & (g > b * 1.2) & ~veg_mask

    # Cloud/snow/ice (high in all bands)
    cloud_mask = (r > 0.7) & (g > 0.7) & (b > 0.7)

    # 1. Enhance water color - deeper blue
    r_balanced = r.copy()
    g_balanced = g.copy()
    b_balanced = b.copy()

    r_balanced[water_mask] *= 0.75
    g_balanced[water_mask] *= 0.9
    b_balanced[water_mask] *= 1.15

    # 2. Enhance vegetation - more vibrant green
    r_balanced[veg_mask] *= 0.9
    g_balanced[veg_mask] *= 1.15
    b_balanced[veg_mask] *= 0.8

    # 3. Enhance land - warmer tones
    r_balanced[land_mask] *= 1.1
    g_balanced[land_mask] *= 1.05
    b_balanced[land_mask] *= 0.9

    # 4. Enhance clouds - pure white
    cloud_strength = 0.8  # Control cloud enhancement strength
    r_balanced[cloud_mask] = (
        r_balanced[cloud_mask] * (1 - cloud_strength) + cloud_strength
    )
    g_balanced[cloud_mask] = (
        g_balanced[cloud_mask] * (1 - cloud_strength) + cloud_strength
    )
    b_balanced[cloud_mask] = (
        b_balanced[cloud_mask] * (1 - cloud_strength) + cloud_strength
    )

    # Ensure valid range
    r_balanced = np.clip(r_balanced, 0, 1)
    g_balanced = np.clip(g_balanced, 0, 1)
    b_balanced = np.clip(b_balanced, 0, 1)

    return r_balanced, g_balanced, b_balanced


def apply_final_enhancements(r, g, b):
    """
    Apply final visual enhancements for a polished Earth image.

    Args:
        r, g, b: Red, green, blue channels (0-1 range)

    Returns:
        Enhanced r, g, b channels
    """
    print("Applying final visual enhancements")

    # Convert to more perceptual LAB colorspace for better enhancement
    rgb = np.dstack([r, g, b])
    lab = color.rgb2lab(rgb)

    # Extract lightness channel (L) and enhance contrast
    l_channel = lab[:, :, 0] / 100.0  # Scale to 0-1

    # Apply contrast enhancement to lightness
    p2, p98 = np.percentile(l_channel[~np.isnan(l_channel)], (2, 98))
    l_rescaled = exposure.rescale_intensity(l_channel, in_range=(p2, p98))

    # Replace lightness channel in LAB
    lab[:, :, 0] = l_rescaled * 100.0

    # Enhance colorfulness (a* and b* channels)
    saturation_factor = 1.1
    lab[:, :, 1] = lab[:, :, 1] * saturation_factor
    lab[:, :, 2] = lab[:, :, 2] * saturation_factor

    # Convert back to RGB
    rgb_enhanced = color.lab2rgb(lab)

    # Final gamma adjustment to improve overall tone
    gamma = 1.1
    rgb_enhanced = np.power(rgb_enhanced, 1 / gamma)

    # Ensure valid range
    rgb_enhanced = np.clip(rgb_enhanced, 0, 1)

    return rgb_enhanced[:, :, 0], rgb_enhanced[:, :, 1], rgb_enhanced[:, :, 2]


def create_natural_earth_color(
    band_files, output_path, target_shape=None, minimal=False
):
    """
    Create natural Earth color image from GOES ABI bands.

    Args:
        band_files: Dictionary mapping band numbers to file paths
        output_path: Path for output image
        target_shape: Target resolution (height, width) or None for auto
        minimal: If True, use minimal processing

    Returns:
        True if successful, False otherwise
    """
    try:
        # Load and prepare bands
        band1 = load_channel(band_files[1])  # Blue
        band2 = load_channel(band_files[2])  # Red
        band3 = load_channel(band_files[3])  # NIR

        # Apply preliminary band corrections
        band1_corr = corrected_reflectance(band1, 1)
        band2_corr = corrected_reflectance(band2, 2)
        band3_corr = corrected_reflectance(band3, 3)

        # Resize to target resolution
        r, g, b = preprocess_bands(band2_corr, band3_corr, band1_corr, target_shape)

        if minimal:
            # Minimal processing path
            print("Using minimal processing pipeline")

            # For minimal processing, use simple band assignment with gamma
            g = make_realistic_green(r, g)  # Convert NIR to realistic green

            # Apply gamma correction
            gamma = 2.2
            r = np.power(np.clip(r, 0, 1), 1 / gamma)
            g = np.power(np.clip(g, 0, 1), 1 / gamma)
            b = np.power(np.clip(b, 0, 1), 1 / gamma)

            # Simple contrast enhancement
            contrast = 1.2
            r = np.clip(r * contrast, 0, 1)
            g = np.clip(g * contrast, 0, 1)
            b = np.clip(b * contrast, 0, 1)
        else:
            # Full processing pipeline
            print("Using full processing pipeline")

            # Create realistic green from NIR and Red
            g = make_realistic_green(r, g)

            # Apply NASA-style atmospheric correction
            r, g, b = correct_atmosphere(r, g, b)

            # Apply Earth-specific color balance
            r, g, b = apply_earth_color_balance(r, g, b)

            # Apply gamma correction (standard value of 2.2)
            gamma = 2.2
            r = np.power(np.clip(r, 0, 1), 1 / gamma)
            g = np.power(np.clip(g, 0, 1), 1 / gamma)
            b = np.power(np.clip(b, 0, 1), 1 / gamma)

            # Apply final visual enhancements
            r, g, b = apply_final_enhancements(r, g, b)

        # Create RGB image
        rgb = np.dstack([r, g, b])

        # Handle NaN values
        rgb = np.nan_to_num(rgb, nan=0)

        # Convert to 8-bit
        rgb_uint8 = (rgb * 255).astype(np.uint8)

        # Save image
        Image.fromarray(rgb_uint8, "RGB").save(output_path)
        print(f"Natural Earth color image saved to {output_path}")

        return True

    except Exception as e:
        print(f"Error creating natural Earth color image: {e}")
        return False


def find_band_files(directory):
    """Find GOES ABI band files in directory."""
    band_files = {}
    for band in [1, 2, 3]:
        pattern = f"*C{band:02d}_*.nc"
        matches = list(Path(directory).glob(pattern))
        if matches:
            band_files[band] = matches[0]

    missing = set([1, 2, 3]) - set(band_files.keys())
    if missing:
        print(f"Missing bands: {missing}")
        return None

    return band_files


def main():
    parser = argparse.ArgumentParser(
        description="Create natural Earth color imagery from GOES ABI data"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="/Users/justin/Downloads/goes_channels",
        help="Directory containing GOES ABI NetCDF files",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for image (default: input_dir/natural_earth_color.png)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        nargs=2,
        default=[2000, 2000],
        help="Target resolution as height width (default: 2000 2000)",
    )
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Use minimal processing instead of full pipeline",
    )
    args = parser.parse_args()

    # Find band files
    band_files = find_band_files(args.input_dir)
    if not band_files:
        print("Could not find all required band files (1, 2, 3)")
        return

    # Set output path
    if args.output:
        output_path = args.output
    else:
        mode = "minimal" if args.minimal else "natural"
        output_path = os.path.join(args.input_dir, f"{mode}_earth_color.png")

    # Create natural Earth color image
    create_natural_earth_color(
        band_files, output_path, target_shape=args.resolution, minimal=args.minimal
    )


if __name__ == "__main__":
    main()
