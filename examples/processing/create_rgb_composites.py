#!/usr/bin/env python3
"""
Create specialized RGB composites from GOES ABI channels.
"""
import argparse
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
parser.add_argument(
    "--input - dir",
    type=str,
    default="/Users / justin / Downloads / goes_channels",
    help="Directory containing NetCDF files",
)
parser.add_argument(
    "--output - dir",
    type=str,
    default=None,
    help="Directory to save output images (default: input_dir / rgb_composites)",
)
args = parser.parse_args()

create_all_composites(args.input_dir, args.output_dir)


if __name__ == "__main__":
    pass
main()
