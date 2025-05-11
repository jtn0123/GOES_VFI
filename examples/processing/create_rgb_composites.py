#!/usr/bin/env python3
"""
Create specialized RGB composites from GOES ABI channels.
These composites highlight different meteorological features.
"""
import argparse
import glob
import os
from pathlib import Path

import numpy as np
import xarray as xr
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


def normalize_data(data, min_val, max_val, invert=True):
    """Normalize data to 0-1 range with optional inversion."""
    normalized = (data - min_val) / (max_val - min_val)
    if invert:
        normalized = 1.0 - normalized
    return np.clip(normalized, 0, 1)


def load_channel(file_path):
    """Load CMI data from a NetCDF file."""
    with xr.open_dataset(file_path) as ds:
        return ds["CMI"].values


def create_airmass_rgb(channel_dir, output_path):
    """
    Create an Airmass RGB composite.
    - Red: Band 8 - Band 10 (Upper-Lower WV difference)
    - Green: Band 12 - Band 13 (Ozone - Clean IR difference)
    - Blue: Band 8 (Upper-level WV)
    """
    print("Creating Airmass RGB composite")

    # Find necessary channel files
    bands_needed = [8, 10, 12, 13]
    band_files = {}

    for band in bands_needed:
        pattern = f"OR_ABI-L2-CMIPF-M6C{band:02d}_*.nc"
        matches = list(Path(channel_dir).glob(pattern))
        if matches:
            band_files[band] = matches[0]

    if len(band_files) != len(bands_needed):
        print(f"  Error: Could not find all required bands. Found: {band_files.keys()}")
        return False

    try:
        # Load data
        band8_data = load_channel(band_files[8])
        band10_data = load_channel(band_files[10])
        band12_data = load_channel(band_files[12])
        band13_data = load_channel(band_files[13])

        # Ensure all arrays have the same shape
        shape = band8_data.shape
        for band, data in [(10, band10_data), (12, band12_data), (13, band13_data)]:
            if data.shape != shape:
                print(
                    f"  Error: Band {band} has different shape {data.shape} vs {shape}"
                )
                return False

        # Create difference products and normalize
        # Red: WV upper - WV lower (range: -25K to 0K)
        red_data = band8_data - band10_data
        red_norm = normalize_data(red_data, -25, 0, invert=False)

        # Green: Ozone - Clean IR (range: -40K to 5K)
        green_data = band12_data - band13_data
        green_norm = normalize_data(green_data, -40, 5, invert=False)

        # Blue: Upper-level water vapor (range: 243K to 208K)
        blue_norm = normalize_data(band8_data, 243, 208, invert=False)

        # Create RGB image
        rgb = np.dstack([red_norm, green_norm, blue_norm])
        rgb_uint8 = (rgb * 255).astype(np.uint8)
        rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0)

        # Save image
        Image.fromarray(rgb_uint8, "RGB").save(output_path)
        print(f"  Saved Airmass RGB composite to {output_path}")
        return True

    except Exception as e:
        print(f"  Error creating Airmass RGB: {e}")
        return False


def create_natural_color_rgb(channel_dir, output_path):
    """
    Create a Natural Color RGB composite.
    - Red: Band 2 (Red)
    - Green: Band 3 (Veggie)
    - Blue: Band 1 (Blue)
    """
    print("Creating Natural Color RGB composite")

    # Find necessary channel files
    bands_needed = [1, 2, 3]
    band_files = {}

    for band in bands_needed:
        pattern = f"OR_ABI-L2-CMIPF-M6C{band:02d}_*.nc"
        matches = list(Path(channel_dir).glob(pattern))
        if matches:
            band_files[band] = matches[0]

    if len(band_files) != len(bands_needed):
        print(f"  Error: Could not find all required bands. Found: {band_files.keys()}")
        return False

    try:
        # Load data with automatic resizing to Band 1 resolution
        band1_data = load_channel(band_files[1])
        band2_data = load_channel(band_files[2])
        band3_data = load_channel(band_files[3])

        # Check shapes and resize if needed
        shapes = [band1_data.shape, band2_data.shape, band3_data.shape]
        if len(set(tuple(shape) for shape in shapes)) > 1:
            print(f"  Bands have different shapes: {shapes}")
            print("  Resizing to match Band 1 dimensions")

            # Use Band 1 as reference size
            target_shape = band1_data.shape

            # Process Band 2 (usually higher resolution)
            if band2_data.shape != target_shape:
                # Simple resize method - better to use proper resampling in production
                img = Image.fromarray(np.clip(band2_data, 0, 1) * 255).convert("L")
                img = img.resize((target_shape[1], target_shape[0]), Image.LANCZOS)
                band2_data = np.array(img).astype(float) / 255.0

            # Process Band 3 if needed
            if band3_data.shape != target_shape:
                img = Image.fromarray(np.clip(band3_data, 0, 1) * 255).convert("L")
                img = img.resize((target_shape[1], target_shape[0]), Image.LANCZOS)
                band3_data = np.array(img).astype(float) / 255.0

        # Apply gamma correction
        gamma = 2.2
        r = np.power(np.clip(band2_data, 0, 1), 1 / gamma)  # Red channel from Band 2
        g = np.power(np.clip(band3_data, 0, 1), 1 / gamma)  # Green channel from Band 3
        b = np.power(np.clip(band1_data, 0, 1), 1 / gamma)  # Blue channel from Band 1

        # Apply color correction
        # Adjust green to improve vegetation appearance
        g = g * 1.1

        # Apply contrast enhancement
        contrast = 1.3
        r = np.clip(r * contrast, 0, 1)
        g = np.clip(g * contrast, 0, 1)
        b = np.clip(b * contrast, 0, 1)

        # Create RGB image
        rgb = np.dstack([r, g, b])
        rgb_uint8 = (rgb * 255).astype(np.uint8)
        rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0)

        # Save image
        Image.fromarray(rgb_uint8, "RGB").save(output_path)
        print(f"  Saved Natural Color RGB composite to {output_path}")
        return True

    except Exception as e:
        print(f"  Error creating Natural Color RGB: {e}")
        return False


def create_fire_temperature_rgb(channel_dir, output_path):
    """
    Create a Fire Temperature RGB composite.
    - Red: Band 7 (3.9μm, fire detection)
    - Green: Band 13 (10.3μm, surface features)
    - Blue: Band 15 (12.3μm, ash/dust)
    """
    print("Creating Fire Temperature RGB composite")

    # Find necessary channel files
    bands_needed = [7, 13, 15]
    band_files = {}

    for band in bands_needed:
        pattern = f"OR_ABI-L2-CMIPF-M6C{band:02d}_*.nc"
        matches = list(Path(channel_dir).glob(pattern))
        if matches:
            band_files[band] = matches[0]

    if len(band_files) != len(bands_needed):
        print(f"  Error: Could not find all required bands. Found: {band_files.keys()}")
        return False

    try:
        # Load data
        band7_data = load_channel(band_files[7])
        band13_data = load_channel(band_files[13])
        band15_data = load_channel(band_files[15])

        # Ensure all arrays have the same shape
        shape = band7_data.shape
        for band, data in [(13, band13_data), (15, band15_data)]:
            if data.shape != shape:
                print(
                    f"  Error: Band {band} has different shape {data.shape} vs {shape}"
                )
                return False

        # Normalize channels with fire-optimized ranges
        # Red: 3.9μm - Enhance hot spots (range: 400K to 273K)
        # Use smaller range for red to really enhance fires
        red_norm = normalize_data(band7_data, 400, 273, invert=True)

        # Green: 10.3μm (range: 330K to 200K)
        green_norm = normalize_data(band13_data, 330, 200, invert=True)

        # Blue: 12.3μm (range: 325K to 200K)
        blue_norm = normalize_data(band15_data, 325, 200, invert=True)

        # Create RGB image
        rgb = np.dstack([red_norm, green_norm, blue_norm])
        rgb_uint8 = (rgb * 255).astype(np.uint8)
        rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0)

        # Save image
        Image.fromarray(rgb_uint8, "RGB").save(output_path)
        print(f"  Saved Fire Temperature RGB composite to {output_path}")
        return True

    except Exception as e:
        print(f"  Error creating Fire Temperature RGB: {e}")
        return False


def create_dust_rgb(channel_dir, output_path):
    """
    Create a Dust RGB composite.
    - Red: Band 15 - Band 13 (Split window difference)
    - Green: Band 13 - Band 11 (Clean IR - Cloud Phase difference)
    - Blue: Band 13 (Clean IR)
    """
    print("Creating Dust RGB composite")

    # Find necessary channel files
    bands_needed = [11, 13, 15]
    band_files = {}

    for band in bands_needed:
        pattern = f"OR_ABI-L2-CMIPF-M6C{band:02d}_*.nc"
        matches = list(Path(channel_dir).glob(pattern))
        if matches:
            band_files[band] = matches[0]

    if len(band_files) != len(bands_needed):
        print(f"  Error: Could not find all required bands. Found: {band_files.keys()}")
        return False

    try:
        # Load data
        band11_data = load_channel(band_files[11])
        band13_data = load_channel(band_files[13])
        band15_data = load_channel(band_files[15])

        # Ensure all arrays have the same shape
        shape = band13_data.shape
        for band, data in [(11, band11_data), (15, band15_data)]:
            if data.shape != shape:
                print(
                    f"  Error: Band {band} has different shape {data.shape} vs {shape}"
                )
                return False

        # Create difference products and normalize
        # Red: Split window difference (range: -4K to 2K)
        red_data = band15_data - band13_data
        red_norm = normalize_data(red_data, -4, 2, invert=False)

        # Green: IR difference (range: -4K to 5K)
        green_data = band13_data - band11_data
        green_norm = normalize_data(green_data, -4, 5, invert=False)

        # Blue: 10.3μm (range: 280K to 220K)
        blue_norm = normalize_data(band13_data, 280, 220, invert=True)

        # Create RGB image
        rgb = np.dstack([red_norm, green_norm, blue_norm])
        rgb_uint8 = (rgb * 255).astype(np.uint8)
        rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0)

        # Save image
        Image.fromarray(rgb_uint8, "RGB").save(output_path)
        print(f"  Saved Dust RGB composite to {output_path}")
        return True

    except Exception as e:
        print(f"  Error creating Dust RGB: {e}")
        return False


def create_day_cloud_phase_rgb(channel_dir, output_path):
    """
    Create a Day Cloud Phase RGB composite.
    - Red: Band 13 (10.3μm IR)
    - Green: Band 5 (1.6μm Snow/Ice)
    - Blue: Band 2 (0.64μm Visible)
    """
    print("Creating Day Cloud Phase RGB composite")

    # Find necessary channel files
    bands_needed = [2, 5, 13]
    band_files = {}

    for band in bands_needed:
        pattern = f"OR_ABI-L2-CMIPF-M6C{band:02d}_*.nc"
        matches = list(Path(channel_dir).glob(pattern))
        if matches:
            band_files[band] = matches[0]

    if len(band_files) != len(bands_needed):
        print(f"  Error: Could not find all required bands. Found: {band_files.keys()}")
        return False

    try:
        # Load data
        band2_data = load_channel(band_files[2])
        band5_data = load_channel(band_files[5])
        band13_data = load_channel(band_files[13])

        # We need to resize as these are different resolutions
        print(
            f"  Band shapes: Band 2: {band2_data.shape}, Band 5: {band5_data.shape}, Band 13: {band13_data.shape}"
        )

        # Resize to lowest resolution (usually Band 13)
        target_shape = band13_data.shape

        # Process Band 2 (usually higher resolution)
        if band2_data.shape != target_shape:
            img = Image.fromarray(np.clip(band2_data, 0, 1) * 255).convert("L")
            img = img.resize((target_shape[1], target_shape[0]), Image.LANCZOS)
            band2_data = np.array(img).astype(float) / 255.0

        # Process Band 5 if needed
        if band5_data.shape != target_shape:
            img = Image.fromarray(np.clip(band5_data, 0, 1) * 255).convert("L")
            img = img.resize((target_shape[1], target_shape[0]), Image.LANCZOS)
            band5_data = np.array(img).astype(float) / 255.0

        # Normalize channels
        # Red: 10.3μm (range: 323K to 223K)
        red_norm = normalize_data(band13_data, 323, 223, invert=True)

        # Green: 1.6μm (range: 0 to 1 reflectance)
        green_norm = normalize_data(band5_data, 0, 1, invert=False)

        # Blue: 0.64μm (range: 0 to 1 reflectance)
        blue_norm = normalize_data(band2_data, 0, 1, invert=False)

        # Create RGB image
        rgb = np.dstack([red_norm, green_norm, blue_norm])
        rgb_uint8 = (rgb * 255).astype(np.uint8)
        rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0)

        # Save image
        Image.fromarray(rgb_uint8, "RGB").save(output_path)
        print(f"  Saved Day Cloud Phase RGB composite to {output_path}")
        return True

    except Exception as e:
        print(f"  Error creating Day Cloud Phase RGB: {e}")
        return False


def create_all_composites(channel_dir, output_dir=None):
    """Create all RGB composites."""
    if not output_dir:
        output_dir = Path(channel_dir) / "rgb_composites"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create each RGB composite
    create_natural_color_rgb(channel_dir, output_dir / "natural_color_rgb.png")
    create_airmass_rgb(channel_dir, output_dir / "airmass_rgb.png")
    create_fire_temperature_rgb(channel_dir, output_dir / "fire_temperature_rgb.png")
    create_dust_rgb(channel_dir, output_dir / "dust_rgb.png")
    create_day_cloud_phase_rgb(channel_dir, output_dir / "day_cloud_phase_rgb.png")

    print(f"\nAll RGB composites created. Results saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Create RGB composites from GOES ABI channels"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="/Users/justin/Downloads/goes_channels",
        help="Directory containing NetCDF files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save output images (default: input_dir/rgb_composites)",
    )
    args = parser.parse_args()

    create_all_composites(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
