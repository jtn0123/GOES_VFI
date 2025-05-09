# GOES Satellite Imagery in GOES_VFI

## Overview

The GOES_VFI project includes functionality for downloading, processing, and visualizing GOES satellite imagery. This functionality is implemented in the `goesvfi.integrity_check` module and provides support for accessing data from both NOAA's Content Delivery Network (CDN) and AWS S3 buckets hosting GOES data.

## Recent Enhancements

We've added several new scripts to provide more robust and flexible access to GOES imagery:

1. **`improved_goes_processor.py`** - Comprehensive processor that handles:
   - Level-2 CMIP and MCMIP products
   - Multiple band processing (IR, True Color)
   - Proper wildcard patterns with band numbers
   - Sánchez colorization for IR imagery

2. **`goes_satpy_processor.py`** - Advanced processor using Satpy when available:
   - Proper band resolution handling
   - Advanced atmospheric correction
   - Better true color compositing

3. **`scan_goes_dates.py`** - Utility to scan for available data:
   - Searches across multiple dates and hours
   - Checks both GOES-16 and GOES-18
   - Reports all available product types

4. **`download_goes_jpeg.py`** - Downloads pre-processed JPEGs from NOAA CDN:
   - Most recent ~15 days only
   - Uses correct CDN URL patterns
   - Handles various product types and sectors

## GOES Data Structure Findings

Our investigation revealed several important details about GOES data organization:

### NOAA S3 Buckets

1. **Path Structure**:
   - `ABI-L2-CMIP{sector}/{YYYY}/{DDD}/{HH}/`
   - Files directly in hour directory (no minute subdirectories)

2. **File Naming**:
   - Format: `OR_ABI-L2-CMIP{sector}-M6C{band}_G{sat}_s{timestamp}_e{timestamp}_c{timestamp}.nc`
   - Band number is part of the product code (`-M6C13`)
   - Satellite ID is at the end of product code (`G16` or `G18`)

3. **Product Types**:
   - `CMIPF` - Full Disk (one file per band)
   - `CMIPC` - CONUS (Continental US)
   - `CMIPM1/M2` - Mesoscale 1 and 2
   - `MCMIPF` - Multi-Channel (all bands in one file)
   - `RRQPEF` - Rainfall Rate (precipitation data)

### NetCDF Structure

1. **CMIP Files**:
   - Contains single-band data in `CMI` variable
   - Bands 1-6: Reflectance (0-1)
   - Bands 7-16: Brightness Temperature (K)
   - Different resolutions:
     - Band 2: 0.5km (2x higher resolution)
     - Most others: 1km or 2km

2. **MCMIP Files**:
   - Contains all bands in `CMI_C01` through `CMI_C16` variables
   - May contain pre-composed `true_color` variable (inconsistent)

### NOAA CDN

1. **URL Pattern**:
   - `https://cdn.star.nesdis.noaa.gov/{satellite}/ABI/{sector}/{product}/{YYYYMMDD}/{HHMMSS}_{satellite}-ABI-{sector}-{product}-{resolution}.jpg`

2. **Limitations**:
   - Recent data only (~15 days)
   - Some networks may restrict access
   - No HEAD request support

## Advanced Processing Techniques

Our implementation includes several advanced techniques:

1. **Sánchez Colorization for IR**:
   - Custom LUT (Lookup Table) for Band 13
   - Maps temperature to intuitive color scheme
   - Temperature range normalization (180K-320K)

2. **True Color Composite**:
   - Proper handling of different band resolutions
   - Gamma correction (2.2) for more natural appearance
   - Contrast enhancement (1.5×)
   - Proper channel ordering (R=1, G=2, B=3)

3. **Satpy Integration**:
   - Advanced compositing with proper resampling
   - Advanced RGB generation with atmospheric correction

## Usage Examples

### Basic IR Image Processing:

```bash
python goes_satpy_processor.py --satellite GOES16 --sector full_disk --product ir --year 2023 --doy 121 --hour 19
```

### True Color Image Processing:

```bash
python goes_satpy_processor.py --satellite GOES16 --sector full_disk --product truecolor --year 2023 --doy 121 --hour 19
```

### Scanning for Available Data:

```bash
python scan_goes_dates.py --start-date 2023-05-01 --end-date 2023-05-01 --hours 15 16 17 18 19 20
```

## Integration with Existing Infrastructure

These new scripts complement the existing infrastructure:

1. **`GOESImageryManager`** (existing):
   - Can leverage the new processing scripts
   - Provides a high-level API for the UI components

2. **`GOESImageryTab`** (existing):
   - Can display the enhanced imagery
   - Provides a user-friendly interface for selection

3. **Key Improvements**:
   - Better wildcard patterns for reliable file finding
   - Proper handling of band numbers in filenames
   - Multiple fallback approaches for true color
   - Improved IR visualization with Sánchez colorization

## Future Enhancements

Potential future improvements include:

1. **Full Satpy Integration**:
   - More advanced composites (Airmass RGB, Day Cloud Phase)
   - Better image projection and resampling

2. **More Product Types**:
   - Cloud Top Temperature (CTPF)
   - Land Surface Temperature (LSTF)
   - Snow/Ice Cover (SFCF)

3. **Animation Support**:
   - Time series of images
   - GIF/MP4 creation for visualization

4. **Performance Optimization**:
   - Parallel downloading of multi-band imagery
   - Caching of processed imagery