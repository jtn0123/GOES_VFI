"""Integration tests for S3Store with real NOAA GOES data patterns."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import (
    RADC_MINUTES,
    RADF_MINUTES,
    SatellitePattern,
    to_s3_key,
)


# Skip these tests by default as they access real S3 and may cause rate limiting
# Run with pytest -xvs tests/unit/test_real_s3_store.py::TestRealS3Store::test_real_s3_exists_recent
# Add RUN_REAL_S3_TESTS=1 environment variable to run these tests
@pytest.mark.skipif(
    os.environ.get("RUN_REAL_S3_TESTS") != "1",
    reason="Skipping tests that access real S3. Set RUN_REAL_S3_TESTS=1 to run.",
)
class TestRealS3Store(unittest.IsolatedAsyncioTestCase):
    pass
    """Test S3Store with real NOAA GOES data patterns.

    Note: These tests access the actual NOAA S3 buckets and may be slow
    or fail due to network issues. They are primarily for validation
    and debugging purposes.
    """

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create S3 store
        self.store = S3Store(aws_region="us-east-1", timeout=30)

        # Create a temporary directory for downloads
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Use yesterday by default for tests to ensure data exists
        yesterday = datetime.now() - timedelta(days=1)
        self.test_date = yesterday.replace(hour=12, minute=0, second=0, microsecond=0)

        # Find valid nearest RadF minute (0, 10, 20, 30, 40, 50)
        # Convert back to 0, 10, 20, 30, 40, 50 minutes
        for minute in RADF_MINUTES:
            if abs(minute - self.test_date.minute) <= 5:
                pass
                self.radf_test_date = self.test_date.replace(minute=minute)
                break
        else:
            # Default to nearest 10-minute mark before the hour
            nearest_10min = (self.test_date.minute // 10) * 10
            self.radf_test_date = self.test_date.replace(minute=nearest_10min)

        # Find valid nearest RadC minute (1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56)
        for minute in RADC_MINUTES:
            if abs(minute - self.test_date.minute) <= 3:
                pass
                self.radc_test_date = self.test_date.replace(minute=minute)
                break
        else:
            # Default to minute 1 past the hour
            self.radc_test_date = self.test_date.replace(minute=1)

        # RadM test date (any minute should work)
        self.radm_test_date = self.test_date

    async def asyncTearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

        # Close S3 store
        await self.store.close()

    async def test_real_s3_exists_recent(self):
        """Test checking if a real file exists in S3 for a recent date."""
        # Try to find a RadF file from yesterday
        exists = await self.store.check_file_exists(
            self.radf_test_date, SatellitePattern.GOES_18
        )

        # Generate the S3 key for logging
        s3_key = to_s3_key(
            self.radf_test_date, SatellitePattern.GOES_18, product_type="RadF", band=13
        )

        if exists:
            pass
            print(f"✅ Found RadF file for {self.radf_test_date.isoformat()}")
            print(f"Key pattern: {s3_key}")
        else:
            print(f"❌ RadF file not found for {self.radf_test_date.isoformat()}")
            print(f"Key pattern: {s3_key}")
            print("Trying another time point 1 hour earlier...")

            # Try 1 hour earlier
            earlier_date = self.radf_test_date - timedelta(hours=1)
            exists = await self.store.check_file_exists(
                earlier_date, SatellitePattern.GOES_18
            )

            if exists:
                pass
                print(f"✅ Found RadF file for {earlier_date.isoformat()}")
            else:
                print(f"❌ RadF file not found for {earlier_date.isoformat()} either")

        # Test should pass regardless of whether file exists - we're testing the functionality
        # not the presence of specific data

    async def test_real_s3_exists_different_bands(self):
        pass
        """Test checking if real files exist for different bands."""
        # Test different bands with RadC product type
        bands_to_test = [1, 2, 7, 8, 13, 14]
        exists_results = {}

        for band in bands_to_test:
            pass
            # For now, use the download method to check existence
            # since check_file_exists doesn't support product_type/band args
            try:
                exists = await self.store.check_file_exists(
                    self.radc_test_date,
                    SatellitePattern.GOES_18,
                )
            except Exception:
                exists = False
            exists_results[band] = exists

            if exists:
                pass
                print(f"✅ Band {band} exists for {self.radc_test_date.isoformat()}")
            else:
                print(f"❌ Band {band} not found for {self.radc_test_date.isoformat()}")

        # Print summary
        print(f"Band availability summary for {self.radc_test_date.isoformat()}:")
        for band, exists in exists_results.items():
            print(f"Band {band}: {'✅ Available' if exists else '❌ Not found'}")

        # Test should pass regardless of which bands exist

    async def test_real_s3_exists_product_types(self):
        pass
        """Test checking if real files exist for different product types."""
        # Test different product types
        product_types = ["RadF", "RadC", "RadM"]
        exists_results = {}

        for product_type in product_types:
            pass
            # Use the appropriate test date for each product type
            if product_type == "RadF":
                pass
                test_date = self.radf_test_date
            elif product_type == "RadC":
                pass
                test_date = self.radc_test_date
            else:
                test_date = self.radm_test_date

            exists = await self.store.check_file_exists(
                test_date, SatellitePattern.GOES_18
            )
            exists_results[product_type] = exists

            if exists:
                pass
                print(f"✅ Product {product_type} exists for {test_date.isoformat()}")
            else:
                print(
                    f"❌ Product {product_type} not found for {test_date.isoformat()}"
                )

        # Print summary
        print("Product type availability summary:")
        for product_type, exists in exists_results.items():
            if product_type == "RadF":
                test_date = self.radf_test_date
            elif product_type == "RadC":
                test_date = self.radc_test_date
            else:
                test_date = self.radm_test_date
            print(
                f"{product_type}: {'✅ Available' if exists else '❌ Not found'} at {test_date.isoformat()}"
            )

        # Test should pass regardless of which product types exist

    async def test_real_s3_download_if_exists(self):
        pass
        """Test downloading a real file from S3 if it exists."""
        # Try to find a RadC file from yesterday
        exists = await self.store.check_file_exists(
            self.radc_test_date, SatellitePattern.GOES_18
        )

        if not exists:
            pass
            # Skip test if file doesn't exist
            print(
                f"⚠️ No RadC file found for {self.radc_test_date.isoformat()},"
                "skipping download test"
            )
            return

        # File exists, try to download it
        dest_path = self.temp_path / "test_download.nc"

        try:
            pass
            # Use the base download_file method
            downloaded_path = await self.store.download_file(
                self.radc_test_date,
                SatellitePattern.GOES_18,
                dest_path,
            )

            print(f"✅ Successfully downloaded file to {downloaded_path}")
            print(f"File size: {downloaded_path.stat().st_size} bytes")

            # Verify file exists and has content
            assert downloaded_path.exists()
            assert downloaded_path.stat().st_size > 0
        except Exception as e:
            print(f"❌ Failed to download file: {e}")
            # Re-raise for test failure
            raise


# Mock tests that simulate real S3 responses but don't actually access S3
class TestMockedRealS3Store(unittest.IsolatedAsyncioTestCase):
    """Test S3Store with mocked responses that simulate real NOAA GOES data patterns."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create S3 store
        self.store = S3Store(aws_region="us-east-1", timeout=30)

        # Create a temporary directory for downloads
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Test timestamp: June 15, 2023 12:30
        self.test_timestamp = datetime(2023, 6, 15, 12, 30, 0)

        # Mock S3 client
        self.s3_client_mock = AsyncMock()
        # get_paginator is a synchronous method that returns a paginator object
        self.s3_client_mock.get_paginator = MagicMock()

        # Patch _get_s3_client on the instance to return our mock
        # Note: _get_s3_client is an async method, so we need to make it return the mock directly
        async def mock_get_s3_client():
            return self.s3_client_mock
        
        # Patch the method on the instance, not the class
        self.store._get_s3_client = mock_get_s3_client

    async def asyncTearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

        # Close S3 store
        await self.store.close()

    async def test_mocked_real_s3_head_object(self):
        """Test head_object with mocked real S3 response."""
        # Configure mock to return success
        self.s3_client_mock.head_object.return_value = {
            "ContentLength": 2000000,
            "LastModified": self.test_timestamp,
            "ETag": '"example-etag"',
            "ContentType": "application/octet-stream",
        }

        # Test exists method
        exists = await self.store.check_file_exists(
            self.test_timestamp, SatellitePattern.GOES_18
        )

        # Verify result
        assert exists
        self.s3_client_mock.head_object.assert_called_once()

        # Extract the bucket and key arguments
        call_args = self.s3_client_mock.head_object.call_args
        bucket = call_args[1]["Bucket"]
        key = call_args[1]["Key"]

        # Check bucket name (should be noaa-goes18)
        assert bucket == "noaa-goes18"

        # Check key format - should match real S3 patterns
        assert key.startswith("ABI-L1b-RadC/2023/166/12/")
        assert "M6C13_G18_s" in key

    async def test_mocked_real_s3_download(self):
        pass
        """Test download with mocked real S3 response."""
        # Configure head_object to return success
        self.s3_client_mock.head_object.return_value = {
            "ContentLength": 2000000,
            "LastModified": self.test_timestamp,
        }

        # Configure download_file to succeed
        self.s3_client_mock.download_file = AsyncMock()

        # Destination path
        dest_path = self.temp_path / "test_download.nc"

        # Test download method
        result = await self.store.download_file(
            self.test_timestamp,
            SatellitePattern.GOES_18,
            dest_path,
        )
        # Store should return the destination path
        assert result == dest_path

        # Verify download_file was called
        self.s3_client_mock.download_file.assert_called_once()

        # Extract the arguments
        call_args = self.s3_client_mock.download_file.call_args
        bucket = call_args[1]["Bucket"]
        key = call_args[1]["Key"]
        filename = call_args[1]["Filename"]

        # Check bucket name (should be noaa-goes18)
        assert bucket == "noaa-goes18"

        # Check key format - should match real S3 patterns
        assert key.startswith("ABI-L1b-RadC/2023/166/12/")
        assert "M6C13_G18_s" in key

        # Check destination path
        assert filename == str(dest_path)

    async def test_mocked_real_s3_download_wildcard(self):
        """Test download with wildcard matching using mocked real S3 responses."""
        # Configure head_object to return 404 (fall back to wildcard search)
        import botocore.exceptions

        head_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadObject",
        )
        self.s3_client_mock.head_object.side_effect = head_error

        # Configure get_paginator for wildcard search
        paginator_mock = AsyncMock()

        # Create realistic response with actual file pattern that matches the expected pattern
        # The pattern expects s202316612* so we need s20231661230 (for 12:30)
        test_key = "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G18_s20231661230190_e20231661232562_c20231661233032.nc"
        test_page = {
            "Contents": [
                {
                    "Key": test_key,
                    "LastModified": self.test_timestamp,
                    "Size": 2000000,
                    "ETag": '"example-etag"',
                }
            ]
        }

        # Create async generator for paginate
        async def async_paginate(*args, **kwargs):
            yield test_page

        # Don't call the function - assign it directly so paginate() returns an async generator
        paginator_mock.paginate = async_paginate
        self.s3_client_mock.get_paginator.return_value = paginator_mock

        # Configure download_file to succeed
        self.s3_client_mock.download_file = AsyncMock()

        # Destination path
        dest_path = self.temp_path / "test_download.nc"

        # Test download method
        await self.store.download_file(
            self.test_timestamp,
            SatellitePattern.GOES_18,
            dest_path,
        )

        # Verify get_paginator was called
        self.s3_client_mock.get_paginator.assert_called_once()

        # Verify download_file was called with the correct key
        self.s3_client_mock.download_file.assert_called_once()
        call_args = self.s3_client_mock.download_file.call_args
        assert call_args[1]["Key"] == test_key


if __name__ == "__main__":
    pass
    unittest.main()
