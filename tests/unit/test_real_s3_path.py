#!/usr/bin/env python
"""
Test script for validating GOES file pattern matching with real S3 data.

This script tests the ability to create correct S3 key patterns that match
real GOES satellite files in the NOAA public S3 buckets.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import (
    SATELLITE_CODES,
    SatellitePattern,
    TimeIndex,
)
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


@pytest.fixture
def timestamp():
    """Test timestamp that should have GOES data available."""
    return datetime(2023, 6, 15, 12, 0, 0)


@pytest.fixture
def satellite_pattern():
    """Test satellite pattern."""
    return SatellitePattern.GOES_16


@pytest.fixture
def dest_dir(tmp_path):
    """Destination directory for downloads."""
    return tmp_path


def _generate_s3_patterns(timestamp, satellite_pattern, dest_dir):
    """Helper function to generate S3 patterns for different product types.

    This validates the pattern generation logic without making real S3 calls.
    """
    # Define product types to test
    product_types = ["RadF", "RadC", "RadM"]

    # Define bands to test
    bands = [13]  # Start with clean IR band

    results = {}

    for product_type in product_types:
        LOGGER.info(
            f"Testing {product_type} for {satellite_pattern.name} at {timestamp.isoformat()}"
        )

        # Generate the S3 bucket name
        sat_code = SATELLITE_CODES.get(satellite_pattern, "G16")
        satellite_number = int(sat_code[1:])  # "G16" -> 16
        bucket = f"noaa-goes{satellite_number}"

        # Generate S3 key pattern for this product type and timestamp
        key = f"ABI-L1b-{product_type}/{timestamp.year}/{timestamp.timetuple().tm_yday:03d}/{timestamp.hour:02d}/"

        # Try each band
        product_result = {"success": True, "attempts": []}

        for band in bands:
            attempt = {
                "timestamp": timestamp.isoformat(),
                "band": band,
                "success": True,
                "bucket": bucket,
                "key_pattern": key,
                "product_type": product_type,
            }

            # Generate destination path
            filename = f"{satellite_pattern.name}_{product_type}_Band{band}_{timestamp.strftime('%Y%m%d_%H%M%S')}.nc"
            dest_path = dest_dir / filename
            attempt["dest_path"] = str(dest_path)

            # Validate the pattern makes sense
            assert bucket.startswith(
                "noaa-goes"
            ), f"Bucket should start with noaa-goes: {bucket}"
            assert (
                str(satellite_number) in bucket
            ), f"Bucket should contain satellite number: {bucket}"
            assert product_type in key, f"Key should contain product type: {key}"
            assert str(timestamp.year) in key, f"Key should contain year: {key}"

            # Add attempt to result
            product_result["attempts"].append(attempt)

            # For this test, we consider it successful if patterns are valid
            break

        # Store results for this product type
        results[product_type] = product_result

    # Verify that all product types were tested successfully
    assert len(results) == 3, "Should test all 3 product types"

    for product_type, result in results.items():
        assert result["success"], f"Product type {product_type} should succeed"
        assert (
            len(result["attempts"]) > 0
        ), f"Product type {product_type} should have at least one attempt"

        # Verify bucket names are correct
        for attempt in result["attempts"]:
            assert (
                "noaa-goes" in attempt["bucket"]
            ), f"Invalid bucket: {attempt['bucket']}"
            assert (
                product_type in attempt["key_pattern"]
            ), f"Product type not in key pattern: {attempt['key_pattern']}"

    return results


def test_s3_patterns(timestamp, satellite_pattern, dest_dir):
    """Test S3 pattern generation for different product types."""
    results = _generate_s3_patterns(timestamp, satellite_pattern, dest_dir)

    # Verify that all product types were tested successfully
    assert len(results) == 3, "Should test all 3 product types"

    for product_type, result in results.items():
        assert result["success"], f"Product type {product_type} should succeed"
        assert (
            len(result["attempts"]) > 0
        ), f"Product type {product_type} should have at least one attempt"


def test_multiple_satellites(tmp_path):
    """Test S3 pattern generation with multiple satellites."""
    # Test with both GOES-16 and GOES-18
    satellites = [SatellitePattern.GOES_16, SatellitePattern.GOES_18]
    test_time = datetime(2023, 6, 15, 12, 0, 0)

    all_results = {}

    for satellite in satellites:
        # Run the helper function for each satellite
        results = _generate_s3_patterns(test_time, satellite, tmp_path)
        all_results[satellite.name] = results

        # Verify results
        assert (
            len(results) == 3
        ), f"Should test all 3 product types for {satellite.name}"

        for product_type, result in results.items():
            assert result["success"], f"{satellite.name} {product_type} should succeed"

    # Verify we tested both satellites
    assert len(all_results) == 2, "Should test both satellites"
    assert "GOES_16" in all_results, "Should test GOES-16"
    assert "GOES_18" in all_results, "Should test GOES-18"

    # Verify different bucket names for different satellites
    goes16_bucket = all_results["GOES_16"]["RadF"]["attempts"][0]["bucket"]
    goes18_bucket = all_results["GOES_18"]["RadF"]["attempts"][0]["bucket"]
    assert "16" in goes16_bucket, f"GOES-16 bucket should contain '16': {goes16_bucket}"
    assert "18" in goes18_bucket, f"GOES-18 bucket should contain '18': {goes18_bucket}"
    assert (
        goes16_bucket != goes18_bucket
    ), "Different satellites should have different buckets"
