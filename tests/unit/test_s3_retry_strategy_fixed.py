"""Unit tests for S3 retry strategy and resilience.

These tests focus on the retry behavior, timeout handling, and resilience
of the S3Store implementation when faced with network issues.
"""

import unittest
import asyncio
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock, call

import botocore.exceptions
import aioboto3
from botocore import UNSIGNED

from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.integrity_check.remote.s3_store import S3Store, update_download_stats
from goesvfi.integrity_check.remote.base import (
    RemoteStoreError, ResourceNotFoundError, 
    AuthenticationError, ConnectionError
)


class TestS3RetryStrategy(unittest.IsolatedAsyncioTestCase):
    """Test cases for S3Store retry strategy and network resilience."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        # We'll handle our own mocking for specific tests
        # because we need more control over the retry behavior
        
        self.test_timestamp = datetime(2023, 6, 15, 12, 0, 0)
        self.test_satellite = SatellitePattern.GOES_18
        self.test_dest_path = Path("/tmp/test_download.nc")
    
    async def test_client_creation_retry(self):
        """Test retry logic for client creation."""
        # We need to mock at the aioboto3.Session level
        with patch('aioboto3.Session') as mock_session_class:
            # Setup a mock session
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Setup the client context to raise TimeoutError on first call
            mock_client_context = MagicMock()
            mock_client = AsyncMock()
            mock_client_context.__aenter__ = AsyncMock()
            
            # First call raises TimeoutError, second returns a client
            mock_client_context.__aenter__.side_effect = [
                asyncio.TimeoutError("Connection timed out"),
                mock_client
            ]
            
            # Configure session.client to return our mock context
            mock_session.client.return_value = mock_client_context
            
            # Create S3Store and call _get_s3_client
            store = S3Store(timeout=5)
            # This should retry and succeed on the second attempt
            client = await store._get_s3_client()
            
            # Verify the result and call counts
            self.assertEqual(client, mock_client)
            self.assertEqual(mock_client_context.__aenter__.call_count, 2)
            
            # Verify correct session setup
            mock_session_class.assert_called_once()
            mock_session.client.assert_called_once_with("s3", config=mock_session.client.call_args[1]['config'])
    
    async def test_client_creation_retry_fails_after_max_retries(self):
        """Test client creation fails after exceeding max retries."""
        # We need to mock at the aioboto3.Session level
        with patch('aioboto3.Session') as mock_session_class:
            # Setup a mock session
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Setup the client context to always raise TimeoutError
            mock_client_context = MagicMock()
            mock_client_context.__aenter__ = AsyncMock(
                side_effect=asyncio.TimeoutError("Connection timed out")
            )
            
            # Configure session.client to return our mock context
            mock_session.client.return_value = mock_client_context
            
            # Create S3Store with patch to sleep to avoid real delays
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                store = S3Store(timeout=5)
                
                # This should retry 3 times and then raise ConnectionError
                with self.assertRaises(ConnectionError) as cm:
                    await store._get_s3_client()
                
                # Verify error message
                self.assertIn("Connection to AWS S3 timed out", str(cm.exception))
                
                # Verify retry attempts
                self.assertEqual(mock_client_context.__aenter__.call_count, 3)
                
                # Verify sleep was called for retries
                self.assertEqual(mock_sleep.call_count, 2)  # Once per retry (before 3rd attempt)
    
    async def test_download_with_retry_on_transient_error(self):
        """Test download with retry on transient network errors."""
        # Create a mock S3 client
        mock_s3_client = AsyncMock()
        
        # First head_object succeeds
        mock_s3_client.head_object.return_value = {'ContentLength': 1000}
        
        # First download fails with connection error, second succeeds
        connection_error = botocore.exceptions.ClientError(
            {'Error': {'Code': 'ConnectionError', 'Message': 'Connection reset'}},
            'GetObject'
        )
        
        # Configure download_file to fail once then succeed
        download_calls = 0
        
        async def mock_download_file(*args, **kwargs):
            nonlocal download_calls
            download_calls += 1
            if download_calls == 1:
                raise connection_error
            # Second call succeeds
            return None
        
        mock_s3_client.download_file = mock_download_file
        
        # Create test destination path
        test_dest_path = Path(f"/tmp/test_{time.time()}.nc")
        
        # Mock Path.exists and Path.stat for success verification
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat', return_value=MagicMock(st_size=1024)), \
             patch('goesvfi.integrity_check.remote.s3_store.update_download_stats', new_callable=AsyncMock) as mock_stats, \
             patch('goesvfi.integrity_check.remote.s3_store.S3Store._get_s3_client', new_callable=AsyncMock) as mock_get_s3_client:
            
            # Configure _get_s3_client to return our mock
            mock_get_s3_client.return_value = mock_s3_client
            
            # Create store and run download
            store = S3Store(timeout=5)
            result = await store.download(
                self.test_timestamp, 
                self.test_satellite, 
                test_dest_path
            )
            
            # Verify stats were updated
            mock_stats.assert_called()
            
            # Verify we retried the download
            self.assertEqual(download_calls, 2)
            
            # Verify the result is the correct path
            self.assertEqual(result, test_dest_path)
    
    async def test_concurrent_download_limiter(self):
        """Test that concurrent downloads are limited by the semaphore."""
        # Need to mock ReconcileManager
        from goesvfi.integrity_check.reconcile_manager import ReconcileManager
        
        # Mock dependencies
        mock_cache_db = AsyncMock()
        mock_s3_store = AsyncMock()
        
        # Track active downloads for testing concurrency
        active_downloads = 0
        max_active = 0
        
        async def mock_download(*args, **kwargs):
            nonlocal active_downloads, max_active
            active_downloads += 1
            max_active = max(max_active, active_downloads)
            
            # Simulate work with a delay
            await asyncio.sleep(0.1)
            
            active_downloads -= 1
            return Path("/fake/path/file.nc")
        
        # Setup mock methods
        mock_s3_store.download = mock_download
        mock_s3_store.exists = AsyncMock(return_value=True)
        mock_s3_store.__aenter__ = AsyncMock(return_value=mock_s3_store)
        mock_s3_store.__aexit__ = AsyncMock(return_value=None)
        
        # Create manager with max_concurrency=2
        manager = ReconcileManager(
            cache_db=mock_cache_db,
            base_dir="/fake/base",
            s3_store=mock_s3_store,
            cdn_store=None,
            max_concurrency=2
        )
        
        # Create 5 timestamps
        timestamps = {
            datetime(2023, 1, 1, 12, i*10, 0) for i in range(5)
        }
        
        # Mock _is_recent to always use S3
        manager._is_recent = AsyncMock(return_value=False)
        
        # Run fetch_missing_files
        results = await manager.fetch_missing_files(
            missing_timestamps=timestamps,
            satellite=self.test_satellite
        )
        
        # Verify results
        self.assertEqual(len(results), 5)
        
        # Verify concurrency was limited
        self.assertLessEqual(max_active, 2)
    
    async def test_network_diagnostics_collection(self):
        """Test that network diagnostics are collected on repeated failures."""
        # Mock get_system_network_info
        with patch('goesvfi.integrity_check.remote.s3_store.get_system_network_info') as mock_info, \
             patch('goesvfi.integrity_check.remote.s3_store.DOWNLOAD_STATS') as mock_stats:
            
            # Setup mock stats
            mock_stats.get.return_value = 0  # Return 0 for any key for simplicity
            mock_stats.__getitem__.return_value = 4  # Return 4 for failed count
            
            # Call update_download_stats with a failure
            update_download_stats(
                success=False,
                error_type='network',
                error_message='Connection failed'
            )
            
            # Verify get_system_network_info was called
            # We're mocking the failed count to be at a 5-multiple 
            mock_info.assert_called_once()


if __name__ == '__main__':
    unittest.main()