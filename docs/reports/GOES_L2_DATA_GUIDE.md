# GOES Level-2 Data Usage Guide

This guide explains how to use the GOES Level-2 data download scripts to obtain ready-to-view satellite imagery.

## Overview

NOAA provides several levels of GOES satellite data products:

1. **Level-1b** (ABI-L1b): Raw radiometric data requiring calibration
2. **Level-2** (ABI-L2): Processed data products ready for viewing

The Level-2 products are much easier to work with, as they've already been calibrated, navigated, and processed into usable imagery.

## Key Products

| Product | Description | Scan Frequency | Key Variables |
|---------|-------------|----------------|--------------|
| `CMIPF` | Full Disk Cloud & Moisture Imagery | 10 minutes | `CMI` (individual bands), `CMI_C01_C02_C03` (true color) |
| `CMIPC` | CONUS Cloud & Moisture Imagery | 5 minutes | `CMI` (individual bands), `CMI_C01_C02_C03` (true color) |
| `CMIPM` | Mesoscale Cloud & Moisture Imagery | 1 minute | `CMI` (individual bands), `CMI_C01_C02_C03` (true color) |
| `RRQPEF` | Full Disk Rainfall Rate | 10 minutes | `RRQPE` (rainfall rate mm/hour) |
| `RRQPEM` | Mesoscale Rainfall Rate | 1 minute | `RRQPE` (rainfall rate mm/hour) |

## Scripts Provided

1. `download_goes_l2_data.py`: Comprehensive script to download various Level-2 products
2. `download_mesoscale_l2.py`: Specialized script for Mesoscale data (both M1 and M2 regions)

## Usage

### Basic Usage

```bash
# Download various Level-2 products
python download_goes_l2_data.py

# Download specifically Mesoscale data
python download_mesoscale_l2.py
```

### Where Data is Stored

Downloaded files are stored in:
- `~/Downloads/goes_l2_downloads/` for the main script
- `~/Downloads/goes_mesoscale/` for the mesoscale script

Within these directories, data is organized by:
- Product type (CMIPF, CMIPC, CMIPM, RRQPEF, etc.)
- For mesoscale data, there are separate M1 and M2 directories

### Output File Types

The scripts produce two types of files:

1. `.nc` files: Raw NetCDF data files from NOAA
2. `.png` files: Extracted imagery, including:
   - `*_truecolor.png`: True color RGB images
   - `*_ir13.png`: Clean IR (band 13) images
   - `*_rainfall.png`: Rainfall rate visualizations (for RRQPE products)

## Advantages of Level-2 Products

1. **Ready-to-view**: Variables are already scaled to appropriate ranges
2. **True color included**: No need to combine bands for RGB images
3. **Includes derivatives**: Products like rainfall rate are pre-calculated
4. **Same access method**: Uses the same anonymous S3 access as Level-1b products

## Customization

### Changing Date/Time

To download data from a different date/time, modify these variables in the scripts:

```python
# Test date: May 9, 2023 (Day of Year 129)
test_date = "2023/129"
test_hour = "18"  # 18:00 UTC
```

### Downloading Recent Data

The mesoscale script includes a function to download recent data:

```python
# This will attempt to download data from approximately 1 hour ago
recent_m1, recent_m2 = await download_recent_mesoscale(satellite, hours_back=1)
```

## Integration with GOES_VFI

To integrate with the main GOES_VFI application:

1. Use the `xarray` library to open and process NetCDF files
2. Extract ready-to-view imagery directly without complex calibration
3. For Sánchez processing, use the `CMI` variable from band 13
4. For true color, use the `CMI_C01_C02_C03` variable that's already combined

## Example Image Processing Code

```python
import xarray as xr
from PIL import Image
import numpy as np

# Load true color image
def load_true_color(nc_path):
    with xr.open_dataset(nc_path) as ds:
        rgb = ds["CMI_C01_C02_C03"].values.transpose(1, 2, 0)
        rgb = (rgb * 255).astype(np.uint8)  # Scale if needed
    return rgb

# Load IR image for Sánchez processing
def load_ir_for_sanchez(nc_path):
    with xr.open_dataset(nc_path) as ds:
        ir = ds["CMI"].values
        ir = ir.astype(np.uint8)  # Already 0-255
    return ir
```

## Mesoscale M1 vs M2 Identification

The scripts attempt to identify whether a mesoscale image belongs to M1 or M2 sectors based on timing patterns. This is a heuristic approach, as the definitive identification would require:

1. Checking metadata in the NetCDF files
2. Analyzing the actual scan area coordinates

For practical purposes, we use the timestamp pattern in filenames, where:
- M1 tends to use specific minutes/seconds
- M2 uses a different pattern

Both M1 and M2 data are downloaded and separated into appropriate directories.