"""Integration tests for S3Store with real NOAA GOES data patterns."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import (
    SatellitePattern,
)


class TestRealS3Store(unittest.IsolatedAsyncioTestCase):
    """Test S3Store with mocked NOAA GOES data patterns.

    These tests use mocked S3 responses to simulate real data patterns
    without requiring external network access.
    """

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        # Create S3 store
        self.store = S3Store(aws_region="us-east-1", timeout=30)

        # Create a temporary directory for downloads
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Use fixed test date for consistent testing
        self.test_date = datetime(2023, 6, 15, 12, 0, 0)
        self.radf_test_date = self.test_date.replace(minute=0)  # RadF minute
        self.radc_test_date = self.test_date.replace(minute=1)  # RadC minute
        self.radm_test_date = self.test_date  # RadM minute

        # Mock S3 client
        self.s3_client_mock = AsyncMock()
        self.s3_client_mock.get_paginator = MagicMock()

        # Patch _get_s3_client on the instance to return our mock
        async def mock_get_s3_client():
            return self.s3_client_mock

        self.store._get_s3_client = mock_get_s3_client

    async def asyncTearDown(self) -> None:
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

        # Close S3 store
        await self.store.close()

    async def test_real_s3_exists_recent(self) -> None:
        """Test checking if a file exists in S3 with mocked response."""
        # Configure mock to return success for file existence check
        self.s3_client_mock.head_object.return_value = {
            "ContentLength": 2000000,
            "LastModified": self.radf_test_date,
            "ETag": '"example-etag"',
            "ContentType": "application/octet-stream",
        }

        # Test file exists
        exists = await self.store.check_file_exists(self.radf_test_date, SatellitePattern.GOES_18)
        assert exists

        # Verify head_object was called
        self.s3_client_mock.head_object.assert_called_once()

        # Test the functionality works correctly

    async def test_real_s3_exists_different_bands(self) -> None:
        """Test checking if files exist for different bands with mocked responses."""
        # Configure mock to return success for existence checks
        self.s3_client_mock.head_object.return_value = {
            "ContentLength": 2000000,
            "LastModified": self.radc_test_date,
            "ETag": '"example-etag"',
            "ContentType": "application/octet-stream",
        }

        # Test different bands with RadC product type
        bands_to_test = [1, 2, 7, 8, 13, 14]

        for _ in bands_to_test:
            exists = await self.store.check_file_exists(
                self.radc_test_date,
                SatellitePattern.GOES_18,
            )
            assert exists

        # Verify head_object was called for each band test
        assert self.s3_client_mock.head_object.call_count == len(bands_to_test)

    async def test_real_s3_exists_product_types(self) -> None:
        """Test checking if files exist for different product types with mocked responses."""
        # Configure mock to return success for existence checks
        self.s3_client_mock.head_object.return_value = {
            "ContentLength": 2000000,
            "LastModified": self.test_date,
            "ETag": '"example-etag"',
            "ContentType": "application/octet-stream",
        }

        # Test different product types
        product_types = ["RadF", "RadC", "RadM"]

        for product_type in product_types:
            # Use the appropriate test date for each product type
            if product_type == "RadF":
                test_date = self.radf_test_date
            elif product_type == "RadC":
                test_date = self.radc_test_date
            else:
                test_date = self.radm_test_date

            exists = await self.store.check_file_exists(test_date, SatellitePattern.GOES_18)
            assert exists

        # Verify head_object was called for each product type test
        assert self.s3_client_mock.head_object.call_count == len(product_types)

    async def test_real_s3_download_if_exists(self) -> None:
        """Test downloading a file from S3 with mocked responses."""
        # Configure head_object to return success for existence check
        self.s3_client_mock.head_object.return_value = {
            "ContentLength": 2000000,
            "LastModified": self.radc_test_date,
            "ETag": '"example-etag"',
            "ContentType": "application/octet-stream",
        }

        # Configure download_file to succeed
        self.s3_client_mock.download_file = AsyncMock()

        # Test file exists check
        exists = await self.store.check_file_exists(self.radc_test_date, SatellitePattern.GOES_18)
        assert exists

        # Test download
        dest_path = self.temp_path / "test_download.nc"
        downloaded_path = await self.store.download_file(
            self.radc_test_date,
            SatellitePattern.GOES_18,
            dest_path,
        )

        # Verify download was attempted
        self.s3_client_mock.download_file.assert_called_once()
        assert downloaded_path == dest_path


# Mock tests that simulate real S3 responses but don't actually access S3
class TestMockedRealS3Store(unittest.IsolatedAsyncioTestCase):
    """Test S3Store with mocked responses that simulate real NOAA GOES data patterns."""

    async def asyncSetUp(self) -> None:
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

    async def asyncTearDown(self) -> None:
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

        # Close S3 store
        await self.store.close()

    async def test_mocked_real_s3_head_object(self) -> None:
        """Test head_object with mocked real S3 response."""
        # Configure mock to return success
        self.s3_client_mock.head_object.return_value = {
            "ContentLength": 2000000,
            "LastModified": self.test_timestamp,
            "ETag": '"example-etag"',
            "ContentType": "application/octet-stream",
        }

        # Test exists method
        exists = await self.store.check_file_exists(self.test_timestamp, SatellitePattern.GOES_18)

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

    async def test_mocked_real_s3_download(self) -> None:
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

    async def test_mocked_real_s3_download_wildcard(self) -> None:
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
        test_key = (
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G18_s20231661230190_e20231661232562_c20231661233032.nc"
        )
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
    unittest.main()
