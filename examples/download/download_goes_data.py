#!/usr/bin/env python3
"""
Download GOES satellite data from AWS S3 buckets.
This script uses anonymous access to download GOES-16 and GOES-18 satellite imagery.
"""
import asyncio
import os
import logging
from datetime import datetime
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("download_goes_data")

# Constants
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_downloads"))
SATELLITES = {
    "GOES-16": "noaa-goes16",
    "GOES-18": "noaa-goes18"
}
PRODUCT_TYPES = {
    "RadF": "Full Disk",
    "RadC": "CONUS",
    "RadM": "Mesoscale"
}
ALL_BANDS = list(range(1, 17))  # Bands 1-16

# Create download directory
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Configure anonymous access to S3
s3_config = Config(
    signature_version=UNSIGNED,
    region_name="us-east-1",
    retries={"max_attempts": 3, "mode": "standard"},
    read_timeout=300,  # 5 minutes
    connect_timeout=30
)


async def list_s3_files(bucket, prefix):
    """List files in S3 bucket with given prefix."""
    s3 = boto3.client("s3", config=s3_config)
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if "Contents" in response:
            return [obj["Key"] for obj in response["Contents"]]
        return []
    except Exception as e:
        logger.error(f"Error listing files in {bucket}/{prefix}: {e}")
        return []


async def download_file(bucket, key, dest_path):
    """Download a file from S3."""
    s3 = boto3.client("s3", config=s3_config)
    try:
        logger.info(f"Downloading {bucket}/{key} to {dest_path}")
        s3.download_file(bucket, key, str(dest_path))
        file_size = dest_path.stat().st_size
        logger.info(f"Downloaded {dest_path.name} ({file_size:,} bytes)")
        return True
    except Exception as e:
        logger.error(f"Failed to download {key}: {e}")
        return False


async def download_product(satellite, product_type, bands, date_str, hour="12"):
    """Download files for a specific product type and bands."""
    bucket_name = SATELLITES[satellite]
    satellite_abbr = satellite.replace("GOES-", "G")  # GOES-16 -> G16
    
    success_count = 0
    failed_count = 0
    
    # Create product directory
    product_dir = DOWNLOAD_DIR / product_type
    product_dir.mkdir(exist_ok=True)
    
    for band in bands:
        # Format band as two digits (e.g., 01, 02, ...)
        band_str = f"C{band:02d}"
        
        # Generate the S3 prefix for this product and hour
        prefix = f"ABI-L1b-{product_type}/{date_str}/{hour}/"
        
        # Find files for this band
        all_files = await list_s3_files(bucket_name, prefix)
        matching_files = [f for f in all_files if band_str in f and f.endswith(".nc")]
        
        if matching_files:
            # Take the first matching file
            file_key = matching_files[0]
            
            # Create a descriptive filename
            local_filename = f"{satellite_abbr}_{product_type}_Band{band:02d}_{os.path.basename(file_key)}"
            local_path = product_dir / local_filename
            
            # Download the file
            success = await download_file(bucket_name, file_key, local_path)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
        else:
            logger.warning(f"No files found for {satellite} {product_type} Band {band}")
            failed_count += 1
    
    return success_count, failed_count


async def download_mesoscale(satellite, bands, date_str, hour="12", minutes=["00", "01", "02", "03", "15", "30", "31", "32", "45"]):
    """Download Mesoscale files, which require special handling."""
    bucket_name = SATELLITES[satellite]
    satellite_abbr = satellite.replace("GOES-", "G")  # GOES-16 -> G16
    product_type = "RadM"
    
    success_count = 0
    failed_count = 0
    
    # Create product directories for M1 and M2
    m1_dir = DOWNLOAD_DIR / "RadM" / "M1"
    m2_dir = DOWNLOAD_DIR / "RadM" / "M2"
    m1_dir.mkdir(parents=True, exist_ok=True)
    m2_dir.mkdir(parents=True, exist_ok=True)
    
    # Try additional hours if necessary
    available_hours = [hour]
    if hour != "13":
        available_hours.append("13")
    if hour != "14":
        available_hours.append("14")
    
    # Check if RadM directory exists for this date
    for check_hour in available_hours:
        prefix = f"ABI-L1b-{product_type}/{date_str}/{check_hour}/"
        logger.info(f"Checking for Mesoscale data in {bucket_name}/{prefix}")
        
        # Just list the directory to see if it exists and has contents
        all_files = await list_s3_files(bucket_name, prefix)
        if all_files:
            logger.info(f"Found {len(all_files)} files in {prefix}")
            # List a few minute directories
            minute_prefixes = set()
            for file_key in all_files[:20]:  # Look at first 20 files
                parts = file_key.split('/')
                if len(parts) > 5:  # Should have minute directory
                    minute_prefixes.add(parts[4])  # The minute directory
            
            if minute_prefixes:
                logger.info(f"Available minute directories: {sorted(minute_prefixes)}")
    
    for band in bands:
        # Format band as two digits
        band_str = f"C{band:02d}"
        found_m1 = False
        found_m2 = False
        
        for check_hour in available_hours:
            # Try different minutes to find both M1 and M2 files
            for minute in minutes:
                # Generate the S3 prefix for this minute
                prefix = f"ABI-L1b-{product_type}/{date_str}/{check_hour}/{minute}/"
                
                # Find files for this band
                all_files = await list_s3_files(bucket_name, prefix)
                matching_files = [f for f in all_files if band_str in f and f.endswith(".nc")]
                
                if matching_files:
                    logger.info(f"Found {len(matching_files)} {band_str} files in {prefix}")
                
                for file_key in matching_files:
                    # Determine if this is M1 or M2 based on the timestamp in filename
                    # Parse out the timestamp which is after "_s" and before "_e"
                    timestamp_match = file_key.split("_s")[1].split("_e")[0]
                    # Use second digit from the timestamp's seconds portion to determine M1/M2
                    # This is a simplified approach, adapt with actual observation of file patterns
                    region = "M1" if int(timestamp_match[-2]) % 2 == 0 else "M2"
                    target_dir = m1_dir if region == "M1" else m2_dir
                    
                    logger.info(f"File {os.path.basename(file_key)} appears to be a {region} file based on timestamp {timestamp_match}")
                    
                    if region == "M1" and not found_m1:
                        # Create a descriptive filename
                        local_filename = f"{satellite_abbr}_RadM_{region}_Band{band:02d}_{os.path.basename(file_key)}"
                        local_path = target_dir / local_filename
                        
                        # Download the file
                        success = await download_file(bucket_name, file_key, local_path)
                        if success:
                            success_count += 1
                            found_m1 = True
                        else:
                            failed_count += 1
                    
                    elif region == "M2" and not found_m2:
                        # Create a descriptive filename
                        local_filename = f"{satellite_abbr}_RadM_{region}_Band{band:02d}_{os.path.basename(file_key)}"
                        local_path = target_dir / local_filename
                        
                        # Download the file
                        success = await download_file(bucket_name, file_key, local_path)
                        if success:
                            success_count += 1
                            found_m2 = True
                        else:
                            failed_count += 1
                    
                    # If we found both M1 and M2, move to the next band
                    if found_m1 and found_m2:
                        break
                
                # If we found both M1 and M2, move to the next band
                if found_m1 and found_m2:
                    break
            
            # If we found both M1 and M2, move to the next band
            if found_m1 and found_m2:
                break
        
        # Count failures if we didn't find M1 or M2
        if not found_m1:
            logger.warning(f"No M1 files found for {satellite} Band {band}")
            failed_count += 1
        if not found_m2:
            logger.warning(f"No M2 files found for {satellite} Band {band}")
            failed_count += 1
    
    return success_count, failed_count


async def main():
    """Main function to download GOES satellite data."""
    # Sample bands to download (to keep the test manageable)
    # These represent key spectral ranges:
    # - Band 2 (Visible Blue)
    # - Band 3 (Visible Green)
    # - Band 8 (Near-IR water vapor)
    # - Band 13 (Clean IR longwave window)
    test_bands = [2, 3, 8, 13]  
    
    # Test date: June 15th, 2023 (DOY 166)
    test_date = "2023/166"
    test_hour = "12"
    test_minutes = ["00", "01", "30", "31"]
    
    logger.info(f"Starting GOES satellite data download to {DOWNLOAD_DIR}")
    results = {}
    
    # Download data for both satellites
    for satellite_name, bucket in SATELLITES.items():
        satellite_results = {}
        
        # Download Full Disk (RadF) data
        logger.info(f"Downloading {satellite_name} Full Disk (RadF) data...")
        success, failed = await download_product(
            satellite_name, "RadF", test_bands, test_date, test_hour
        )
        satellite_results["RadF"] = {"success": success, "failed": failed}
        
        # Download CONUS (RadC) data
        logger.info(f"Downloading {satellite_name} CONUS (RadC) data...")
        success, failed = await download_product(
            satellite_name, "RadC", test_bands, test_date, test_hour
        )
        satellite_results["RadC"] = {"success": success, "failed": failed}
        
        # Download Mesoscale (RadM) data
        logger.info(f"Downloading {satellite_name} Mesoscale (RadM) data...")
        success, failed = await download_mesoscale(
            satellite_name, test_bands, test_date, test_hour, test_minutes
        )
        satellite_results["RadM"] = {"success": success, "failed": failed}
        
        results[satellite_name] = satellite_results
    
    # Print summary
    logger.info("\n=== Download Summary ===")
    
    for satellite, products in results.items():
        logger.info(f"\n{satellite}:")
        
        total_success = 0
        total_failed = 0
        
        for product_type, counts in products.items():
            product_name = PRODUCT_TYPES.get(product_type, product_type)
            success = counts["success"]
            failed = counts["failed"]
            total = success + failed
            
            logger.info(f"  {product_name} ({product_type}): {success}/{total} files downloaded successfully")
            total_success += success
            total_failed += failed
        
        logger.info(f"  Total: {total_success}/{total_success + total_failed} files downloaded successfully")
    
    logger.info(f"\nAll downloads completed. Files saved to: {DOWNLOAD_DIR}")


if __name__ == "__main__":
    asyncio.run(main())