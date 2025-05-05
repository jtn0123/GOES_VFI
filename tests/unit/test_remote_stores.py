"""Unit tests for the integrity_check remote stores functionality."""

import unittest
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import aiohttp
import botocore.exceptions

from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store


class TestCDNStore(unittest.TestCase):
    """Test cases for the CDNStore class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        
        # Test timestamp
        self.test_timestamp = datetime(2023, 6, 15, 12, 30, 0)
        self.test_satellite = SatellitePattern.GOES_16
        
        # Create store under test
        self.cdn_store = CDNStore(resolution="1000m", timeout=5)
        
        # Make sure session property returns something in tests
        self.session_mock = AsyncMock(spec=aiohttp.ClientSession)
        
        # Configure response mock
        self.session_response_mock = AsyncMock()
        self.session_response_mock.status = 200
        self.session_response_mock.headers = {'Content-Length': '12345'}
        
        # Configure context manager for head method
        head_context_manager = AsyncMock()
        head_context_manager.__aenter__.return_value = self.session_response_mock
        head_context_manager.__aexit__.return_value = None
        self.session_mock.head.return_value = head_context_manager
        
        # Configure context manager for get method
        get_context_manager = AsyncMock()
        get_context_manager.__aenter__.return_value = self.session_response_mock
        get_context_manager.__aexit__.return_value = None
        self.session_mock.get.return_value = get_context_manager
        
        # Configure content for downloads
        self.content_mock = AsyncMock()
        self.session_response_mock.content = self.content_mock
        
        # Configure async iterator for content chunks
        async def mock_async_generator():
            yield b"test data"
            
        self.content_mock.iter_chunked.return_value = mock_async_generator()

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

    async def test_session_property(self):
        """Test the session property creates a new session if needed."""
        # Setup - create a fresh CDNStore to avoid setup conflicts
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        cdn_store._session = None  # Ensure session is None to start
        
        # Mock the ClientSession class
        with patch('aiohttp.ClientSession') as mock_client_session:
            # Create a simple mock object to return
            session_mock = MagicMock()
            mock_client_session.return_value = session_mock
            
            # Test - should create a new session
            session = await cdn_store.session
            
            # Verify
            self.assertIsNotNone(session)
            mock_client_session.assert_called_once()
            
            # Test reuse - session should be cached
            session2 = await cdn_store.session
            self.assertEqual(session, session2)
            
            # Verify ClientSession was only created once
            self.assertEqual(mock_client_session.call_count, 1)

    async def test_close(self):
        """Test closing the session."""
        # Setup - create a new CDNStore and mock session
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        session_mock = MagicMock()
        session_mock.closed = False
        session_mock.close = AsyncMock()
        
        # Set mock session
        cdn_store._session = session_mock
        
        # Test close
        await cdn_store.close()
        
        # Verify
        session_mock.close.assert_called_once()
        self.assertIsNone(cdn_store._session)

    async def test_exists(self):
        """Test checking if a file exists in the CDN."""
        # Create a fresh store for cleaner testing
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        
        # Create mocks
        with patch('goesvfi.integrity_check.remote.cdn_store.aiohttp.ClientSession') as mock_session_class:
            # Create response mock
            response_mock = MagicMock()
            response_mock.status = 200
            
            # Create context manager mock
            context_mock = MagicMock()
            context_mock.__aenter__ = AsyncMock(return_value=response_mock)
            context_mock.__aexit__ = AsyncMock(return_value=None)
            
            # Create session mock
            session_mock = MagicMock()
            session_mock.head = MagicMock(return_value=context_mock)
            mock_session_class.return_value = session_mock
            
            # Test success case (200)
            exists = await cdn_store.exists(self.test_timestamp, self.test_satellite)
            self.assertTrue(exists)
            
            # Test not found case (404)
            response_mock.status = 404
            exists = await cdn_store.exists(self.test_timestamp, self.test_satellite)
            self.assertFalse(exists)
            
            # Test error case
            session_mock.head.side_effect = aiohttp.ClientError("Test error")
            exists = await cdn_store.exists(self.test_timestamp, self.test_satellite)
            self.assertFalse(exists)

    async def test_download(self):
        """Test downloading a file from the CDN."""
        # Create a fresh store for cleaner testing
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        
        # Setup the session mock with proper context manager behavior
        session_mock = AsyncMock(spec=aiohttp.ClientSession)
        response_mock = AsyncMock()
        response_mock.status = 200
        response_mock.headers = {'Content-Length': '12345'}
        
        # Configure content for download
        content_mock = AsyncMock()
        response_mock.content = content_mock
        
        # Create async generator for content chunks
        async def mock_content_generator():
            yield b"test data"
        
        content_mock.iter_chunked = MagicMock(return_value=mock_content_generator())
        
        # Configure the context managers
        head_context = AsyncMock()
        head_context.__aenter__.return_value = response_mock
        session_mock.head.return_value = head_context
        
        get_context = AsyncMock()
        get_context.__aenter__.return_value = response_mock
        session_mock.get.return_value = get_context
        
        # Directly inject the session
        cdn_store._session = session_mock
        
        # Destination path
        dest_path = self.base_dir / "test_download.jpg"
        
        # Mock file open
        mock_open = unittest.mock.mock_open()
        
        # Test successful download
        with patch('builtins.open', mock_open):
            result = await cdn_store.download(self.test_timestamp, self.test_satellite, dest_path)
        
        # Verify
        self.assertEqual(result, dest_path)
        mock_open.assert_called_with(dest_path, 'wb')
        mock_open().write.assert_called_with(b"test data")
        
        # Test file not found
        response_mock.status = 404
        
        with patch('builtins.open', mock_open), self.assertRaises(FileNotFoundError):
            await cdn_store.download(self.test_timestamp, self.test_satellite, dest_path)
        
        # Test client error
        session_mock.head.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=MagicMock(), status=500
        )
        
        with patch('builtins.open', mock_open), self.assertRaises(IOError):
            await cdn_store.download(self.test_timestamp, self.test_satellite, dest_path)


class TestS3Store(unittest.TestCase):
    """Test cases for the S3Store class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        
        # Test timestamp
        self.test_timestamp = datetime(2023, 6, 15, 12, 30, 0)
        self.test_satellite = SatellitePattern.GOES_16
        
        # Create store under test
        self.s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
        
        # Mock S3 client
        self.s3_client_mock = AsyncMock()
        self.s3_client_mock.__aenter__.return_value = self.s3_client_mock
        self.s3_client_mock.__aexit__.return_value = None
        
        # Mock aioboto3 session
        self.session_mock = MagicMock()
        self.session_mock.client.return_value = self.s3_client_mock

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

    @patch('aioboto3.Session')
    async def test_get_s3_client(self, mock_session_class):
        """Test getting the S3 client."""
        # Setup
        mock_session_class.return_value = self.session_mock
        
        # Test
        client = await self.s3_store._get_s3_client()
        
        # Verify
        self.assertEqual(client, self.s3_client_mock)
        mock_session_class.assert_called_once_with(region_name='us-east-1')
        self.session_mock.client.assert_called_once_with('s3')
        
        # Test reuse
        client2 = await self.s3_store._get_s3_client()
        self.assertEqual(client, client2)
        self.assertEqual(mock_session_class.call_count, 1)

    @patch('aioboto3.Session')
    async def test_close(self, mock_session_class):
        """Test closing the S3 client."""
        # Setup
        mock_session_class.return_value = self.session_mock
        
        # Get client
        await self.s3_store._get_s3_client()
        
        # Test close
        await self.s3_store.close()
        
        # Verify
        self.s3_client_mock.__aexit__.assert_called_once()
        self.assertIsNone(self.s3_store._s3_client)

    @patch.object(S3Store, '_get_s3_client', new_callable=AsyncMock)
    async def test_get_bucket_and_key(self, mock_get_client):
        """Test getting the bucket and key for a timestamp."""
        # No need to use client for this test
        mock_get_client.return_value = None
        
        # Test with GOES-16
        bucket, key = self.s3_store._get_bucket_and_key(
            self.test_timestamp, SatellitePattern.GOES_16
        )
        expected_bucket = TimeIndex.S3_BUCKETS[SatellitePattern.GOES_16]
        expected_key = TimeIndex.to_s3_key(self.test_timestamp, SatellitePattern.GOES_16)
        
        self.assertEqual(bucket, expected_bucket)
        self.assertEqual(key, expected_key)
        
        # Test with GOES-18
        bucket, key = self.s3_store._get_bucket_and_key(
            self.test_timestamp, SatellitePattern.GOES_18
        )
        expected_bucket = TimeIndex.S3_BUCKETS[SatellitePattern.GOES_18]
        expected_key = TimeIndex.to_s3_key(self.test_timestamp, SatellitePattern.GOES_18)
        
        self.assertEqual(bucket, expected_bucket)
        self.assertEqual(key, expected_key)

    @patch.object(S3Store, '_get_s3_client', new_callable=AsyncMock)
    async def test_exists(self, mock_get_client):
        """Test checking if a file exists in S3."""
        # Setup
        mock_get_client.return_value = self.s3_client_mock
        
        # Test success case
        self.s3_client_mock.head_object.return_value = {"ContentLength": 12345}
        exists = await self.s3_store.exists(self.test_timestamp, self.test_satellite)
        
        # Verify
        self.assertTrue(exists)
        
        # Test not found case
        error_response = {'Error': {'Code': '404'}}
        self.s3_client_mock.head_object.side_effect = botocore.exceptions.ClientError(
            error_response, 'HeadObject'
        )
        exists = await self.s3_store.exists(self.test_timestamp, self.test_satellite)
        
        # Verify
        self.assertFalse(exists)
        
        # Test other error case
        error_response = {'Error': {'Code': '500'}}
        self.s3_client_mock.head_object.side_effect = botocore.exceptions.ClientError(
            error_response, 'HeadObject'
        )
        exists = await self.s3_store.exists(self.test_timestamp, self.test_satellite)
        
        # Verify
        self.assertFalse(exists)

    @patch.object(S3Store, '_get_s3_client', new_callable=AsyncMock)
    async def test_download(self, mock_get_client):
        """Test downloading a file from S3."""
        # Setup
        mock_get_client.return_value = self.s3_client_mock
        
        # Destination path
        dest_path = self.base_dir / "test_download.nc"
        
        # Test successful download
        await self.s3_store.download(self.test_timestamp, self.test_satellite, dest_path)
        
        # Verify
        bucket, key = self.s3_store._get_bucket_and_key(
            self.test_timestamp, self.test_satellite
        )
        self.s3_client_mock.download_file.assert_called_once_with(
            Bucket=bucket, Key=key, Filename=str(dest_path)
        )
        
        # Test file not found
        error_response = {'Error': {'Code': '404'}}
        self.s3_client_mock.head_object.side_effect = botocore.exceptions.ClientError(
            error_response, 'HeadObject'
        )
        
        with self.assertRaises(FileNotFoundError):
            await self.s3_store.download(self.test_timestamp, self.test_satellite, dest_path)
        
        # Test other error
        error_response = {'Error': {'Code': '500'}}
        self.s3_client_mock.head_object.side_effect = botocore.exceptions.ClientError(
            error_response, 'HeadObject'
        )
        
        with self.assertRaises(IOError):
            await self.s3_store.download(self.test_timestamp, self.test_satellite, dest_path)


def async_test(coro):
    """Decorator for running async tests."""
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


# Apply async_test decorator to async test methods
for cls in [TestCDNStore, TestS3Store]:
    for method_name in dir(cls):
        if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(cls, method_name)):
            setattr(cls, method_name, async_test(getattr(cls, method_name)))


if __name__ == '__main__':
    unittest.main()