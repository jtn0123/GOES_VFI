#!/usr/bin/env python
"""
Test script for validating GOES file pattern matching with real S3 data.

This script tests the ability to create correct S3 key patterns that match
real GOES satellite files in the NOAA public S3 buckets.
"""

import asyncio
import logging
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.utils import date_utils, log

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
LOGGER = log.get_logger(__name__)


async def test_s3_patterns(timestamp, satellite_pattern, dest_dir):
    """Test S3 pattern generation and file download for different product types.

    Args:
        timestamp: Datetime object for the image
        satellite_pattern: SatellitePattern enum
        dest_dir: Directory to save downloaded files

    Returns:
        Dictionary with results for each product type
    """
    # Create S3 store with increased timeout
    s3_store = S3Store(timeout=60)

    # Define product types to test
    product_types = ["RadF", "RadC", "RadM"]

    # Define bands to test
    bands = [13]  # Start with clean IR band

    results = {}

    for product_type in product_types:
        LOGGER.info(
            f"Testing {product_type} for {satellite_pattern.name} at {timestamp.isoformat()}"
        )

        # Find the nearest valid timestamps for this product
        nearest_times = TimeIndex.find_nearest_intervals(timestamp, product_type)
        if not nearest_times:
            LOGGER.warning(f"No valid scan times found for {product_type}")
            results[product_type] = {
                "success": False,
                "error": "No valid scan times found",
            }
            continue

        LOGGER.info(
            f"Found {len(nearest_times)} nearest scan times: {[t.isoformat() for t in nearest_times]}"
        )

        # Try each nearest time
        product_result = {"success": False, "attempts": []}

        for ts in nearest_times:
            # Try each band
            for band in bands:
                attempt = {"timestamp": ts.isoformat(), "band": band, "success": False}

                try:
                    # Generate destination path
                    filename = f"{satellite_pattern.name}_{product_type}_Band{band}_{ts.strftime('%Y%m%d_%H%M%S')}.nc"
                    dest_path = dest_dir / filename

                    # Generate the S3 key pattern
                    bucket = TimeIndex.get_s3_bucket(satellite_pattern)
                    key = TimeIndex.to_s3_key(
                        ts, satellite_pattern, product_type=product_type, band=band
                    )

                    LOGGER.info(f"Trying to access s3://{bucket}/{key} -> {dest_path}")

                    # Check if file exists
                    exists = await s3_store.exists(
                        ts, satellite_pattern, product_type=product_type, band=band
                    )
                    attempt["exists"] = exists

                    if exists:
                        # Download the file
                        LOGGER.info(f"File exists! Downloading...")
                        result_path = await s3_store.download(
                            ts,
                            satellite_pattern,
                            dest_path,
                            product_type=product_type,
                            band=band,
                        )

                        # Check the downloaded file
                        if result_path.exists():
                            file_size = result_path.stat().st_size
                            attempt["success"] = True
                            attempt["file_size"] = file_size
                            attempt["file_path"] = str(result_path)

                            LOGGER.info(
                                f"✓ Successfully downloaded file: {result_path} ({file_size} bytes)"
                            )

                            # Success for this product type
                            product_result["success"] = True
                        else:
                            attempt[
                                "error"
                            ] = "File reported as downloaded but doesn't exist"
                            LOGGER.error(
                                f"✗ Download failed: File doesn't exist at {dest_path}"
                            )
                    else:
                        attempt["error"] = "File doesn't exist in S3"
                        LOGGER.warning(f"✗ File doesn't exist: s3://{bucket}/{key}")

                except Exception as e:
                    attempt["error"] = str(e)
                    attempt["exception_type"] = type(e).__name__
                    LOGGER.error(f"✗ Error: {e}")

                # Add attempt to result
                product_result["attempts"].append(attempt)

                # If successful, we can stop trying more bands
                if attempt["success"]:
                    break

            # If successful with any band, we can stop trying more timestamps
            if product_result["success"]:
                break

        # Store results for this product type
        results[product_type] = product_result

    # Close the S3 store
    await s3_store.close()

    return results


async def main():
    """Main entry point for the script."""
    # Create a temporary directory for downloads
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_dir = Path(temp_dir)

        # Use a specific timestamp that we know has data available
        # June 15, 2023 at 12:00 UTC should have GOES data available
        test_time = datetime(2023, 6, 15, 12, 0, 0)

        LOGGER.info(f"Testing with timestamp: {test_time.isoformat()}")

        # Test with GOES-16 and GOES-18
        satellites = [SatellitePattern.GOES_16, SatellitePattern.GOES_18]

        all_results = {}

        for satellite in satellites:
            LOGGER.info(f"Testing {satellite.name}...")

            # Run the test
            results = await test_s3_patterns(test_time, satellite, dest_dir)

            # Store results
            all_results[satellite.name] = results

            # Quick summary
            for product_type, result in results.items():
                if result["success"]:
                    LOGGER.info(f"✓ {satellite.name} {product_type}: SUCCESS")
                else:
                    LOGGER.info(f"✗ {satellite.name} {product_type}: FAILED")

        # Print final summary
        LOGGER.info("\n=== TEST SUMMARY ===")
        for satellite, results in all_results.items():
            successful_products = [p for p, r in results.items() if r["success"]]
            failed_products = [p for p, r in results.items() if not r["success"]]

            LOGGER.info(
                f"{satellite}: {len(successful_products)}/{len(results)} successful"
            )
            LOGGER.info(
                f"  Successful: {', '.join(successful_products) if successful_products else 'None'}"
            )
            LOGGER.info(
                f"  Failed: {', '.join(failed_products) if failed_products else 'None'}"
            )


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
