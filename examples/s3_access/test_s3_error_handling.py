"""Unit tests for S3 error handling in the S3Store class."""

import asyncio
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import botocore.exceptions

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    ConnectionError,
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3ErrorHandling(unittest.IsolatedAsyncioTestCase):
    pass


"""Test cases for S3Store error handling."""


async def asyncSetUp(self):
    """Set up test fixtures."""


self.store = S3Store()
self.test_timestamp = datetime(2023, 6, 15, 12, 0, 0)
self.test_satellite = SatellitePattern.GOES_18
self.test_dest_path = Path("/tmp / test_download.nc")

# Mock S3 client
self.mock_s3_client = AsyncMock()

# Patch the _get_s3_client method to return our mock
patcher = patch.object(S3Store, "_get_s3_client", return_value=self.mock_s3_client)
self.mock_get_s3_client = patcher.start()
self.addAsyncCleanup(patcher.stop)


async def test_head_object_not_found(self):
    """Test handling of 404 Not Found error during head_object call."""


# Prepare a 404 ClientError response
client_error = botocore.exceptions.ClientError(
    error_response={"Error": {"Code": "404", "Message": "Not Found"}},
    operation_name="HeadObject",
)
self.mock_s3_client.head_object.side_effect = client_error

# Also prepare a mock for wildcard search (list_objects_v2)
paginator_mock = AsyncMock()
paginator_mock.paginate.return_value = []  # No objects found
self.mock_s3_client.get_paginator.return_value = paginator_mock

# Test the exists method
result = await self.store.exists(self.test_timestamp, self.test_satellite)
self.assertFalse(result)

# Verify the correct calls were made
self.mock_s3_client.head_object.assert_called_once()


async def test_download_access_denied(self):
    pass


"""Test handling of Access Denied error during download."""
# Prepare a 403 ClientError response
client_error = botocore.exceptions.ClientError(
    error_response={"Error": {"Code": "403", "Message": "Access Denied"}},
    operation_name="HeadObject",
)
self.mock_s3_client.head_object.side_effect = client_error

# Test the download method - should raise AuthenticationError
with self.assertRaises(AuthenticationError) as context:
    await self.store.download(
        self.test_timestamp, self.test_satellite, self.test_dest_path
    )

# Verify the error message contains helpful information
error_msg = str(context.exception)
self.assertIn("Access denied", error_msg)
self.assertIn(self.test_satellite.name, error_msg)


async def test_download_timeout_error(self):
    pass


pass
"""Test handling of timeout error during download."""
# First let head_object succeed
self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

# Then make download_file fail with timeout
self.mock_s3_client.download_file.side_effect = asyncio.TimeoutError(
    "Connection timed out"
)

# Test the download method - should raise ConnectionError
with self.assertRaises(ConnectionError) as context:
    await self.store.download(
        self.test_timestamp, self.test_satellite, self.test_dest_path
    )

# Verify the error message contains helpful information
error_msg = str(context.exception)
self.assertIn("Timeout", error_msg)
self.assertIn(self.test_satellite.name, error_msg)


async def test_download_wildcard_not_found(self):
    pass


pass
"""Test handling of not found errors during wildcard matching."""
# Set up head_object to return 404
client_error = botocore.exceptions.ClientError(
    error_response={"Error": {"Code": "404", "Message": "Not Found"}},
    operation_name="HeadObject",
)
self.mock_s3_client.head_object.side_effect = client_error

# Set up paginator to return empty results (no files found)
paginator_mock = MagicMock()
empty_pages = []


# Make sure the AsyncMock can be iterated
async def mock_paginate(*args, **kwargs):
    for page in empty_pages:
        pass
    yield page


paginator_mock.paginate = mock_paginate
self.mock_s3_client.get_paginator.return_value = paginator_mock

# Test the download method - should raise ResourceNotFoundError
with self.assertRaises(ResourceNotFoundError) as context:
    await self.store.download(
        self.test_timestamp, self.test_satellite, self.test_dest_path
    )

# Verify the error message contains helpful information
error_msg = str(context.exception)
self.assertIn("No files found", error_msg)
self.assertIn(self.test_satellite.name, error_msg)

# Make sure technical details contain search parameters
technical_details = getattr(context.exception, "technical_details", "")
self.assertIn("Search parameters", technical_details)


async def test_download_permission_error(self):
    pass


pass
"""Test handling of permission error during file writing."""
# Make head_object succeed
self.mock_s3_client.head_object.return_value = {"ContentLength": 1000}

# Make download_file raise PermissionError
self.mock_s3_client.download_file.side_effect = PermissionError("Permission denied")

# Test the download method - should raise AuthenticationError
with self.assertRaises(AuthenticationError) as context:
    await self.store.download(
        self.test_timestamp, self.test_satellite, self.test_dest_path
    )

# Verify the error message contains helpful information
error_msg = str(context.exception)
self.assertIn("Permission", error_msg)

# Verify technical details include the path
technical_details = getattr(context.exception, "technical_details", "")
self.assertIn(str(self.test_dest_path), technical_details)


async def test_wildcard_match_download_error(self):
    pass


pass
"""Test handling of download error after successful wildcard match."""
# Set up head_object to return 404 (falling back to wildcard)
head_error = botocore.exceptions.ClientError(
    error_response={"Error": {"Code": "404", "Message": "Not Found"}},
    operation_name="HeadObject",
)
self.mock_s3_client.head_object.side_effect = head_error

# Set up paginator to return one matching object
paginator_mock = MagicMock()

# Create a test page with one match
test_page = {"Contents": [{"Key": "test_match_key.nc"}]}


# Make sure the AsyncMock can be iterated and return our test page
async def mock_paginate(*args, **kwargs):
    yield test_page


paginator_mock.paginate = mock_paginate
self.mock_s3_client.get_paginator.return_value = paginator_mock

# Set up download_file to fail with a client error
download_error = botocore.exceptions.ClientError(
    error_response={"Error": {"Code": "InternalError", "Message": "Server Error"}},
    operation_name="GetObject",
)
self.mock_s3_client.download_file.side_effect = download_error

# Test the download method - should raise RemoteStoreError
with self.assertRaises(RemoteStoreError) as context:
    await self.store.download(
        self.test_timestamp, self.test_satellite, self.test_dest_path
    )

# Verify the error message contains helpful information
error_msg = str(context.exception)
self.assertIn("Error downloading", error_msg)
self.assertIn(self.test_satellite.name, error_msg)


# Run the tests if this file is executed directly
if __name__ == "__main__":
    pass
    pass
unittest.main()
