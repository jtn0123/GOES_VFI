"""Unit tests for S3 error handling in the S3Store class."""

# flake8: noqa: PT009,PT027

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import botocore.exceptions

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    ConnectionError,
    RemoteStoreError,
)
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3ErrorHandling(unittest.IsolatedAsyncioTestCase):
    """Test cases for S3Store error handling."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.store = S3Store()
        self.test_timestamp = datetime(2023, 6, 15, 12, 0, 0)
        self.test_satellite = SatellitePattern.GOES_18

        # Create temporary directory for tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dest_path = Path(self.temp_dir.name) / "test_download.nc"

        # Mock S3 client
        self.mock_s3_client = AsyncMock()
        # get_paginator is a synchronous method that returns a paginator object
        self.mock_s3_client.get_paginator = MagicMock()

        # Patch the _get_s3_client method to return our mock
        patcher = patch.object(S3Store, "_get_s3_client", return_value=self.mock_s3_client)
        self.mock_get_s3_client = patcher.start()

        async def async_stop() -> None:
            patcher.stop()
            self.temp_dir.cleanup()

        self.addAsyncCleanup(async_stop)

    async def test_head_object_not_found(self) -> None:
        """Test handling of 404 Not Found error during head_object call."""
        # Prepare a 404 ClientError response
        client_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadObject",
        )
        self.mock_s3_client.head_object.side_effect = client_error

        # Also prepare a mock for wildcard search (list_objects_v2)
        paginator_mock = MagicMock()  # Use MagicMock, not AsyncMock

        # Create an async generator that returns no pages
        async def empty_paginate(*args, **kwargs) -> None:
            # Return empty async iterator
            return

        # Create an actual async generator
        async def async_empty_gen() -> None:
            return

        paginator_mock.paginate.return_value = async_empty_gen()
        self.mock_s3_client.get_paginator.return_value = paginator_mock

        # Test the exists method
        result = await self.store.check_file_exists(self.test_timestamp, self.test_satellite)
        self.assertFalse(result)

        # Verify the correct calls were made
        self.mock_s3_client.head_object.assert_called_once()

    async def test_download_access_denied(self) -> None:
        """Test handling of Access Denied error during download."""
        # Prepare a 403 ClientError response
        client_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "403", "Message": "Access Denied"}},
            operation_name="HeadObject",
        )
        self.mock_s3_client.head_object.side_effect = client_error

        # Test the download method - should raise AuthenticationError
        with self.assertRaises(AuthenticationError) as context:
            await self.store.download_file(self.test_timestamp, self.test_satellite, self.test_dest_path)

        # Verify the error message contains helpful information
        error_msg = str(context.exception)
        self.assertIn("Access denied", error_msg)
        self.assertIn(self.test_satellite.name, error_msg)

    async def test_download_timeout_error(self) -> None:
        """Test handling of timeout error during download."""
        # First let head_object succeed
        self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

        # Then make download_file fail with timeout
        self.mock_s3_client.download_file.side_effect = TimeoutError("Connection timed out")

        # Test the download method - should raise ConnectionError
        with self.assertRaises(ConnectionError) as context:
            await self.store.download_file(self.test_timestamp, self.test_satellite, self.test_dest_path)

        # Verify the error message contains helpful information
        error_msg = str(context.exception)
        self.assertIn("Timeout", error_msg)
        self.assertIn(self.test_satellite.name, error_msg)

    async def test_download_wildcard_not_found(self) -> None:
        """Test handling of not found errors during wildcard matching."""
        # Set up head_object to return 404
        client_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadObject",
        )
        self.mock_s3_client.head_object.side_effect = client_error

        # Set up paginator to return empty results (no files found)
        paginator_mock = MagicMock()  # Regular mock for paginator object
        empty_pages: list[dict] = []

        # Create async generator for paginate method
        async def mock_paginate(*args, **kwargs):
            for page in empty_pages:
                yield page

        paginator_mock.paginate.return_value = mock_paginate()
        self.mock_s3_client.get_paginator.return_value = paginator_mock

        # Test the download method - should raise RemoteStoreError
        # (The ResourceNotFoundError from wildcard search is caught and re-raised as RemoteStoreError)
        with self.assertRaises(RemoteStoreError) as context:
            await self.store.download_file(self.test_timestamp, self.test_satellite, self.test_dest_path)

        # Verify the error message contains helpful information
        error_msg = str(context.exception)
        self.assertIn("No files found for", error_msg)
        self.assertIn(self.test_satellite.name, error_msg)

        # Make sure technical details contain search parameters
        technical_details = getattr(context.exception, "technical_details", "")
        self.assertIn("Search parameters", technical_details)

    async def test_download_permission_error(self) -> None:
        """Test handling of permission error during file writing."""
        # Make head_object succeed
        self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

        # Make download_file raise PermissionError
        self.mock_s3_client.download_file.side_effect = PermissionError("Permission denied")

        # Test the download method - should raise AuthenticationError
        with self.assertRaises(AuthenticationError) as context:
            await self.store.download_file(self.test_timestamp, self.test_satellite, self.test_dest_path)

        # Verify the error message contains helpful information
        error_msg = str(context.exception)
        self.assertIn("Permission", error_msg)

        # Verify technical details include the path
        technical_details = getattr(context.exception, "technical_details", "")
        self.assertIn(str(self.test_dest_path), technical_details)

    async def test_wildcard_match_download_error(self) -> None:
        """Test handling of download error after successful wildcard match."""
        # Set up head_object to return 404 (falling back to wildcard)
        head_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadObject",
        )
        self.mock_s3_client.head_object.side_effect = head_error

        # Set up paginator to return one matching object
        paginator_mock = MagicMock()  # Regular mock for paginator object

        # Create a test page with one match
        # The key needs to have the satellite code and timestamp part that match
        test_key = (
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G18_s20231661200000_e20231661202000_c20231661202030.nc"
        )
        test_page = {"Contents": [{"Key": test_key}]}

        # Create async generator for paginate method
        async def mock_paginate(*args, **kwargs):
            yield test_page

        paginator_mock.paginate.return_value = mock_paginate()
        self.mock_s3_client.get_paginator.return_value = paginator_mock

        # Set up download_file to fail with a client error
        download_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "InternalError", "Message": "Server Error"}},
            operation_name="GetObject",
        )
        self.mock_s3_client.download_file.side_effect = download_error

        # Test the download method - should raise RemoteStoreError
        with self.assertRaises(RemoteStoreError) as context:
            await self.store.download_file(self.test_timestamp, self.test_satellite, self.test_dest_path)

        # Verify the error message contains helpful information
        error_msg = str(context.exception)
        self.assertIn("Error accessing", error_msg)
        self.assertIn(self.test_satellite.name, error_msg)


# Run the tests if this file is executed directly
if __name__ == "__main__":
    unittest.main()
