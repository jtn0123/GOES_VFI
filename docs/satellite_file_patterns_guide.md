# GOES Satellite File Pattern Guide

This guide explains the file naming patterns used by NOAA for GOES satellite imagery and how our application accesses these files.

## S3 Bucket Structure

The NOAA GOES satellite imagery is available in public AWS S3 buckets:

- GOES-16 (East): `noaa-goes16`
- GOES-18 (West): `noaa-goes18`

## File Path Structure

The S3 keys follow this general structure:

```
ABI-L1b-{product_type}/{year}/{doy}/{hour}/OR_ABI-L1b-{product_type}-M6C{band}_{sat_code}_s{year}{doy}{hour}{minute}{second}_e{end_timestamp}_c{creation_timestamp}.nc
```

Where:
- `product_type`: Product type, one of:
  - `RadF`: Full Disk (whole Earth)
  - `RadC`: CONUS (Continental United States)
  - `RadM`: Mesoscale (smaller regions)
- `year`: 4-digit year (e.g., 2023)
- `doy`: 3-digit day of year (001-366)
- `hour`: 2-digit hour (00-23)
- `minute`: 2-digit minute (00-59)
- `second`: 2-digit second (00-59)
- `band`: 2-digit band number (01-16, where 13 is Clean IR)
- `sat_code`: `G16` for GOES-16, `G18` for GOES-18

## Scan Schedules

GOES satellites follow specific scanning schedules:

- **RadF** (Full Disk): Every 10 minutes at `[0, 10, 20, 30, 40, 50]` minutes past the hour
- **RadC** (CONUS): Every 5 minutes at `[1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56]` minutes past the hour
- **RadM** (Mesoscale): Every minute `[0-59]`

Each product type also has characteristic start seconds:
- RadF: ~0 seconds
- RadC: ~19 seconds
- RadM: ~24 seconds

## Example File Patterns

### RadF (Full Disk) Examples

```
OR_ABI-L1b-RadF-M6C13_G16_s20230661200000_e20230661209214_c20230661209291.nc
OR_ABI-L1b-RadF-M6C13_G18_s20240920100012_e20240920109307_c20240920109383.nc
```

### RadC (CONUS) Examples

```
OR_ABI-L1b-RadC-M6C13_G16_s20231661206190_e20231661208562_c20231661209032.nc
OR_ABI-L1b-RadC-M6C13_G18_s20240920101189_e20240920103562_c20240920104022.nc
```

### RadM (Mesoscale) Examples

```
OR_ABI-L1b-RadM1-M6C13_G16_s20231661200245_e20231661200302_c20231661200344.nc
OR_ABI-L1b-RadM1-M6C13_G18_s20240920100245_e20240920100302_c20240920100347.nc
```

## Bands

GOES ABI (Advanced Baseline Imager) has 16 different spectral bands:

1. Band 1 (0.47 μm): Blue - Aerosols, Daytime Clouds
2. Band 2 (0.64 μm): Red - Daytime Clouds, Fog, Dust
3. Band 3 (0.86 μm): Vegetation
4. Band 4 (1.37 μm): Cirrus Cloud Detection
5. Band 5 (1.6 μm): Snow/Ice Discrimination
6. Band 6 (2.2 μm): Cloud Particle Size, Dust
7. Band 7 (3.9 μm): Fire Detection, Fog
8. Band 8 (6.2 μm): Upper-Level Water Vapor
9. Band 9 (6.9 μm): Mid-Level Water Vapor
10. Band 10 (7.3 μm): Lower-Level Water Vapor
11. Band 11 (8.4 μm): Cloud-Top Phase
12. Band 12 (9.6 μm): Ozone
13. Band 13 (10.3 μm): **Clean IR Window** (commonly used)
14. Band 14 (11.2 μm): IR Window
15. Band 15 (12.3 μm): Dirty IR Window
16. Band 16 (13.3 μm): CO₂, Air Temperature

The most commonly used band is **Band 13 (Clean IR)** which provides clear infrared imagery.

## Accessing Files

Our application uses the following steps to access GOES imagery:

1. Calculate the proper day of year (DOY) from the calendar date
2. Find the nearest scan time based on the product type's schedule
3. Generate an S3 key pattern with wildcards to allow flexible matching
4. First try to download using a direct head_object request
5. If that fails, fall back to listing objects with the prefix and filtering
6. Filter returned objects by band number
7. Download the best match

## Testing with Real Data

We have created test scripts to validate our file patterns against real data:

- `test_real_s3_paths.py`: Standalone script to list and download real files
- `test_real_s3_patterns.py`: Unit tests for S3 key pattern generation
- `test_real_s3_store.py`: Integration tests for downloading real files

To run tests with real S3 access:

```bash
# Test listing recent files for different products/bands
python test_real_s3_paths.py --date 2024-05-01 --product RadC --band 13 --satellite GOES_18

# Run the store integration tests (requires RUN_REAL_S3_TESTS=1)
RUN_REAL_S3_TESTS=1 python -m pytest tests/unit/test_real_s3_store.py -v
```

## Common Issues

1. **File Not Found Errors**:
   - Check the date is within available data range (generally the past 1-2 weeks)
   - Ensure the timestamp matches the scanning schedule
   - Try different bands (not all bands are available at all times)

2. **Wrong Product Type**:
   - If looking for Full Disk (whole Earth) use `RadF`
   - If looking for CONUS (US view) use `RadC`

3. **Network or Timeout Issues**:
   - The S3 buckets may occasionally have access delays
   - Use exponential backoff and retry logic

## Example S3 Access Code

```python
# Generate S3 key with wildcards
s3_key = f"ABI-L1b-RadC/{year}/{doy_str}/{hour}/OR_ABI-L1b-RadC-M6C13_G18_s{year}{doy_str}{hour}{minute}*_e*_c*.nc"

# List objects matching the pattern
objects = s3_client.list_objects_v2(Bucket="noaa-goes18", Prefix=s3_key.split('*')[0])

# Filter for the desired band
filtered_keys = [obj['Key'] for obj in objects.get('Contents', []) 
                if f"M6C{band:02d}_" in obj['Key']]

# Download the best match
if filtered_keys:
    s3_client.download_file(Bucket="noaa-goes18", Key=filtered_keys[0], Filename=output_path)
```

## Additional Resources

- [GOES-R Series Data Book](https://www.goes-r.gov/downloads/resources/documents/GOES-RSeriesDataBook.pdf)
- [AWS NOAA Big Data Program](https://registry.opendata.aws/noaa-goes/)
- [NOAA GOES Image Viewer](https://www.star.nesdis.noaa.gov/GOES/index.php)