#!/usr/bin/env python3
"""
Test script to list and download real GOES satellite imagery files from NOAA's S3 buckets.

This script uses the aioboto3 library to connect to the AWS S3 NOAA buckets and
attempts to find files with different product types, scan schedules, and bands.
It can be used to validate the S3 key format and file patterns used in the GOES_VFI
application.

Example usage:
    python test_real_s3_paths.py --date 2024-05-10 --product RadC --band 13 --satellite GOES_18

Note: This script uses unsigned S3 access for public NOAA GOES buckets.
No AWS credentials are required as these buckets are publicly accessible.
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

import aioboto3
from botocore import UNSIGNED
from botocore.config import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('s3_test_results.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('s3_test')

# NOAA S3 bucket names
S3_BUCKETS = {
    'GOES_16': 'noaa-goes16',
    'GOES_18': 'noaa-goes18'
}

# Satellite codes
SATELLITE_CODES = {
    'GOES_16': 'G16',
    'GOES_18': 'G18'
}

# Scanning schedules
RADF_MINUTES = [0, 10, 20, 30, 40, 50]  # Full Disk scans
RADC_MINUTES = [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56]  # CONUS scans
RADM_MINUTES = list(range(60))  # Mesoscale scans

# Start seconds for each product type (approximate)
START_SECONDS = {"RadF": 0, "RadC": 19, "RadM": 24}

def date_to_doy(date: datetime) -> int:
    """Convert a date to day of year."""
    return date.timetuple().tm_yday

def to_s3_key(ts: datetime, satellite_code: str, product_type: str = "RadC", band: int = 13, use_wildcard: bool = True) -> str:
    """
    Generate an S3 key for the given timestamp, satellite, and product type.
    
    Args:
        ts: Datetime object for the image
        satellite_code: Satellite code (G16 or G18)
        product_type: Product type ("RadF" for Full Disk, "RadC" for CONUS, "RadM" for Mesoscale)
        band: Band number (1-16, default 13 for Clean IR)
        use_wildcard: If True, use wildcard patterns for flexible matching
        
    Returns:
        S3 key string (not including bucket name)
    """
    year = ts.year
    doy = date_to_doy(ts.date())  # Day of year
    doy_str = f"{doy:03d}"  # Day of year as string (001-366)
    hour = ts.strftime("%H")
    
    # Get appropriate scanning schedule for the product type
    scan_minutes = []
    if product_type == "RadF":
        scan_minutes = RADF_MINUTES
    elif product_type == "RadC":
        scan_minutes = RADC_MINUTES
    elif product_type == "RadM":
        scan_minutes = RADM_MINUTES
    
    # Get appropriate start second for the product type
    start_sec = START_SECONDS.get(product_type, 0)
    
    # Find the nearest appropriate minute
    original_minute = ts.minute
    valid_minute = None
    
    # Find the nearest valid scan minute for this product
    for minute in scan_minutes:
        if minute == original_minute:
            valid_minute = minute
            break
        # If we've gone past the original minute, take the previous valid minute
        elif minute > original_minute and valid_minute is not None:
            break
        # Keep updating valid_minute with the last valid minute we've seen
        else:
            valid_minute = minute
    
    # If we never found a match and went through the whole list, wrap around
    if valid_minute is None and scan_minutes:
        valid_minute = scan_minutes[-1]
    elif valid_minute is None:
        # Default to the original minute if the scan_minutes list is empty
        valid_minute = original_minute
    
    # Format the valid minute
    minute_str = f"{valid_minute:02d}"
    
    # Format the band string
    band_str = f"{band:02d}"
    
    # Base key structure
    base_key = f"ABI-L1b-{product_type}/{year}/{doy_str}/{hour}/"
    
    if use_wildcard:
        # Use wildcard pattern for production
        pattern = f"OR_ABI-L1b-{product_type}-M6C{band_str}_{satellite_code}_s{year}{doy_str}{hour}{minute_str}*_e*_c*.nc"
    else:
        # Use concrete filename with exact start second
        pattern = f"OR_ABI-L1b-{product_type}-M6C{band_str}_{satellite_code}_s{year}{doy_str}{hour}{minute_str}{start_sec:02d}_e*_c*.nc"
    
    return base_key + pattern

async def list_s3_objects(bucket: str, prefix: str, pattern: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    List objects in an S3 bucket with the given prefix.
    
    Args:
        bucket: S3 bucket name
        prefix: S3 key prefix
        pattern: Optional pattern to filter results
        limit: Maximum number of objects to return
        
    Returns:
        List of S3 objects (dicts with Key, LastModified, etc.)
    """
    # Create S3 client with unsigned access for public buckets
    session = aioboto3.Session(region_name='us-east-1')
    s3_config = Config(
        signature_version=UNSIGNED,
        connect_timeout=10,
        read_timeout=30,
        retries={'max_attempts': 2}
    )
    
    logger.info(f"Listing objects in s3://{bucket}/{prefix}")
    
    async with session.client('s3', config=s3_config) as s3:
        try:
            paginator = s3.get_paginator('list_objects_v2')
            objects = []
            
            async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' in page:
                    logger.info(f"Found {len(page['Contents'])} objects")
                    
                    for obj in page['Contents']:
                        if pattern is None or pattern in obj['Key']:
                            objects.append(obj)
                            if len(objects) >= limit:
                                break
                    
                    if len(objects) >= limit:
                        break
                else:
                    logger.warning(f"No objects found with prefix: {prefix}")
            
            return objects
        except Exception as e:
            logger.error(f"Error listing S3 objects: {e}")
            return []

async def download_s3_object(bucket: str, key: str, output_path: str) -> bool:
    """
    Download an S3 object to a local file.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        output_path: Local path to save the file
        
    Returns:
        True if download was successful, False otherwise
    """
    # Create S3 client with unsigned access for public buckets
    session = aioboto3.Session(region_name='us-east-1')
    s3_config = Config(
        signature_version=UNSIGNED,
        connect_timeout=10,
        read_timeout=30,
        retries={'max_attempts': 2}
    )
    
    logger.info(f"Downloading s3://{bucket}/{key} to {output_path}")
    
    # Create output directory if it doesn't exist
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    async with session.client('s3', config=s3_config) as s3:
        try:
            await s3.download_file(Bucket=bucket, Key=key, Filename=output_path)
            logger.info(f"Download successful: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error downloading S3 object: {e}")
            return False

async def test_scan_times(
    date: datetime,
    satellite: str,
    product_type: str,
    band: int,
    time_window_hours: int = 1
) -> None:
    """
    Test different scan times to find which ones exist.
    
    Args:
        date: Base date to test
        satellite: Satellite name (GOES_16 or GOES_18)
        product_type: Product type (RadF, RadC, or RadM)
        band: Band number (1-16)
        time_window_hours: Number of hours to test around the base date
    """
    satellite_code = SATELLITE_CODES.get(satellite)
    if not satellite_code:
        logger.error(f"Invalid satellite: {satellite}")
        return
    
    bucket = S3_BUCKETS.get(satellite)
    if not bucket:
        logger.error(f"Invalid satellite for bucket: {satellite}")
        return
    
    # Get appropriate scanning schedule for the product type
    scan_minutes = []
    if product_type == "RadF":
        scan_minutes = RADF_MINUTES
        logger.info(f"Using RadF scan minutes: {scan_minutes}")
    elif product_type == "RadC":
        scan_minutes = RADC_MINUTES
        logger.info(f"Using RadC scan minutes: {scan_minutes}")
    elif product_type == "RadM":
        scan_minutes = RADM_MINUTES[:10]  # Use only first 10 minutes for RadM to avoid too many tests
        logger.info(f"Using first 10 RadM scan minutes: {scan_minutes}")
    else:
        logger.error(f"Invalid product type: {product_type}")
        return
    
    # Set up time range
    start_time = date - timedelta(hours=time_window_hours//2)
    end_time = date + timedelta(hours=time_window_hours//2)
    
    logger.info(f"Testing scan times from {start_time.isoformat()} to {end_time.isoformat()}")
    logger.info(f"Satellite: {satellite} ({satellite_code}), Product: {product_type}, Band: {band}")
    
    # Test each hour in the time range
    current_time = start_time.replace(minute=0, second=0, microsecond=0)
    total_tests = 0
    total_found = 0
    
    while current_time <= end_time:
        # Test each scan minute for this hour
        for minute in scan_minutes:
            test_time = current_time.replace(minute=minute)
            
            # Generate S3 key with wildcard
            s3_key_prefix = to_s3_key(test_time, satellite_code, product_type, band, use_wildcard=True)
            
            # Split into directory prefix and filename pattern for listing
            if '*' in s3_key_prefix:
                prefix = s3_key_prefix.split('*')[0]
            else:
                prefix = s3_key_prefix
            
            # List objects matching the prefix
            objects = await list_s3_objects(bucket, prefix, limit=5)
            total_tests += 1
            
            if objects:
                total_found += 1
                logger.info(f"✅ Found {len(objects)} objects for {test_time.isoformat()}")
                
                # Print the first few object keys
                for i, obj in enumerate(objects[:3]):
                    logger.info(f"  {i+1}. {obj['Key']}")
                    logger.info(f"     Last modified: {obj['LastModified'].isoformat()}")
                    logger.info(f"     Size: {obj['Size']} bytes")
            else:
                logger.info(f"❌ No objects found for {test_time.isoformat()}")
        
        # Move to next hour
        current_time += timedelta(hours=1)
    
    # Summary
    if total_tests > 0:
        success_rate = (total_found / total_tests) * 100
        logger.info(f"Summary: Found data for {total_found} out of {total_tests} test times ({success_rate:.1f}% success rate)")
    else:
        logger.info("No tests were conducted")

async def test_exact_timestamps(
    date: datetime,
    satellite: str,
    product_type: str,
    band: int,
    download: bool = False
) -> None:
    """
    Test specific timestamps to find exact files.
    
    Args:
        date: Base date to test
        satellite: Satellite name (GOES_16 or GOES_18)
        product_type: Product type (RadF, RadC, or RadM)
        band: Band number (1-16)
        download: If True, download the found files
    """
    satellite_code = SATELLITE_CODES.get(satellite)
    if not satellite_code:
        logger.error(f"Invalid satellite: {satellite}")
        return
    
    bucket = S3_BUCKETS.get(satellite)
    if not bucket:
        logger.error(f"Invalid satellite for bucket: {satellite}")
        return
    
    # Get appropriate scanning schedule for the product type
    scan_minutes = []
    if product_type == "RadF":
        scan_minutes = RADF_MINUTES
        logger.info(f"Using RadF scan minutes: {scan_minutes}")
    elif product_type == "RadC":
        scan_minutes = RADC_MINUTES
        logger.info(f"Using RadC scan minutes: {scan_minutes}")
    elif product_type == "RadM":
        scan_minutes = RADM_MINUTES[:5]  # Use only first 5 minutes for RadM to avoid too many tests
        logger.info(f"Using first 5 RadM scan minutes: {scan_minutes}")
    else:
        logger.error(f"Invalid product type: {product_type}")
        return
    
    # Get the hour of the base date
    hour = date.hour
    base_date = date.replace(minute=0, second=0, microsecond=0)
    
    logger.info(f"Testing exact timestamps for {base_date.isoformat()} (hour {hour})")
    logger.info(f"Satellite: {satellite} ({satellite_code}), Product: {product_type}, Band: {band}")
    
    # Test each scan minute for this hour
    for minute in scan_minutes:
        test_time = base_date.replace(minute=minute)
        
        # Generate S3 key with wildcard for listing
        s3_key_prefix = to_s3_key(test_time, satellite_code, product_type, band, use_wildcard=True)
        
        # Split into directory prefix and filename pattern for listing
        if '*' in s3_key_prefix:
            prefix = s3_key_prefix.split('*')[0]
        else:
            prefix = s3_key_prefix
        
        # List objects matching the prefix
        objects = await list_s3_objects(bucket, prefix, limit=5)
        
        if objects:
            logger.info(f"✅ Found {len(objects)} objects for {test_time.isoformat()}")
            
            # Print all object keys and download if requested
            for i, obj in enumerate(objects):
                key = obj['Key']
                modified = obj['LastModified'].isoformat()
                size = obj['Size']
                
                logger.info(f"  {i+1}. {key}")
                logger.info(f"     Last modified: {modified}")
                logger.info(f"     Size: {size} bytes")
                
                if download:
                    # Create output directory based on date components
                    output_dir = Path("downloaded_files") / f"{date.year}" / f"{date.month:02d}" / f"{date.day:02d}"
                    output_path = output_dir / Path(key).name
                    
                    # Download the file
                    success = await download_s3_object(bucket, key, str(output_path))
                    if success:
                        logger.info(f"     Downloaded to: {output_path}")
                    else:
                        logger.error(f"     Failed to download: {output_path}")
        else:
            logger.info(f"❌ No objects found for {test_time.isoformat()}")

async def test_band_wildcards(
    date: datetime,
    satellite: str,
    product_type: str,
    hour_to_test: Optional[int] = None
) -> None:
    """
    Test listing files for multiple bands to see which bands are available.
    
    Args:
        date: Base date to test
        satellite: Satellite name (GOES_16 or GOES_18)
        product_type: Product type (RadF, RadC, or RadM)
        hour_to_test: Specific hour to test, or None to use the hour from date
    """
    satellite_code = SATELLITE_CODES.get(satellite)
    if not satellite_code:
        logger.error(f"Invalid satellite: {satellite}")
        return
    
    bucket = S3_BUCKETS.get(satellite)
    if not bucket:
        logger.error(f"Invalid satellite for bucket: {satellite}")
        return
    
    # Use specified hour or hour from date
    if hour_to_test is not None:
        test_date = date.replace(hour=hour_to_test, minute=0, second=0, microsecond=0)
    else:
        test_date = date.replace(minute=0, second=0, microsecond=0)
    
    logger.info(f"Testing band wildcards for {test_date.isoformat()}")
    logger.info(f"Satellite: {satellite} ({satellite_code}), Product: {product_type}")
    
    # Get year, day of year, and hour for constructing prefix
    year = test_date.year
    doy = date_to_doy(test_date.date())
    doy_str = f"{doy:03d}"
    hour = test_date.strftime("%H")
    
    # Use a more general prefix to catch files for all bands
    prefix = f"ABI-L1b-{product_type}/{year}/{doy_str}/{hour}/"
    
    # List objects with this prefix
    objects = await list_s3_objects(bucket, prefix, limit=50)
    
    if not objects:
        logger.warning(f"No objects found with prefix: {prefix}")
        return
    
    logger.info(f"Found {len(objects)} objects with prefix: {prefix}")
    
    # Extract band numbers from filenames
    band_counts = {}
    for obj in objects:
        key = obj['Key']
        # Pattern: OR_ABI-L1b-{product_type}-M6C{band}_{satellite_code}_s...
        if f"ABI-L1b-{product_type}-M6C" in key and f"_{satellite_code}_s" in key:
            try:
                # Extract the band number
                band_str = key.split(f"ABI-L1b-{product_type}-M6C")[1].split("_")[0]
                band_num = int(band_str)
                
                # Count occurrences of each band
                if band_num in band_counts:
                    band_counts[band_num] += 1
                else:
                    band_counts[band_num] = 1
                    
                # Print the first occurrence of each band
                if band_counts[band_num] == 1:
                    logger.info(f"Band {band_num}: {key}")
            except (ValueError, IndexError):
                logger.warning(f"Could not extract band number from key: {key}")
    
    # Sort bands by number and print summary
    sorted_bands = sorted(band_counts.keys())
    logger.info(f"Found data for {len(sorted_bands)} different bands:")
    for band in sorted_bands:
        logger.info(f"  Band {band}: {band_counts[band]} files")
    
    # Missing bands
    all_bands = set(range(1, 17))  # Bands 1-16
    missing_bands = all_bands - set(sorted_bands)
    if missing_bands:
        logger.info(f"Missing bands: {', '.join(str(b) for b in sorted(missing_bands))}")
    else:
        logger.info("All bands (1-16) are available for this timestamp")

async def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Test GOES S3 file access")
    parser.add_argument("--date", type=str, help="Date to test (YYYY-MM-DD or YYYY-MM-DD HH:MM)")
    parser.add_argument("--satellite", choices=["GOES_16", "GOES_18"], default="GOES_18",
                        help="Satellite to test")
    parser.add_argument("--product", choices=["RadF", "RadC", "RadM"], default="RadC",
                        help="Product type to test")
    parser.add_argument("--band", type=int, default=13, help="Band number to test (1-16)")
    parser.add_argument("--download", action="store_true", help="Download found files")
    parser.add_argument("--test-type", choices=["scan", "exact", "bands", "all"], default="all",
                        help="Type of test to run")
    
    args = parser.parse_args()
    
    # Parse date
    if args.date:
        try:
            if " " in args.date:
                # Date with time
                date = datetime.fromisoformat(args.date)
            else:
                # Date only
                date = datetime.fromisoformat(args.date + "T12:00:00")
        except ValueError:
            logger.error(f"Invalid date format: {args.date}")
            return
    else:
        # Use current date/time (UTC) minus 24 hours to ensure data exists
        date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    
    logger.info(f"Testing with date: {date.isoformat()}")
    logger.info(f"Satellite: {args.satellite}")
    logger.info(f"Product type: {args.product}")
    logger.info(f"Band: {args.band}")
    
    # Run the requested tests
    if args.test_type == "scan" or args.test_type == "all":
        await test_scan_times(date, args.satellite, args.product, args.band)
    
    if args.test_type == "exact" or args.test_type == "all":
        await test_exact_timestamps(date, args.satellite, args.product, args.band, args.download)
    
    if args.test_type == "bands" or args.test_type == "all":
        await test_band_wildcards(date, args.satellite, args.product)
    
    logger.info("Testing complete")

if __name__ == "__main__":
    asyncio.run(main())