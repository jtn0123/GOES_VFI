# GOES Satellite Products Reference

This document provides information about the different GOES satellite products available for use in the GOES VFI application.

## Product Types

### Full Disk (ABI-L1b-RadF)
Full disk images cover the entire Earth disk as viewed from the satellite's position. These are available in all 16 channels.

### Mesoscale (ABI-L1b-RadM)
Mesoscale sectors provide higher resolution data for targeted regions. There are two mesoscale sectors (M1 and M2) that can be positioned anywhere in the field of view. These are available in most channels with 1-minute updates.

### Cloud and Moisture Imagery (ABI-L2-CMIPF)
Processed imagery specifically for cloud and moisture visualization, available for all channels.

### Rain Rate / QPE (ABI-L2-RRQPEF)
Quantitative Precipitation Estimate products, providing rainfall rate information.

## Channels and Their Applications

| Channel | Wavelength (μm) | Description | Primary Applications |
|---------|----------------|-------------|---------------------|
| 1 | 0.47 | Blue Visible | Aerosols, smoke, haze detection |
| 2 | 0.64 | Red Visible | Cloud, fog, insolation, winds |
| 3 | 0.86 | Veggie Near-IR | Vegetation, burn scar, aerosol, winds |
| 4 | 1.37 | Cirrus Near-IR | Cirrus cloud detection |
| 5 | 1.6 | Snow/Ice Near-IR | Cloud-top phase, snow/ice discrimination |
| 6 | 2.2 | Cloud Particle Size Near-IR | Cloud particle size, snow cloud discrimination |
| 7 | 3.9 | Shortwave Window IR | Fire detection, fog detection, night fog, winds |
| 8 | 6.2 | Upper-Level Water Vapor IR | High-level moisture, winds, rainfall |
| 9 | 6.9 | Mid-Level Water Vapor IR | Mid-level moisture, winds, rainfall |
| 10 | 7.3 | Lower-level Water Vapor IR | Lower-level moisture, winds, rainfall |
| 11 | 8.4 | Cloud Top Phase IR | Cloud-top phase, dust, SO2 detection |
| 12 | 9.6 | Ozone IR | Atmospheric total column ozone |
| 13 | 10.3 | Clean Longwave Window IR | Surface temp, cloud detection, rainfall |
| 14 | 11.2 | Dirty Longwave Window IR | Sea surface temperature |
| 15 | 12.3 | Mid-level Tropospheric CO2 IR | Air temperature, cloud heights |
| 16 | 13.3 | CO2 Longwave IR | Air temperature, cloud heights |

## Common Imagery Types

### True Color
Created by combining Channels 1 (blue), 2 (red), and 3 (green) to create a natural-looking color image.

### Clean IR (Channel 13)
Infrared imagery showing cloud top temperatures using the clean IR window (10.3 μm). This channel has less water vapor absorption compared to Channel 14, providing clearer imagery of Earth's surface in non-cloudy regions.

### Dirty IR (Channel 14)
Infrared imagery using the 11.2 μm band, called "dirty" because of its sensitivity to water vapor absorption. Often used for sea surface temperature measurements.

### Water Vapor (Channels 8, 9, 10)
Shows moisture content in the atmosphere at different levels. Channel 8 shows upper-level moisture, Channel 9 shows mid-level, and Channel 10 shows lower-level moisture.

## S3 Bucket Structure

GOES-16 data is stored in the `noaa-goes16` public S3 bucket with the following path structure:

```
[Product]/[Year]/[Day of Year]/[Hour]/[Filename]
```

For example:
```
ABI-L1b-RadF/2023/032/14/OR_ABI-L1b-RadF-M6C13_G16_s20230321402203_e20230321404576_c20230321405089.nc
```

Filenames follow this structure:
```
OR_[Product]-[Processing Level]-[Type]_G[16/17]_s[Start Time]_e[End Time]_c[Creation Time].nc
```

## Usage Examples

See the test script (`test_goes_product_detection.py`) for examples of how to:

1. Find and download specific product types and channels
2. Process and visualize different channels appropriately
3. Create true color images from multiple channels

## Command Line Examples

```bash
# List available days for full disk data
python test_goes_product_detection.py --product full_disk --list-days

# Process and visualize clean IR (channel 13) from full disk
python test_goes_product_detection.py --product full_disk --channel 13

# Create a true color image from mesoscale sector 1
python test_goes_product_detection.py --product meso1 --true-color

# View rain rate data
python test_goes_product_detection.py --product rain_rate

# Get data for a specific day (day 32 of the year)
python test_goes_product_detection.py --product full_disk --channel 2 --day 32
```

## Integration with GOES VFI Application

This reference and the test script provide a foundation for integrating these product types into the main application. Key considerations for integration include:

1. UI components to allow selection of product types, channels, and time periods
2. Efficient data downloading and caching strategies
3. Appropriate visualization techniques for different channel types
4. Processing pipelines for creating specialized products like true color imagery