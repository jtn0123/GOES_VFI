#!/usr/bin/env python3
"""
Download GOES Level - 2 data products and save as ready - to - view images.
This script focuses on the Level - 2 CMIP products which contain pre - processed imagery.
"""
import asyncio
import logging
import os
from pathlib import Path

import boto3
import numpy as np
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


if __name__ == "__main__":
    pass
asyncio.run(main())
