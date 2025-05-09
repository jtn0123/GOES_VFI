#!/usr/bin/env python
"""
GOES Product Detection Test Script

This script tests the detection and processing of various GOES satellite product types:
- Full Disk (RadF - ABI-L1b-RadF)
- Mesoscale (RadM - ABI-L1b-RadM)
- Clean IR (Band 13)
- Dirty IR (Band 14)
- True Color (Bands 1,2,3)
- Rain Rate (RRQPEF - ABI-L2-RRQPEF)

The script demonstrates how to:
1. Find files for specific product types and channels
2. Download and process NetCDF data
3. Display and visualize different bands appropriately
4. Handle product-specific metadata
"""

import os
import sys
import time
import argparse
import boto3
import botocore
import logging
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import imageio.v3 as iio
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
GOES_BUCKET = 'noaa-goes16'
TEMP_DIR = Path('temp_netcdf_downloads')
PRODUCTS = {
    'full_disk': {
        'prefix': 'ABI-L1b-RadF',
        'description': 'Full Disk imagery',
        'channels': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    },
    'meso1': {
        'prefix': 'ABI-L1b-RadM1',
        'description': 'Mesoscale 1 sector',
        'channels': [1, 2, 3, 7, 8, 9, 10, 13, 14, 15, 16]
    },
    'meso2': {
        'prefix': 'ABI-L1b-RadM2',
        'description': 'Mesoscale 2 sector',
        'channels': [1, 2, 3, 7, 8, 9, 10, 13, 14, 15, 16]
    },
    'cmip': {
        'prefix': 'ABI-L2-CMIPF',
        'description': 'Cloud and Moisture Imagery',
        'channels': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    },
    'rain_rate': {
        'prefix': 'ABI-L2-RRQPEF',
        'description': 'Rainfall Rate / QPE',
        'channels': [1],  # Only one data variable for rain rate
    }
}

CHANNEL_DESCRIPTIONS = {
    1: "Blue (Visible)",
    2: "Red (Visible)",
    3: "Veggie (Near-IR)",
    4: "Cirrus (Near-IR)",
    5: "Snow/Ice (Near-IR)",
    6: "Cloud Particle Size (Near-IR)",
    7: "Shortwave Window (IR)",
    8: "Upper-Level Water Vapor (IR)",
    9: "Mid-Level Water Vapor (IR)",
    10: "Lower-level Water Vapor (IR)",
    11: "Cloud Top Phase (IR)",
    12: "Ozone (IR)",
    13: "Clean Longwave Window (IR)",
    14: "Dirty Longwave Window (IR)",
    15: "Mid-level Tropospheric CO2 (IR)",
    16: "CO2 Longwave (IR)"
}


def create_s3_client():
    """Create an S3 client with unsigned access for public buckets."""
    return boto3.client(
        's3',
        config=boto3.session.Config(
            signature_version=botocore.UNSIGNED,
            retries={'max_attempts': 5}
        )
    )


def list_available_days(s3_client, product_prefix, year=None, month=None, day=None):
    """List available days for a given product type."""
    if year is None:
        year = datetime.now().year
    
    base_prefix = f"{product_prefix}/{year}"
    if month is not None:
        base_prefix += f"/{month:03d}"
        if day is not None:
            base_prefix += f"/{day:03d}"
    
    logger.info(f"Searching for available data in: {base_prefix}")
    
    try:
        # Use delimiter to list by directories
        response = s3_client.list_objects_v2(
            Bucket=GOES_BUCKET,
            Prefix=base_prefix,
            Delimiter='/',
            MaxKeys=100
        )
        
        available_items = []
        
        # Process common prefixes (directories)
        if 'CommonPrefixes' in response:
            for prefix in response['CommonPrefixes']:
                # Extract the last part of the prefix (day or hour)
                item = prefix['Prefix'].rstrip('/').split('/')[-1]
                available_items.append(item)
        
        return available_items
    except Exception as e:
        logger.error(f"Error listing available days: {e}")
        return []


def find_latest_file(s3_client, product_type, channel_num=None, year=None, day_of_year=None, hour=None):
    """Find the latest file for a specific product type and channel."""
    product_info = PRODUCTS.get(product_type)
    if not product_info:
        logger.error(f"Unknown product type: {product_type}")
        return None
    
    product_prefix = product_info['prefix']
    
    # Use current date if not specified
    if year is None or day_of_year is None:
        now = datetime.now()
        year = now.year
        day_of_year = now.timetuple().tm_yday
    
    # Build the prefix
    prefix = f"{product_prefix}/{year}/{day_of_year:03d}"
    if hour is not None:
        prefix += f"/{hour:02d}"
    
    logger.info(f"Searching for {product_type} files in {prefix}")
    
    try:
        # List objects with the given prefix
        response = s3_client.list_objects_v2(
            Bucket=GOES_BUCKET,
            Prefix=prefix,
            MaxKeys=100
        )
        
        if 'Contents' not in response:
            logger.warning(f"No files found for {prefix}")
            return None
        
        # Filter by channel if specified
        matching_files = []
        for obj in response['Contents']:
            file_key = obj['Key']
            
            # Skip non-NetCDF files
            if not file_key.endswith('.nc'):
                continue
                
            # Filter by channel if specified
            if channel_num is not None:
                # Check for channel pattern in filename
                channel_pattern = f"C{channel_num:02d}_"
                if channel_pattern not in file_key and not product_type == 'rain_rate':
                    continue
            
            matching_files.append(file_key)
        
        if not matching_files:
            logger.warning(f"No matching files found for {prefix} with channel {channel_num}")
            return None
        
        # Sort by name (which includes timestamp) and return the latest
        matching_files.sort()
        latest_file = matching_files[-1]
        logger.info(f"Found latest file: {latest_file}")
        return latest_file
        
    except Exception as e:
        logger.error(f"Error searching for {product_type} files: {e}")
        return None


def download_file(s3_client, file_key):
    """Download a file from S3 to local temp directory."""
    if not TEMP_DIR.exists():
        TEMP_DIR.mkdir(parents=True)
    
    local_file = TEMP_DIR / Path(file_key).name
    
    # Skip if file already exists
    if local_file.exists():
        logger.info(f"File already exists locally: {local_file}")
        return local_file
    
    logger.info(f"Downloading {file_key} to {local_file}")
    try:
        s3_client.download_file(
            Bucket=GOES_BUCKET,
            Key=file_key,
            Filename=str(local_file)
        )
        logger.info(f"Download complete: {local_file}")
        return local_file
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return None


def extract_netcdf_data(nc_file, product_type):
    """Extract relevant data from a NetCDF file based on product type."""
    logger.info(f"Opening NetCDF file: {nc_file}")
    try:
        # Open the dataset
        ds = xr.open_dataset(nc_file)
        
        # Debug: print available variables
        logger.info(f"Available variables: {list(ds.data_vars.keys())}")
        
        # Extract metadata
        metadata = {
            'filename': os.path.basename(nc_file),
            'time_coverage_start': ds.attrs.get('time_coverage_start', 'unknown'),
            'time_coverage_end': ds.attrs.get('time_coverage_end', 'unknown'),
            'product_type': product_type,
        }
        
        # Try to extract channel number from filename
        try:
            filename = os.path.basename(nc_file)
            if '_C' in filename:
                channel_part = filename.split('_C')[1]
                if len(channel_part) >= 2 and channel_part[:2].isdigit():
                    metadata['channel'] = int(channel_part[:2])
        except Exception as e:
            logger.warning(f"Could not extract channel from filename: {e}")
        
        # Extract relevant data variables based on product type
        if product_type == 'rain_rate':
            # Rain rate products have specific variables
            rain_vars = ['RRQPE', 'precipitation_rate', 'rainfall_rate']
            found = False
            
            for var in rain_vars:
                if var in ds:
                    data = ds[var]
                    metadata['variable'] = var
                    metadata['units'] = ds[var].attrs.get('units', 'mm/hr')
                    found = True
                    break
                    
            if not found:
                # Try to find any relevant rainfall variable
                candidates = [var for var in ds.data_vars if any(kw in var.lower() 
                             for kw in ['rain', 'precip', 'qpe', 'rate'])]
                if candidates:
                    var_name = candidates[0]
                    data = ds[var_name]
                    metadata['variable'] = var_name
                    metadata['units'] = ds[var_name].attrs.get('units', 'unknown')
                else:
                    # Last resort: use the first data variable
                    var_name = list(ds.data_vars.keys())[0]
                    data = ds[var_name]
                    metadata['variable'] = var_name
                    metadata['units'] = ds[var_name].attrs.get('units', 'unknown')
        else:
            # For ABI L1b products, try common variable names
            common_vars = ['Rad', 'Radiance', 'CMI', 'radiance']
            found = False
            
            for var in common_vars:
                if var in ds:
                    data = ds[var]
                    metadata['variable'] = var
                    metadata['units'] = ds[var].attrs.get('units', 'unknown')
                    found = True
                    break
            
            if not found:
                # Fallback to the first data variable
                if len(ds.data_vars) > 0:
                    var_name = list(ds.data_vars.keys())[0]
                    data = ds[var_name]
                    metadata['variable'] = var_name
                    metadata['units'] = ds[var_name].attrs.get('units', 'unknown')
                else:
                    logger.error("No data variables found in the NetCDF file")
                    return None, None, None
                
        # Include channel description if available
        if 'channel' in metadata:
            metadata['channel_description'] = CHANNEL_DESCRIPTIONS.get(
                metadata['channel'], 'Unknown channel'
            )
            
        # Include projection information if available
        if 'goes_imager_projection' in ds:
            metadata['projection'] = 'GOES Imager Projection'
            metadata['semi_major_axis'] = ds.goes_imager_projection.attrs.get('semi_major_axis', 'unknown')
            metadata['semi_minor_axis'] = ds.goes_imager_projection.attrs.get('semi_minor_axis', 'unknown')
        
        return data, metadata, ds
    
    except Exception as e:
        logger.error(f"Error extracting data from NetCDF file: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def visualize_data(data, metadata, save_path=None, downsample=4):
    """Visualize the extracted data with appropriate processing based on product type."""
    if data is None:
        logger.error("No data to visualize")
        return
    
    # Apply downsampling for large images if needed
    if downsample > 1 and hasattr(data, 'shape') and len(data.shape) >= 2:
        data = data[::downsample, ::downsample]
        logger.info(f"Downsampled data to shape: {data.shape}")
    
    product_type = metadata.get('product_type', 'unknown')
    variable = metadata.get('variable', 'unknown')
    channel = metadata.get('channel', None)
    
    # Get timestamp for filename
    timestamp = metadata.get('time_coverage_start', 'unknown')
    if timestamp.endswith('Z'):
        timestamp = timestamp[:-1]  # Remove Z suffix if present
    
    # Create figure without borders or axes
    fig = plt.figure(figsize=(12, 10), frameon=False)
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    
    # Apply visualization based on product type and channel
    try:
        if product_type == 'rain_rate':
            # Rain rate visualization (typically uses a colormap)
            img = ax.imshow(data, cmap='jet')
        elif variable == 'CMI' or variable == 'Rad':
            # For cloud moisture imagery or radiance
            if channel in [1, 2, 3]:  # Visible channels
                # Scale visible channels - typically values are between 0-1
                vmin, vmax = np.nanpercentile(data, [1, 99])
                img = ax.imshow(data, cmap='gray', vmin=vmin, vmax=vmax)
            elif channel in [13, 14]:  # IR channels
                # Typically convert to brightness temperature, invert colormap 
                # for IR (cold clouds = white)
                vmin, vmax = np.nanpercentile(data, [1, 99])
                img = ax.imshow(data, cmap='gray_r', vmin=vmin, vmax=vmax)
            else:  # Other channels
                # Generic visualization
                vmin, vmax = np.nanpercentile(data, [1, 99])
                img = ax.imshow(data, cmap='viridis', vmin=vmin, vmax=vmax)
        else:
            # Generic visualization for other data types
            vmin, vmax = np.nanpercentile(data, [1, 99])
            img = ax.imshow(data, cmap='viridis', vmin=vmin, vmax=vmax)
    
        # Add minimal timestamp text
        channel_text = f"Ch{channel}" if channel else ""
        plt.figtext(0.02, 0.02, f"{timestamp} {channel_text}", fontsize=8, color='white', 
                   bbox=dict(facecolor='black', alpha=0.5, pad=1))
        
        # Save figure if requested
        if save_path:
            # First save the annotated version with timestamp
            plt.savefig(save_path, dpi=150, bbox_inches='tight', pad_inches=0)
            logger.info(f"Saved visualization to {save_path}")
            
            # Create a direct image file instead of using matplotlib for raw version
            # Convert the image data to 8-bit RGB
            img_data = np.clip(data, *np.nanpercentile(data, [1, 99]))
            img_data = (img_data - np.nanmin(img_data)) / (np.nanmax(img_data) - np.nanmin(img_data))
            
            # For IR channels, invert the colormap
            if channel in [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]:
                img_data = 1.0 - img_data
                
            # Create RGB array (grayscale)
            rgb = np.zeros((img_data.shape[0], img_data.shape[1], 3), dtype=np.uint8)
            img_data = (img_data * 255).astype(np.uint8)
            for i in range(3):
                rgb[:, :, i] = img_data
                
            # Save directly without matplotlib
            raw_path = str(save_path).replace('.png', '_raw.png')
            iio.imwrite(raw_path, rgb)
            logger.info(f"Saved raw visualization (no text) to {raw_path}")
        
        return plt.gcf()
    
    except Exception as e:
        logger.error(f"Error visualizing data: {e}")
        import traceback
        traceback.print_exc()
        plt.close()
        return None


def create_true_color(channel1_file, channel2_file, channel3_file, save_path=None, downsample=4):
    """Create a true color image from channels 1, 2, and 3."""
    logger.info("Creating true color image from channels 1, 2, and 3")
    try:
        # Open the three channel datasets
        ds1 = xr.open_dataset(channel1_file)
        ds2 = xr.open_dataset(channel2_file)
        ds3 = xr.open_dataset(channel3_file)
        
        # Log the shapes of the data arrays for debugging
        logger.info(f"Channel shapes before processing - CH1: {ds1['Rad'].shape if 'Rad' in ds1 else 'N/A'}, " +
                   f"CH2: {ds2['Rad'].shape if 'Rad' in ds2 else 'N/A'}, " +
                   f"CH3: {ds3['Rad'].shape if 'Rad' in ds3 else 'N/A'}")
        
        # Extract the data variables
        if 'Rad' in ds1 and 'Rad' in ds2 and 'Rad' in ds3:
            blue = ds1['Rad'].values
            green = ds3['Rad'].values  # Channel 3 is usually the green component
            red = ds2['Rad'].values
            variable = 'Rad'
        elif 'CMI' in ds1 and 'CMI' in ds2 and 'CMI' in ds3:
            blue = ds1['CMI'].values
            green = ds3['CMI'].values
            red = ds2['CMI'].values
            variable = 'CMI'
        else:
            logger.error("Could not find consistent Rad or CMI variables in all three datasets")
            return None
        
        # Ensure all arrays have the same dimensions by resampling to the smallest size
        min_shape = min(blue.shape[0], green.shape[0], red.shape[0])
        
        # Resample to common shape if needed
        if blue.shape[0] != min_shape:
            logger.info(f"Resampling blue channel from {blue.shape} to ({min_shape}, {min_shape})")
            import skimage.transform
            blue = skimage.transform.resize(blue, (min_shape, min_shape), 
                                          anti_aliasing=True, preserve_range=True)
        
        if green.shape[0] != min_shape:
            logger.info(f"Resampling green channel from {green.shape} to ({min_shape}, {min_shape})")
            import skimage.transform
            green = skimage.transform.resize(green, (min_shape, min_shape), 
                                           anti_aliasing=True, preserve_range=True)
        
        if red.shape[0] != min_shape:
            logger.info(f"Resampling red channel from {red.shape} to ({min_shape}, {min_shape})")
            import skimage.transform
            red = skimage.transform.resize(red, (min_shape, min_shape), 
                                         anti_aliasing=True, preserve_range=True)
        
        # Apply downsampling if needed and arrays are large
        if downsample > 1 and min_shape > 1000:
            target_shape = min_shape // downsample
            logger.info(f"Downsampling all channels to shape: ({target_shape}, {target_shape})")
            
            import skimage.transform
            blue = skimage.transform.resize(blue, (target_shape, target_shape), 
                                          anti_aliasing=True, preserve_range=True)
            green = skimage.transform.resize(green, (target_shape, target_shape), 
                                           anti_aliasing=True, preserve_range=True)
            red = skimage.transform.resize(red, (target_shape, target_shape), 
                                         anti_aliasing=True, preserve_range=True)
        
        # Create a true color RGB array
        logger.info(f"Final array shapes - Red: {red.shape}, Green: {green.shape}, Blue: {blue.shape}")
        rgb = np.zeros((blue.shape[0], blue.shape[1], 3), dtype=np.float32)
        
        # Scale each channel to 0-1 range using percentiles to avoid extreme values
        for idx, data in enumerate([red, green, blue]):
            p1, p99 = np.nanpercentile(data, [1, 99])
            scaled = np.clip((data - p1) / (p99 - p1), 0, 1)
            rgb[:, :, idx] = scaled
            
        # Apply gamma correction to brighten the image
        gamma = 0.6  # Less than 1 = brighter, more than 1 = darker
        rgb = np.power(rgb, gamma)
        
        # Create figure and display RGB image without axes or borders
        fig = plt.figure(figsize=(12, 10), frameon=False)
        ax = plt.Axes(fig, [0., 0., 1., 1.])
        ax.set_axis_off()
        fig.add_axes(ax)
        
        # Display the image without axes, borders, or other elements
        ax.imshow(rgb)
        
        # Add minimal timestamp at bottom (small and unobtrusive)
        timestamp = ds1.attrs.get('time_coverage_start', 'unknown')
        if timestamp.endswith('Z'):
            timestamp = timestamp[:-1]  # Remove Z suffix if present
        
        # Add very small timestamp in corner
        plt.figtext(0.02, 0.02, timestamp, fontsize=8, color='white', 
                   bbox=dict(facecolor='black', alpha=0.5, pad=1))
        
        # Save figure if requested
        if save_path:
            # First save the annotated version with timestamp
            plt.savefig(save_path, dpi=150, bbox_inches='tight', pad_inches=0)
            logger.info(f"Saved true color image to {save_path}")
            
            # Create a direct image file instead of using matplotlib for raw version
            # Save RGB array directly to file
            raw_path = str(save_path).replace('.png', '_raw.png')
            rgb_uint8 = (rgb * 255).astype(np.uint8)
            iio.imwrite(raw_path, rgb_uint8)
            logger.info(f"Saved raw true color image (no text) to {raw_path}")
        return plt.gcf()
        
    except Exception as e:
        logger.error(f"Error creating true color image: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_product(s3_client, product_type, channel=None, year=None, day=None, hour=None, 
                    download_dir=None, show_plot=True, save_plot=True):
    """Process a specific product type and channel."""
    logger.info(f"Processing {product_type}, channel {channel}")
    
    # Find the latest file
    file_key = find_latest_file(s3_client, product_type, channel, year, day, hour)
    if not file_key:
        logger.error(f"No file found for {product_type}, channel {channel}")
        return None, None
    
    # Download the file
    local_file = download_file(s3_client, file_key)
    if not local_file:
        logger.error(f"Failed to download {file_key}")
        return None, None
    
    # Extract data from NetCDF
    data, metadata, ds = extract_netcdf_data(local_file, product_type)
    if data is None:
        logger.error(f"Failed to extract data from {local_file}")
        return None, None
    
    # Visualize the data
    if save_plot:
        # Parse the timestamp from the metadata to use in the filename
        timestamp = "unknown_time"
        if 'time_coverage_start' in metadata:
            try:
                # Convert ISO format time to a cleaner filename format
                dt = datetime.fromisoformat(metadata['time_coverage_start'].replace('Z', '+00:00'))
                timestamp = dt.strftime('%Y%m%d_%H%M%S')
            except Exception as e:
                logger.warning(f"Could not parse time from metadata: {e}")
        
        save_path = TEMP_DIR / f"{product_type}_ch{channel}_{timestamp}.png"
    else:
        save_path = None
        
    fig = visualize_data(data, metadata, save_path)
    
    # Show plot if requested
    if show_plot:
        plt.show()
    else:
        plt.close()
    
    return local_file, metadata


def process_true_color(s3_client, product_type='full_disk', year=None, day=None, hour=None,
                       download_dir=None, show_plot=True, save_plot=True):
    """Process and create a true color image from channels 1, 2, and 3."""
    logger.info(f"Processing true color image for {product_type}")
    
    # Download channels 1, 2, and 3
    channels = {}
    timestamps = []
    
    for ch in [1, 2, 3]:
        # Find and download the file
        file_key = find_latest_file(s3_client, product_type, ch, year, day, hour)
        if not file_key:
            logger.error(f"Could not find file for {product_type}, channel {ch}")
            return None
            
        local_file = download_file(s3_client, file_key)
        if not local_file:
            logger.error(f"Failed to download {file_key}")
            return None
        
        # Extract timestamp from file name
        try:
            # Look for the pattern s[YYYYDDDHHMMSS] in the filename
            filename = os.path.basename(file_key)
            if '_s' in filename:
                timestamp_part = filename.split('_s')[1][:13]  # Format: YYYYDDDHHMMSS
                year_str = timestamp_part[:4]
                doy_str = timestamp_part[4:7]
                hour_str = timestamp_part[7:9]
                min_str = timestamp_part[9:11]
                sec_str = timestamp_part[11:13]
                
                # Create datetime object
                base_date = datetime(int(year_str), 1, 1)
                date_time = base_date + timedelta(days=int(doy_str)-1, 
                                                  hours=int(hour_str),
                                                  minutes=int(min_str),
                                                  seconds=int(sec_str))
                timestamps.append(date_time)
        except Exception as e:
            logger.warning(f"Could not parse timestamp from filename {filename}: {e}")
        
        channels[ch] = local_file
    
    # Create true color image
    if save_plot:
        # Use the timestamp from the files if available
        if timestamps:
            # Use the most recent timestamp
            timestamps.sort()
            timestamp_str = timestamps[-1].strftime('%Y%m%d_%H%M%S')
        else:
            # Fallback to using the scan time (s) from the filename
            try:
                # Extract scan time from one of the files
                filename = os.path.basename(channels[1])
                if '_s' in filename:
                    timestamp_part = filename.split('_s')[1][:13]  # YYYYDDDHHMMSS
                    timestamp_str = f"{timestamp_part[:4]}{timestamp_part[4:7]}_{timestamp_part[7:13]}"
                else:
                    # Last resort: current time
                    timestamp_str = "unknown_time"
            except:
                timestamp_str = "unknown_time"
        
        save_path = TEMP_DIR / f"{product_type}_true_color_{timestamp_str}.png"
    else:
        save_path = None
        
    fig = create_true_color(channels[1], channels[2], channels[3], save_path)
    
    # Show plot if requested
    if show_plot:
        plt.show()
    else:
        plt.close()
    
    return fig


def main():
    """Main function to run the script with command line arguments."""
    parser = argparse.ArgumentParser(description='GOES Product Detection Test Script')
    parser.add_argument('--product', type=str, choices=list(PRODUCTS.keys()), default='full_disk',
                        help='Product type to process')
    parser.add_argument('--channel', type=int, help='Channel number to process')
    parser.add_argument('--true-color', action='store_true', help='Create true color image (channels 1, 2, 3)')
    parser.add_argument('--year', type=int, help='Year to search for data (YYYY)')
    parser.add_argument('--day', type=int, help='Day of year to search for data (1-366)')
    parser.add_argument('--hour', type=int, help='Hour to search for data (0-23)')
    parser.add_argument('--list-days', action='store_true', help='List available days for the product')
    parser.add_argument('--no-plot', action='store_true', help='Do not display plots')
    parser.add_argument('--no-save', action='store_true', help='Do not save plots')
    
    args = parser.parse_args()
    
    # Create S3 client
    s3_client = create_s3_client()
    
    # List available days if requested
    if args.list_days:
        days = list_available_days(s3_client, PRODUCTS[args.product]['prefix'], 
                                  args.year, args.day)
        print(f"Available days for {args.product}:")
        for day in days:
            print(f"  {day}")
        return
    
    # Process product
    if args.true_color:
        process_true_color(
            s3_client, args.product, args.year, args.day, args.hour,
            show_plot=not args.no_plot, save_plot=not args.no_save
        )
    elif args.channel or args.product == 'rain_rate':
        # For rain_rate products, we don't need a specific channel
        channel = args.channel if args.channel else (1 if args.product == 'rain_rate' else None)
        process_product(
            s3_client, args.product, channel, args.year, args.day, args.hour,
            show_plot=not args.no_plot, save_plot=not args.no_save
        )
    else:
        print("Please specify a channel number or use --true-color option.")
        parser.print_help()
        return


if __name__ == "__main__":
    main()