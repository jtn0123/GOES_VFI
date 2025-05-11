# GOES Satellite Download Enhancements

This document summarizes the enhancements made to the GOES satellite imagery downloader functionality.

## Overview

The GOES VFI application has been enhanced to support downloading satellite imagery for:

1. **Multiple bands**: All 16 ABI bands (1-16) are now supported
2. **Multiple product types**: Full Disk (RadF), CONUS (RadC), and Mesoscale (RadM) products
3. **Both satellites**: GOES-16 (East) and GOES-18 (West)
4. **Multiple regions for mesoscale**: Both Mesoscale-1 and Mesoscale-2 regions

## Test Scripts Created

Several test scripts were created to verify the functionality:

1. `download_goes_data.py`: Main script to download satellite imagery using anonymous S3 access
2. `test_download_full_disk.py`: Focused script for testing Full Disk (RadF) downloads
3. `test_download_mesoscale.py`: Specialized script for testing Mesoscale (RadM) downloads
4. `test_download_all_products.py`: Comprehensive script to test all product types and bands

## Code Improvements

### 1. Enhanced `time_index.py`

The `time_index.py` file was updated to:

- Make the band number configurable (default remains band 13, Clean IR)
- Support all product types (RadF, RadC, RadM)
- Improve filename patterns to match GOES ABI files correctly
- Generate appropriate S3 keys for all combinations of band, product type, and satellite

### 2. Anonymous S3 Access

Enhanced S3 access using boto3's unsigned configuration to access NOAA's public S3 buckets:

```python
s3 = boto3.client('s3',
                 region_name='us-east-1',
                 config=Config(signature_version=UNSIGNED))
```

### 3. Improved Mesoscale Handling

Added support for both Mesoscale-1 and Mesoscale-2 regions by:
- Using timestamp patterns to differentiate between M1 and M2 files
- Organizing downloads by region for clear separation
- Adding extended minutes search to find files across different times

## Testing Results

The test scripts successfully downloaded:

1. **Full Disk (RadF)**:
   - GOES-16: Bands 2, 3, 8, 13
   - GOES-18: Bands 2, 3, 8, 13
   - File sizes ranged from 17MB to 326MB

2. **CONUS (RadC)**:
   - GOES-16: Bands 2, 3, 8, 13
   - GOES-18: Bands 2, 3, 8, 13
   - File sizes ranged from 2.9MB to 53MB

3. **Mesoscale (RadM)**:
   - Additional testing needed to confirm all time patterns
   - Directory structure confirmed but file structure requires verification

## Next Steps

1. **Integration**: Incorporate the updated `time_index.py` into the main application
2. **UI Enhancements**: Add band selection in the UI to allow users to choose which bands to download
3. **Configuration**: Add product type selection to allow users to choose RadF, RadC, or RadM
4. **Performance**: Optimize simultaneous downloads with proper throttling
5. **Error Handling**: Enhance error handling for missing files or connection issues

## File Structure

Downloaded files are organized as follows:

```
~/Downloads/goes_downloads/
├── RadF/                             # Full Disk products
│   ├── G16_RadF_Band02_OR_*.nc       # GOES-16 Full Disk files
│   ├── G16_RadF_Band03_OR_*.nc
│   └── ...
├── RadC/                             # CONUS products
│   ├── G16_RadC_Band02_OR_*.nc       # GOES-16 CONUS files
│   ├── G18_RadC_Band13_OR_*.nc       # GOES-18 CONUS files
│   └── ...
└── RadM/                             # Mesoscale products
    ├── M1/                           # Mesoscale-1 region
    │   ├── G16_RadM_M1_Band02_OR_*.nc
    │   └── ...
    └── M2/                           # Mesoscale-2 region
        ├── G16_RadM_M2_Band02_OR_*.nc
        └── ...
```

## NetCDF File Usage

The downloaded .nc files can be read using Python libraries such as:

```python
import xarray as xr

# Open a NetCDF file
ds = xr.open_dataset('path/to/file.nc')

# View the data
print(ds)

# Extract the data array and convert to numpy array
data = ds['Rad'].values

# Plot with matplotlib
import matplotlib.pyplot as plt
plt.imshow(data)
plt.colorbar()
plt.show()
```

Alternatively, standalone applications like Panoply can be used to visualize NetCDF files.
