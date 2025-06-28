"""Fixed integration tests for S3Store with proper async mock handling."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


# Mock tests that simulate real S3 responses but don't actually access S3
class TestMockedRealS3StoreFixed(unittest.IsolatedAsyncioTestCase):
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

        # Patch _get_s3_client to return our mock
        patcher = patch.object(S3Store, "_get_s3_client", return_value=self.s3_client_mock)
        self.mock_get_s3_client = patcher.start()

        async def _stop_patcher() -> None:
            patcher.stop()

        self.addAsyncCleanup(_stop_patcher)

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

        # Configure download_file to succeed (no return value needed)
        self.s3_client_mock.download_file = AsyncMock(return_value=None)

        # Destination path
        dest_path = self.temp_path / "test_download.nc"

        # Test download method
        await self.store.download_file(
            self.test_timestamp,
            SatellitePattern.GOES_18,
            dest_path,
        )

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
        paginator_mock = MagicMock()  # Use MagicMock, not AsyncMock

        # Create realistic response with actual file pattern
        # The timestamp part needs to match: s20231661230 (year=2023, doy=166, hour=12, minute=30)
        test_key = (
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G18_s20231661230000_e20231661232000_c20231661232030.nc"
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

        # Create proper async iterator for paginate
        class AsyncPaginateIterator:
            def __init__(self, pages) -> None:
                self.pages = pages
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index < len(self.pages):
                    page = self.pages[self.index]
                    self.index += 1
                    return page
                raise StopAsyncIteration

        # Setup paginator to return our async iterator
        paginator_mock.paginate.return_value = AsyncPaginateIterator([test_page])
        self.s3_client_mock.get_paginator.return_value = paginator_mock

        # Configure download_file to succeed
        self.s3_client_mock.download_file = AsyncMock(return_value=None)

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
