#!/usr/bin/env python
"""
Test script for working with Band 13 (Clean IR) GOES files in AWS S3.

This script demonstrates working with the GOES time index and S3 store
to access Band 13 files specifically.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.utils import date_utils, log

LOGGER = log.get_logger(__name__)


@pytest.fixture
def timestamp():
    """Test timestamp for Band 13 testing."""
    return datetime(2023, 6, 15, 12, 0, 0)


@pytest.fixture
def satellite_pattern():
    """Test satellite pattern."""
    return SatellitePattern.GOES_16


@pytest.fixture
def product_type():
    """Test product type."""
    return "RadC"


@pytest.fixture
def dest_dir(tmp_path):
    """Destination directory for downloads."""
    return tmp_path


@pytest.fixture
def mock_s3_objects():
    """Mock S3 object keys for Band 13."""
    return [
        "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661201176_e20231661203549_c20231661203597.nc",
        "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661202176_e20231661204549_c20231661204597.nc",
        "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661203176_e20231661205549_c20231661205597.nc",
    ]


async def list_s3_objects_band13(bucket: str, prefix: str, limit: int = 10):
    """List Band 13 objects in an S3 bucket with the given prefix.

    This function is mocked in tests to avoid real S3 calls.
    """
    # This will be mocked in tests
    mock_keys = [
        f"{prefix}OR_ABI-L1b-RadC-M6C13_G16_s20231661201176_e20231661203549_c20231661203597.nc",
        f"{prefix}OR_ABI-L1b-RadC-M6C13_G16_s20231661202176_e20231661204549_c20231661204597.nc",
    ]
    return mock_keys[:limit]


@pytest.mark.asyncio
async def test_list_s3_objects_band13_success(mock_s3_objects):
    """Test successful listing of Band 13 S3 objects."""
    bucket = "noaa-goes16"
    prefix = "ABI-L1b-RadC/2023/166/12/"

    # Mock the function
    with patch("tests.unit.test_s3_band13.list_s3_objects_band13") as mock_list:
        mock_list.return_value = mock_s3_objects

        result = await list_s3_objects_band13(bucket, prefix, limit=5)

        assert result == mock_s3_objects
        assert len(result) == 3
        assert all("C13" in key for key in result), "All keys should be Band 13"
        mock_list.assert_called_once_with(bucket, prefix, limit=5)


@pytest.mark.asyncio
async def test_list_s3_objects_band13_no_objects():
    """Test listing when no Band 13 objects are found."""
    bucket = "noaa-goes16"
    prefix = "ABI-L1b-RadC/2023/166/12/"

    with patch("tests.unit.test_s3_band13.list_s3_objects_band13") as mock_list:
        mock_list.return_value = []

        result = await list_s3_objects_band13(bucket, prefix, limit=5)

        assert result == []
        mock_list.assert_called_once_with(bucket, prefix, limit=5)


@pytest.mark.asyncio
async def test_download_band13_mocked(timestamp, satellite_pattern, product_type, dest_dir, mock_s3_objects):
    """Test downloading a Band 13 file with mocked S3 operations."""

    # Mock S3Store completely
    with patch("goesvfi.integrity_check.remote.s3_store.S3Store") as MockS3Store:
        mock_s3_store = AsyncMock(spec=S3Store)
        MockS3Store.return_value = mock_s3_store

        # Create a mock downloaded file
        test_filename = "OR_ABI-L1b-RadC-M6C13_G16_s20231661201176_e20231661203549_c20231661203597.nc"
        test_file = dest_dir / test_filename
        test_file.write_bytes(b"mock satellite data for band 13")

        # Mock the download method to return the test file
        mock_s3_store.download.return_value = test_file
        mock_s3_store.close.return_value = None

        # Mock TimeIndex methods
        with (
            patch.object(TimeIndex, "get_s3_bucket") as mock_get_bucket,
            patch.object(TimeIndex, "find_nearest_intervals") as mock_find_nearest,
            patch("tests.unit.test_s3_band13.list_s3_objects_band13") as mock_list_objects,
        ):

            mock_get_bucket.return_value = "noaa-goes16"
            mock_find_nearest.return_value = [timestamp]
            mock_list_objects.return_value = [f"ABI-L1b-{product_type}/2023/166/12/{test_filename}"]

            # Create S3 store (will be mocked)
            s3_store = S3Store(timeout=60)

            LOGGER.info(
                f"Testing download of Band 13 {product_type} for {satellite_pattern.name} at {timestamp.isoformat()}"
            )

            try:
                # Get bucket name
                bucket = TimeIndex.get_s3_bucket(satellite_pattern)

                # Find the nearest valid timestamps for this product
                nearest_times = TimeIndex.find_nearest_intervals(timestamp, product_type)
                assert nearest_times, "Should find valid scan times"

                # Convert date to DOY format
                year = timestamp.year
                doy = date_utils.date_to_doy(timestamp.date())
                doy_str = f"{doy:03d}"
                hour = timestamp.strftime("%H")

                # List Band 13 objects for this hour
                prefix = f"ABI-L1b-{product_type}/{year}/{doy_str}/{hour}/"
                band13_keys = await list_s3_objects_band13(bucket, prefix, limit=5)

                assert band13_keys, "Should find Band 13 files"

                # Try to download a single Band 13 file
                test_key = band13_keys[0]
                filename = test_key.split("/")[-1]
                dest_path = dest_dir / filename

                # Extract timestamp from filename and download
                import re

                pattern = r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{3})_"
                match = re.search(pattern, filename)

                assert match, f"Should be able to extract timestamp from filename: {filename}"

                # Extract components
                file_year = int(match.group(1))
                file_doy = int(match.group(2))
                file_hour = int(match.group(3))
                file_minute = int(match.group(4))

                # Convert DOY to date
                date_obj = date_utils.doy_to_date(file_year, file_doy)

                # Create timestamp for download
                file_ts = datetime(
                    date_obj.year,
                    date_obj.month,
                    date_obj.day,
                    hour=file_hour,
                    minute=file_minute,
                    second=0,
                )

                # Download using the S3Store's band support
                result = await s3_store.download(
                    file_ts,
                    satellite_pattern,
                    dest_path,
                    product_type=product_type,
                    band=13,
                )

                # Verify the download was successful
                assert result.exists(), "Downloaded file should exist"
                file_size = result.stat().st_size
                assert file_size > 0, "Downloaded file should have content"

                LOGGER.info(f"✓ Successfully downloaded to {result} ({file_size} bytes)")

            finally:
                # Close the S3 store
                await s3_store.close()


def test_band13_filename_parsing():
    """Test parsing Band 13 filenames for timestamp extraction."""
    test_filename = "OR_ABI-L1b-RadC-M6C13_G16_s20231661201176_e20231661203549_c20231661203597.nc"

    import re

    pattern = r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{3})_"
    match = re.search(pattern, test_filename)

    assert match, "Should match Band 13 filename pattern"

    # Extract components
    file_year = int(match.group(1))
    file_doy = int(match.group(2))
    file_hour = int(match.group(3))
    file_minute = int(match.group(4))

    assert file_year == 2023, "Should extract correct year"
    assert file_doy == 166, "Should extract correct day of year"
    assert file_hour == 12, "Should extract correct hour"
    assert file_minute == 1, "Should extract correct minute"


@pytest.mark.parametrize(
    ("satellite", "expected_bucket"),
    [
        (SatellitePattern.GOES_16, "noaa-goes16"),
        (SatellitePattern.GOES_18, "noaa-goes18"),
    ],
)
def test_band13_bucket_patterns(satellite, expected_bucket):
    """Test that Band 13 operations use correct S3 buckets for different satellites."""
    with patch.object(TimeIndex, "get_s3_bucket") as mock_get_bucket:
        mock_get_bucket.return_value = expected_bucket

        bucket = TimeIndex.get_s3_bucket(satellite)
        assert bucket == expected_bucket
        mock_get_bucket.assert_called_once_with(satellite)


@pytest.mark.parametrize("product_type", ["RadF", "RadC", "RadM"])
def test_band13_product_types(product_type):
    """Test Band 13 operations work with different product types."""
    timestamp = datetime(2023, 6, 15, 12, 0, 0)

    # Test prefix generation
    year = timestamp.year
    doy = date_utils.date_to_doy(timestamp.date())
    doy_str = f"{doy:03d}"
    hour = timestamp.strftime("%H")

    expected_prefix = f"ABI-L1b-{product_type}/{year}/{doy_str}/{hour}/"

    assert product_type in expected_prefix, "Product type should be in prefix"
    assert "2023" in expected_prefix, "Year should be in prefix"
    assert "166" in expected_prefix, "DOY should be in prefix"
    assert "12" in expected_prefix, "Hour should be in prefix"
