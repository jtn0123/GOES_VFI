#!/usr/bin/env python
"""
Test script for downloading Band 13 (Clean IR) GOES files from AWS S3.

This script saves the downloaded files to a fixed directory for inspection.
"""

import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.utils import date_utils, log

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
LOGGER = log.get_logger(__name__)

# Set the download directory - create if it doesn't exist
DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/goes_downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def list_s3_objects_band13(bucket: str, prefix: str, limit: int = 10):
    """List Band 13 objects in an S3 bucket with the given prefix.

    Args:
        bucket: S3 bucket name
        prefix: Prefix to filter objects
        limit: Maximum number of objects to return

    Returns:
        List of S3 object keys for Band 13
    """
    LOGGER.info("Listing Band 13 objects in s3://%s/%s (limit: %s)", bucket, prefix, limit)

    import aioboto3
    from botocore import UNSIGNED
    from botocore.config import Config

    # Create a session with unsigned access (no credentials needed)
    session = aioboto3.Session()

    # Configure for unsigned access to public buckets
    config = Config(
        signature_version=UNSIGNED,
        connect_timeout=30,
        read_timeout=30,
        retries={"max_attempts": 3},
    )

    # Create S3 client
    async with session.client("s3", config=config) as s3:
        try:
            # Use paginator for listing objects
            paginator = s3.get_paginator("list_objects_v2")

            all_objects = []

            async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if "Contents" in page:
                    all_objects.extend(obj["Key"] for obj in page["Contents"])

            # Filter objects for Band 13 (C13)
            import re

            band13_pattern = re.compile(r"M6C13")
            band13_objects = [key for key in all_objects if band13_pattern.search(key)]

            # Sort by timestamp
            band13_objects = sorted(band13_objects)

            LOGGER.info("Found %s Band 13 objects out of %s total", len(band13_objects), len(all_objects))

            # Return the first 'limit' Band 13 objects
            return band13_objects[:limit]
        except Exception as e:
            LOGGER.exception("Error listing objects: %s", e)
            return []


async def test_download_band13(timestamp, satellite_pattern, product_type, dest_dir):
    """Test downloading a Band 13 file.

    Args:
        timestamp: Datetime object for the image
        satellite_pattern: SatellitePattern enum
        product_type: Product type ("RadF", "RadC", "RadM")
        dest_dir: Directory to save downloaded files

    Returns:
        Path to downloaded file if successful, None otherwise
    """
    LOGGER.info(
        "Testing download of Band 13 %s for %s at %s", product_type, satellite_pattern.name, timestamp.isoformat()
    )

    # Create S3 store
    s3_store = S3Store(timeout=60)

    try:
        # Get bucket name
        bucket = TimeIndex.get_s3_bucket(satellite_pattern)

        # Find the nearest valid timestamps for this product
        nearest_times = TimeIndex.find_nearest_intervals(timestamp, product_type)
        if not nearest_times:
            LOGGER.warning("No valid scan times found for %s", product_type)
            return None

        LOGGER.info("Found %s nearest scan times: %s", len(nearest_times), [t.isoformat() for t in nearest_times])

        # Convert date to DOY format
        year = timestamp.year
        doy = date_utils.date_to_doy(timestamp.date())
        doy_str = f"{doy:03d}"
        hour = timestamp.strftime("%H")

        # List Band 13 objects for this hour
        prefix = f"ABI-L1b-{product_type}/{year}/{doy_str}/{hour}/"
        band13_keys = await list_s3_objects_band13(bucket, prefix, limit=5)

        if not band13_keys:
            LOGGER.warning("No Band 13 files found for s3://%s/%s", bucket, prefix)
            return None

        # Try to download a single Band 13 file
        test_key = band13_keys[0]
        LOGGER.info("Testing download of key: s3://%s/%s", bucket, test_key)

        # Generate destination path with product type and satellite in the filename
        filename = f"{satellite_pattern.name}_{product_type}_Band13_{test_key.split('/')[-1]}"
        dest_path = dest_dir / filename

        # Create a file pattern for list_objects_v2 that uses actual pattern
        try:
            # Extract timestamp components from the filename
            # Format: OR_ABI-L1b-RadC-M6C13_G16_s20231661201176_e20231661203561_c20231661204041.nc
            import re

            # Filenames use a format like: s20231661201176 where:
            # - First 4 digits are year (2023)
            # - Next 3 digits are DOY (166)
            # - Next 2 digits are hour (12)
            # - Next 2 digits are minute (01)
            # - Next 3 digits are milliseconds or other precision info
            pattern = r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{3})_"
            match = re.search(pattern, test_key)

            if match:
                # Extract components
                file_year = int(match.group(1))
                file_doy = int(match.group(2))
                file_hour = int(match.group(3))
                file_minute = int(match.group(4))
                # The last 3 digits are not seconds - they're milliseconds or tenths of seconds
                # Just use 0 for seconds to avoid the "second must be in 0..59" error

                # Convert DOY to date
                date_obj = date_utils.doy_to_date(file_year, file_doy)

                # Create timestamp for download
                file_ts = datetime(
                    date_obj.year,
                    date_obj.month,
                    date_obj.day,
                    hour=file_hour,
                    minute=file_minute,
                    second=0,  # Use 0 for seconds to avoid errors
                )

                LOGGER.info("Extracted timestamp: %s", file_ts.isoformat())

                # Fix for product type - we need to search in the correct directory
                search_product_type = product_type

                # Now try to download using the S3Store's band support
                await s3_store.download(
                    file_ts,
                    satellite_pattern,
                    dest_path,
                    product_type=search_product_type,
                    band=13,  # Explicitly request Band 13
                )

                if dest_path.exists():
                    file_size = dest_path.stat().st_size
                    LOGGER.info("✓ Successfully downloaded to %s (%s bytes)", dest_path, file_size)
                    return dest_path
                LOGGER.error("✗ Download failed: File doesn't exist at %s", dest_path)
                return None
            LOGGER.error("✗ Failed to extract timestamp from filename: %s", test_key)
            return None
        except Exception as e:
            LOGGER.exception("✗ Error during download: %s", e)
            return None

    except Exception as e:
        LOGGER.exception("✗ Error: %s", e)
        return None
    finally:
        # Close the S3 store
        await s3_store.close()


async def download_fixed_list():
    """Download specific Band 13 files that we know exist."""
    # Set of specific files known to be available for Band 13
    KNOWN_FILES = [
        # GOES-16 RadC
        (
            "noaa-goes16",
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661201176_e20231661203561_c20231661204041.nc",
        ),
        # GOES-18 RadC
        (
            "noaa-goes18",
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G18_s20231661201181_e20231661203567_c20231661204040.nc",
        ),
    ]

    downloaded_files = []

    for bucket, key in KNOWN_FILES:
        LOGGER.info("Downloading known file: s3://%s/%s", bucket, key)

        # Create S3 store
        s3_store = S3Store(timeout=60)

        try:
            import aioboto3
            from botocore import UNSIGNED
            from botocore.config import Config

            # Create a session with unsigned access (no credentials needed)
            session = aioboto3.Session()

            # Configure for unsigned access to public buckets
            config = Config(
                signature_version=UNSIGNED,
                connect_timeout=30,
                read_timeout=30,
                retries={"max_attempts": 3},
            )

            # Create destination path
            filename = key.split("/")[-1]
            sat_name = "GOES16" if bucket == "noaa-goes16" else "GOES18"
            dest_path = DOWNLOAD_DIR / f"{sat_name}_{filename}"

            # Create S3 client and download
            async with session.client("s3", config=config) as s3:
                LOGGER.info("Downloading to %s", dest_path)
                await s3.download_file(Bucket=bucket, Key=key, Filename=str(dest_path))

                if dest_path.exists():
                    file_size = dest_path.stat().st_size
                    LOGGER.info("✓ Successfully downloaded to %s (%s bytes)", dest_path, file_size)
                    downloaded_files.append(dest_path)
                else:
                    LOGGER.error("✗ Download failed: File doesn't exist at %s", dest_path)
        except Exception as e:
            LOGGER.exception("✗ Error downloading %s: %s", key, e)
        finally:
            await s3_store.close()

    return downloaded_files


async def main() -> None:
    """Main entry point for the script."""
    LOGGER.info("Downloading files to: %s", DOWNLOAD_DIR)

    # First try the dynamic approach
    test_time = datetime(2023, 6, 15, 12, 0, 0)
    LOGGER.info("Testing with timestamp: %s", test_time.isoformat())

    # Test with GOES-16 and GOES-18
    satellites = [
        (SatellitePattern.GOES_16, "GOES-16"),
        (SatellitePattern.GOES_18, "GOES-18"),
    ]

    # Test with RadF, RadC, and RadM product types
    product_types = ["RadF", "RadC", "RadM"]

    results: dict[str, dict] = {}
    downloaded_files: list[str] = []

    for satellite, sat_name in satellites:
        results[sat_name] = {}

        for product_type in product_types:
            downloaded_path = await test_download_band13(test_time, satellite, product_type, DOWNLOAD_DIR)
            results[sat_name][product_type] = downloaded_path is not None
            if downloaded_path:
                downloaded_files.append(downloaded_path)

    # If dynamic approach didn't work well, try direct downloads
    if not downloaded_files:
        LOGGER.info("Dynamic approach failed, trying direct downloads of known files")
        downloaded_files = await download_fixed_list()

    # Print final summary
    LOGGER.info("\n=== TEST SUMMARY ===")
    for satellite, products in results.items():
        successful = [p for p, s in products.items() if s]
        failed = [p for p, s in products.items() if not s]

        LOGGER.info("%s: %s/%s successful", satellite, len(successful), len(products))
        LOGGER.info("  Successful: %s", ", ".join(successful) if successful else "None")
        LOGGER.info("  Failed: %s", ", ".join(failed) if failed else "None")

    # List all downloaded files
    LOGGER.info("\n=== DOWNLOADED FILES ===")
    for i, path in enumerate(downloaded_files):
        LOGGER.info("%s. %s (%s bytes)", i + 1, path, path.stat().st_size)

    LOGGER.info("\nDownloaded files are saved in: %s", DOWNLOAD_DIR)
    LOGGER.info("Please check this directory to view the downloaded files.")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
