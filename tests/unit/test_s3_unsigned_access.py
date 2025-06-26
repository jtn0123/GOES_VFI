"""
Unit tests for unsigned S3 access in the integrity_check module.
"""

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import botocore.exceptions
from botocore import UNSIGNED
from botocore.config import Config

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
)
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestUnsignedS3Access(unittest.TestCase):
    """Test cases for S3Store's unsigned S3 access functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Test timestamp and satellite
        self.test_timestamp = datetime(2023, 6, 15, 12, 30, 0)
        self.test_satellite = SatellitePattern.GOES_18

        # Create store under test with no AWS profile (should use unsigned access)
        self.s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)

        # Create a mock S3 client
        self.s3_client_mock = AsyncMock()
        self.s3_client_mock.__aenter__ = AsyncMock(return_value=self.s3_client_mock)
        self.s3_client_mock.__aexit__ = AsyncMock(return_value=None)

        # Mock boto3/aioboto3 session
        self.session_mock = MagicMock()
        self.session_mock.client = MagicMock(return_value=self.s3_client_mock)

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

        # Clean up any AsyncMock references
        if hasattr(self, "s3_client_mock"):
            if hasattr(self.s3_client_mock, "__aenter__"):
                self.s3_client_mock.__aenter__.reset_mock()
            if hasattr(self.s3_client_mock, "__aexit__"):
                self.s3_client_mock.__aexit__.reset_mock()

        # Reset store client reference
        if hasattr(self, "s3_store") and hasattr(self.s3_store, "_s3_client"):
            self.s3_store._s3_client = None

    @patch("aioboto3.Session")
    async def test_unsigned_s3_client_creation(self, mock_session_class):
        """Test that S3 client is created with unsigned access."""
        # Setup
        mock_session_class.return_value = self.session_mock

        # Create a config spy to verify UNSIGNED is used
        config_spy = MagicMock(wraps=Config)

        with patch("goesvfi.integrity_check.remote.s3_store.Config", config_spy):
            # Call method under test
            client = await self.s3_store._get_s3_client()

            # Verify the client was created with the session
            mock_session_class.assert_called_once()
            self.session_mock.client.assert_called_once()

            # Verify Config was called with UNSIGNED
            config_spy.assert_called_once()
            # Check the args passed to Config
            args, kwargs = config_spy.call_args
            self.assertIn("signature_version", kwargs)
            self.assertEqual(kwargs["signature_version"], UNSIGNED)

            # Verify the client was returned
            self.assertEqual(client, self.s3_client_mock)

    @patch("aioboto3.Session")
    async def test_unsigned_access_for_public_buckets(self, mock_session_class):
        """Test S3Store correctly accesses public NOAA buckets with unsigned access."""
        # Setup
        mock_session_class.return_value = self.session_mock

        # Use a realistic mock response for head_object
        mock_head_response = {"ContentLength": 12345, "LastModified": datetime.now()}
        self.s3_client_mock.head_object = AsyncMock(return_value=mock_head_response)

        # Patch Config to verify it's created with UNSIGNED
        with patch(
            "goesvfi.integrity_check.remote.s3_store.Config"
        ) as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config

            # Call exists method which should get the client
            exists = await self.s3_store.check_file_exists(
                self.test_timestamp, self.test_satellite
            )

            # Verify Config was created with UNSIGNED
            mock_config_class.assert_called_once()
            config_args = mock_config_class.call_args
            self.assertEqual(config_args[1]["signature_version"], UNSIGNED)

            # Verify client was created correctly
            self.session_mock.client.assert_called_once_with("s3", config=mock_config)

            # Verify head_object was called with the right bucket and key
            args = self.s3_client_mock.head_object.call_args
            self.assertIn("Bucket", args[1])
            self.assertIn("Key", args[1])

            # Verify the exists check succeeded
            self.assertTrue(exists)

    @patch("aioboto3.Session")
    async def test_error_handling_for_404(self, mock_session_class):
        """Test error handling for 404 Not Found responses."""
        # Setup
        mock_session_class.return_value = self.session_mock

        # Simulate a 404 error
        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        error = botocore.exceptions.ClientError(error_response, "HeadObject")
        self.s3_client_mock.head_object = AsyncMock(side_effect=error)

        # Call the exists method
        exists = await self.s3_store.check_file_exists(
            self.test_timestamp, self.test_satellite
        )

        # Verify exists returns False for 404
        self.assertFalse(exists)

    @patch("aioboto3.Session")
    async def test_error_handling_for_auth_errors(self, mock_session_class):
        """Test error handling for authentication errors."""
        # Setup
        mock_session_class.return_value = self.session_mock

        # Simulate an authentication error
        error_response = {
            "Error": {"Code": "InvalidAccessKeyId", "Message": "Invalid Access Key"}
        }
        error = botocore.exceptions.ClientError(error_response, "HeadObject")
        self.s3_client_mock.head_object = AsyncMock(side_effect=error)

        # Call the exists method - should raise AuthenticationError
        with self.assertRaises(AuthenticationError):
            await self.s3_store.check_file_exists(
                self.test_timestamp, self.test_satellite
            )

    @patch("aioboto3.Session")
    async def test_download_with_unsigned_access(self, mock_session_class):
        """Test downloading a file with unsigned access."""
        # Setup
        mock_session_class.return_value = self.session_mock

        # Mock successful head_object and download
        self.s3_client_mock.head_object = AsyncMock(
            return_value={"ContentLength": 12345}
        )
        self.s3_client_mock.download_file = AsyncMock()

        # Setup Config spy
        config_spy = MagicMock(wraps=Config)

        with patch("goesvfi.integrity_check.remote.s3_store.Config", config_spy):
            # Call download method
            dest_path = self.base_dir / "test_file.nc"
            result = await self.s3_store.download_file(
                self.test_timestamp, self.test_satellite, dest_path
            )

            # Verify Config was called with UNSIGNED
            config_spy.assert_called_once()
            args, kwargs = config_spy.call_args
            self.assertIn("signature_version", kwargs)
            self.assertEqual(kwargs["signature_version"], UNSIGNED)

            # Verify download_file was called
            self.s3_client_mock.download_file.assert_called_once()

            # Verify the result is the destination path
            self.assertEqual(result, dest_path)

    @patch("aioboto3.Session")
    async def test_noaa_bucket_access(self, mock_session_class):
        """Test S3Store correctly accesses NOAA buckets."""
        # Setup
        mock_session_class.return_value = self.session_mock
        self.s3_client_mock.head_object = AsyncMock(
            return_value={"ContentLength": 12345}
        )

        # Test both GOES-16 and GOES-18
        satellites = [SatellitePattern.GOES_16, SatellitePattern.GOES_18]
        expected_buckets = {
            SatellitePattern.GOES_16: "noaa-goes16",
            SatellitePattern.GOES_18: "noaa-goes18",
        }

        for satellite in satellites:
            # Reset mocks
            self.s3_client_mock.head_object.reset_mock()

            # Call exists method
            await self.s3_store.check_file_exists(self.test_timestamp, satellite)

            # Verify the correct bucket was accessed
            args = self.s3_client_mock.head_object.call_args
            self.assertEqual(args[1]["Bucket"], expected_buckets[satellite])


def async_test(coro):
    """Decorator for running async tests."""

    def wrapper(*args, **kwargs):
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run the test
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            # Clean up
            loop.close()

    return wrapper


# Apply async_test decorator to async test methods
for name in dir(TestUnsignedS3Access):
    if name.startswith("test_") and asyncio.iscoroutinefunction(
        getattr(TestUnsignedS3Access, name)
    ):
        setattr(
            TestUnsignedS3Access, name, async_test(getattr(TestUnsignedS3Access, name))
        )


if __name__ == "__main__":
    unittest.main()
