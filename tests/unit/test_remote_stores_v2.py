"""Optimized remote stores tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common CDN and S3 store configurations
- Parameterized test scenarios for comprehensive store functionality testing
- Enhanced mock patterns to avoid real network calls while maintaining realistic behavior
- Mock-based async testing to avoid real I/O operations
- Comprehensive edge case and boundary condition testing
"""

from datetime import datetime
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
import pytest

import aiohttp
import botocore.exceptions

from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex


class TestRemoteStoresV2:
    """Optimized test class for remote stores functionality."""

    @pytest.fixture(scope="class")
    def store_configurations(self):
        """Define various store configuration test cases."""
        return {
            "cdn_standard": {
                "store_type": "cdn",
                "resolution": "1000m",
                "timeout": 5,
                "description": "Standard CDN store configuration",
            },
            "cdn_high_res": {
                "store_type": "cdn",
                "resolution": "500m",
                "timeout": 10,
                "description": "High resolution CDN store configuration",
            },
            "s3_standard": {
                "store_type": "s3",
                "aws_profile": None,
                "aws_region": "us-east-1",
                "timeout": 30,
                "description": "Standard S3 store configuration",
            },
            "s3_west": {
                "store_type": "s3",
                "aws_profile": None,
                "aws_region": "us-west-2",
                "timeout": 60,
                "description": "West coast S3 store configuration",
            },
        }

    @pytest.fixture(scope="class")
    def satellite_test_cases(self):
        """Define satellite test case configurations."""
        return {
            "goes_16": {
                "satellite": SatellitePattern.GOES_16,
                "expected_bucket": "noaa-goes16",
                "satellite_code": "G16",
                "position": "East",
            },
            "goes_18": {
                "satellite": SatellitePattern.GOES_18,
                "expected_bucket": "noaa-goes18",
                "satellite_code": "G18",
                "position": "West",
            },
        }

    @pytest.fixture(scope="class")
    def timestamp_scenarios(self):
        """Define various timestamp scenario test cases."""
        return {
            "standard_times": [
                datetime(2023, 6, 15, 12, 0, 0),
                datetime(2023, 6, 15, 18, 30, 0),
                datetime(2023, 6, 15, 6, 45, 0),
            ],
            "edge_case_times": [
                datetime(2023, 1, 1, 0, 0, 0),      # New Year
                datetime(2023, 12, 31, 23, 59, 0),  # End of year
                datetime(2024, 2, 29, 12, 0, 0),    # Leap day
            ],
            "various_doy_times": [
                datetime(2023, 3, 21, 12, 0, 0),    # Spring equinox
                datetime(2023, 6, 21, 12, 0, 0),    # Summer solstice
                datetime(2023, 9, 23, 12, 0, 0),    # Fall equinox
                datetime(2023, 12, 21, 12, 0, 0),   # Winter solstice
            ],
        }

    @pytest.fixture(scope="class")
    def response_scenarios(self):
        """Define various HTTP response scenario test cases."""
        return {
            "success_responses": [
                {"status": 200, "headers": {"Content-Length": "12345"}},
                {"status": 200, "headers": {"Content-Length": "54321", "Content-Type": "application/netcdf"}},
            ],
            "error_responses": [
                {"status": 404, "exception": aiohttp.ClientResponseError},
                {"status": 403, "exception": aiohttp.ClientResponseError},
                {"status": 500, "exception": aiohttp.ClientResponseError},
                {"status": 503, "exception": aiohttp.ClientResponseError},
            ],
            "client_errors": [
                {"exception": aiohttp.ClientConnectionError, "message": "Connection failed"},
                {"exception": aiohttp.ClientTimeout, "message": "Request timeout"},
                {"exception": aiohttp.ClientError, "message": "Generic client error"},
            ],
        }

    @pytest.fixture(scope="class")
    def s3_error_scenarios(self):
        """Define various S3 error scenario test cases."""
        return {
            "not_found_errors": [
                {"Code": "404", "Message": "Not Found"},
                {"Code": "NoSuchKey", "Message": "The specified key does not exist"},
                {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist"},
            ],
            "authentication_errors": [
                {"Code": "InvalidAccessKeyId", "Message": "The AWS Access Key Id you provided does not exist"},
                {"Code": "SignatureDoesNotMatch", "Message": "Request signature does not match"},
                {"Code": "TokenRefreshRequired", "Message": "The provided token must be refreshed"},
                {"Code": "AccessDenied", "Message": "Access Denied"},
            ],
            "server_errors": [
                {"Code": "500", "Message": "Internal Server Error"},
                {"Code": "503", "Message": "Service Unavailable"},
                {"Code": "RequestTimeout", "Message": "Request has expired"},
            ],
        }

    @pytest.fixture
    def temp_directory(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_cdn_session(self):
        """Create a comprehensive mock for aiohttp ClientSession."""
        session_mock = MagicMock()
        session_mock.closed = False
        
        # Default successful response
        response_mock = MagicMock()
        response_mock.status = 200
        response_mock.headers = {"Content-Length": "12345"}
        
        # Mock content for downloads
        content_mock = MagicMock()
        response_mock.content = content_mock
        
        async def mock_content_generator():
            yield b"test data chunk 1"
            yield b"test data chunk 2"
        
        content_mock.iter_chunked.return_value = mock_content_generator()
        
        # Configure context managers
        head_context = MagicMock()
        head_context.__aenter__ = AsyncMock(return_value=response_mock)
        head_context.__aexit__ = AsyncMock(return_value=None)
        session_mock.head = MagicMock(return_value=head_context)
        
        get_context = MagicMock()
        get_context.__aenter__ = AsyncMock(return_value=response_mock)
        get_context.__aexit__ = AsyncMock(return_value=None)
        session_mock.get = MagicMock(return_value=get_context)
        
        return session_mock, response_mock

    @pytest.fixture
    def mock_s3_client(self):
        """Create a comprehensive mock for S3 client."""
        s3_client_mock = MagicMock()
        s3_client_mock.__aenter__ = AsyncMock(return_value=s3_client_mock)
        s3_client_mock.__aexit__ = AsyncMock(return_value=None)
        s3_client_mock.head_object = AsyncMock()
        s3_client_mock.download_file = AsyncMock()
        
        session_mock = MagicMock()
        session_mock.client.return_value = s3_client_mock
        
        return s3_client_mock, session_mock

    @pytest.mark.parametrize("config_name", ["cdn_standard", "cdn_high_res"])
    def test_cdn_store_initialization(self, store_configurations, config_name):
        """Test CDN store initialization with different configurations."""
        config = store_configurations[config_name]
        
        # Create CDN store
        cdn_store = CDNStore(
            resolution=config["resolution"],
            timeout=config["timeout"]
        )
        
        # Verify initialization
        assert cdn_store.resolution == config["resolution"]
        assert cdn_store.timeout == config["timeout"]
        assert cdn_store._session is None

    @pytest.mark.parametrize("config_name", ["s3_standard", "s3_west"])
    def test_s3_store_initialization(self, store_configurations, config_name):
        """Test S3 store initialization with different configurations."""
        config = store_configurations[config_name]
        
        # Mock network diagnostics to avoid real network calls
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
        ):
            s3_store = S3Store(
                aws_profile=config["aws_profile"],
                aws_region=config["aws_region"],
                timeout=config["timeout"]
            )
        
        # Verify initialization
        assert s3_store.aws_region == config["aws_region"]
        assert s3_store.timeout == config["timeout"]
        assert s3_store._s3_client is None

    @pytest.mark.asyncio
    async def test_cdn_store_session_creation_and_reuse(self):
        """Test CDN store session creation and reuse patterns."""
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            session_mock = MagicMock()
            session_mock.closed = False
            mock_session_class.return_value = session_mock
            
            # First access should create session
            session1 = await cdn_store.session
            assert session1 is not None
            mock_session_class.assert_called_once()
            
            # Second access should reuse session
            session2 = await cdn_store.session
            assert session1 == session2
            assert mock_session_class.call_count == 1

    @pytest.mark.asyncio
    async def test_cdn_store_session_recreation_after_close(self):
        """Test CDN store session recreation after closing."""
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            session_mock = AsyncMock()
            session_mock.closed = False
            mock_session_class.return_value = session_mock
            
            # Create session
            session1 = await cdn_store.session
            assert session1 is not None
            
            # Close session
            await cdn_store.close()
            session_mock.close.assert_awaited_once()
            assert cdn_store._session is None
            
            # Create new session
            session2 = await cdn_store.session
            assert session2 is not None
            assert mock_session_class.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize("satellite_name", ["goes_16", "goes_18"])
    @pytest.mark.parametrize("timestamp_category", ["standard_times", "edge_case_times"])
    async def test_cdn_store_file_exists_comprehensive(self, satellite_test_cases, timestamp_scenarios,
                                                     mock_cdn_session, satellite_name, timestamp_category):
        """Test CDN store file existence checking with various scenarios."""
        session_mock, response_mock = mock_cdn_session
        satellite_config = satellite_test_cases[satellite_name]
        timestamps = timestamp_scenarios[timestamp_category]
        
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        
        with (
            patch("aiohttp.ClientSession", return_value=session_mock),
            patch("goesvfi.integrity_check.time_index.TimeIndex.to_cdn_url", return_value="https://example.com/test.jpg"),
        ):
            for timestamp in timestamps:
                # Test successful check
                response_mock.status = 200
                exists = await cdn_store.check_file_exists(timestamp, satellite_config["satellite"])
                assert exists
                
                # Test not found
                response_mock.status = 404
                exists = await cdn_store.check_file_exists(timestamp, satellite_config["satellite"])
                assert not exists

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error_scenario", ["client_errors"])
    async def test_cdn_store_file_exists_error_handling(self, response_scenarios, mock_cdn_session, error_scenario):
        """Test CDN store error handling during file existence checks."""
        session_mock, response_mock = mock_cdn_session
        error_configs = response_scenarios[error_scenario]
        
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        timestamp = datetime(2023, 6, 15, 12, 0, 0)
        satellite = SatellitePattern.GOES_16
        
        with (
            patch("aiohttp.ClientSession", return_value=session_mock),
            patch("goesvfi.integrity_check.time_index.TimeIndex.to_cdn_url", return_value="https://example.com/test.jpg"),
        ):
            for error_config in error_configs:
                # Configure error
                error_context = MagicMock()
                error_context.__aenter__ = AsyncMock(side_effect=error_config["exception"](error_config["message"]))
                session_mock.head = MagicMock(return_value=error_context)
                
                # Should return False on error
                exists = await cdn_store.check_file_exists(timestamp, satellite)
                assert not exists

    @pytest.mark.asyncio
    @pytest.mark.parametrize("satellite_name", ["goes_16", "goes_18"])
    async def test_cdn_store_download_success(self, satellite_test_cases, mock_cdn_session, temp_directory, satellite_name):
        """Test successful CDN store downloads."""
        session_mock, response_mock = mock_cdn_session
        satellite_config = satellite_test_cases[satellite_name]
        
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        timestamp = datetime(2023, 6, 15, 12, 0, 0)
        dest_path = temp_directory / f"test_download_{satellite_name}.jpg"
        
        # Configure successful response
        response_mock.status = 200
        response_mock.headers = {"Content-Length": "12345"}
        
        with (
            patch("aiohttp.ClientSession", return_value=session_mock),
            patch("goesvfi.integrity_check.time_index.TimeIndex.to_cdn_url", return_value="https://example.com/test.jpg"),
            patch("builtins.open", mock_open()) as open_mock,
        ):
            # Inject session directly to avoid creation logic
            cdn_store._session = session_mock
            
            result = await cdn_store.download_file(timestamp, satellite_config["satellite"], dest_path)
            
            # Verify
            assert result == dest_path
            open_mock.assert_called_with(dest_path, "wb")
            # Verify content was written
            write_calls = open_mock().write.call_args_list
            assert len(write_calls) == 2  # Two chunks
            assert write_calls[0][0][0] == b"test data chunk 1"
            assert write_calls[1][0][0] == b"test data chunk 2"

    @pytest.mark.asyncio
    async def test_cdn_store_download_not_found(self, mock_cdn_session, temp_directory):
        """Test CDN store download when file not found."""
        session_mock, response_mock = mock_cdn_session
        
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        timestamp = datetime(2023, 6, 15, 12, 0, 0)
        satellite = SatellitePattern.GOES_16
        dest_path = temp_directory / "test_download.jpg"
        
        # Configure 404 error
        error = aiohttp.ClientResponseError(
            request_info=MagicMock(), 
            history=MagicMock(), 
            status=404
        )
        
        head_context = MagicMock()
        head_context.__aenter__ = AsyncMock(side_effect=error)
        session_mock.head = MagicMock(return_value=head_context)
        
        with (
            patch("aiohttp.ClientSession", return_value=session_mock),
            patch("goesvfi.integrity_check.time_index.TimeIndex.to_cdn_url", return_value="https://example.com/test.jpg"),
        ):
            cdn_store._session = session_mock
            
            with pytest.raises(FileNotFoundError):
                await cdn_store.download_file(timestamp, satellite, dest_path)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("satellite_name", ["goes_16", "goes_18"])
    async def test_s3_store_client_creation_and_reuse(self, satellite_test_cases, mock_s3_client, satellite_name):
        """Test S3 store client creation and reuse patterns."""
        s3_client_mock, session_mock = mock_s3_client
        
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
            patch("aioboto3.Session", return_value=session_mock),
            patch("goesvfi.integrity_check.remote.s3_store.Config") as mock_config_class,
            patch("goesvfi.integrity_check.remote.s3_store.UNSIGNED", "UNSIGNED"),
        ):
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            
            s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
            
            # First access should create client
            client1 = await s3_store._get_s3_client()
            assert client1 == s3_client_mock
            
            # Second access should reuse client
            client2 = await s3_store._get_s3_client()
            assert client1 == client2
            
            # Verify configuration
            mock_config_class.assert_called_once()
            config_args = mock_config_class.call_args
            assert config_args[1]["signature_version"] == "UNSIGNED"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("satellite_name", ["goes_16", "goes_18"])
    async def test_s3_store_bucket_and_key_generation(self, satellite_test_cases, satellite_name):
        """Test S3 store bucket and key generation."""
        satellite_config = satellite_test_cases[satellite_name]
        
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
        ):
            s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
        
        timestamp = datetime(2023, 6, 15, 12, 30, 0)
        satellite = satellite_config["satellite"]
        
        # Test default product and band
        bucket, key = s3_store._get_bucket_and_key(timestamp, satellite)
        expected_bucket = TimeIndex.S3_BUCKETS[satellite]
        expected_key = TimeIndex.to_s3_key(timestamp, satellite, product_type="RadC", band=13)
        
        assert bucket == expected_bucket
        assert key == expected_key
        assert satellite_config["expected_bucket"] in bucket
        
        # Test different product types and bands
        test_cases = [
            {"product_type": "RadF", "band": 1},
            {"product_type": "RadC", "band": 7},
            {"product_type": "RadM", "band": 16},
        ]
        
        for case in test_cases:
            bucket, key = s3_store._get_bucket_and_key(
                timestamp, satellite, 
                product_type=case["product_type"], 
                band=case["band"]
            )
            expected_key = TimeIndex.to_s3_key(
                timestamp, satellite, 
                product_type=case["product_type"], 
                band=case["band"]
            )
            assert bucket == expected_bucket
            assert key == expected_key

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error_scenario", ["not_found_errors", "server_errors"])
    async def test_s3_store_file_exists_error_handling(self, s3_error_scenarios, mock_s3_client, error_scenario):
        """Test S3 store error handling during file existence checks."""
        s3_client_mock, session_mock = mock_s3_client
        error_configs = s3_error_scenarios[error_scenario]
        
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
            patch("aioboto3.Session", return_value=session_mock),
        ):
            s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
        
        timestamp = datetime(2023, 6, 15, 12, 0, 0)
        satellite = SatellitePattern.GOES_16
        
        for error_config in error_configs:
            error_response = {"Error": error_config}
            s3_client_mock.head_object.side_effect = botocore.exceptions.ClientError(
                error_response, "HeadObject"
            )
            
            if error_scenario == "not_found_errors":
                # Should return False for not found
                exists = await s3_store.check_file_exists(timestamp, satellite)
                assert not exists
            else:
                # Server errors should also return False
                exists = await s3_store.check_file_exists(timestamp, satellite)
                assert not exists

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error_config", [
        {"Code": "InvalidAccessKeyId", "Message": "Invalid key"},
        {"Code": "SignatureDoesNotMatch", "Message": "Bad signature"},
        {"Code": "AccessDenied", "Message": "Access denied"},
    ])
    async def test_s3_store_authentication_errors(self, mock_s3_client, error_config):
        """Test S3 store authentication error handling."""
        s3_client_mock, session_mock = mock_s3_client
        
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
            patch("aioboto3.Session", return_value=session_mock),
        ):
            s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
        
        timestamp = datetime(2023, 6, 15, 12, 0, 0)
        satellite = SatellitePattern.GOES_16
        
        error_response = {"Error": error_config}
        s3_client_mock.head_object.side_effect = botocore.exceptions.ClientError(
            error_response, "HeadObject"
        )
        
        # Should raise AuthenticationError
        with pytest.raises(AuthenticationError):
            await s3_store.check_file_exists(timestamp, satellite)

    @pytest.mark.asyncio
    async def test_s3_store_successful_file_exists(self, mock_s3_client):
        """Test successful S3 store file existence check."""
        s3_client_mock, session_mock = mock_s3_client
        
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
            patch("aioboto3.Session", return_value=session_mock),
        ):
            s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
        
        timestamp = datetime(2023, 6, 15, 12, 0, 0)
        satellite = SatellitePattern.GOES_16
        
        # Configure successful response
        s3_client_mock.head_object.return_value = {"ContentLength": 12345}
        
        exists = await s3_store.check_file_exists(timestamp, satellite)
        assert exists

    @pytest.mark.asyncio
    async def test_s3_store_download_success(self, mock_s3_client, temp_directory):
        """Test successful S3 store download."""
        s3_client_mock, session_mock = mock_s3_client
        
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
            patch("aioboto3.Session", return_value=session_mock),
        ):
            s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
        
        timestamp = datetime(2023, 6, 15, 12, 0, 0)
        satellite = SatellitePattern.GOES_16
        dest_path = temp_directory / "test_download.nc"
        
        # Mock the download method to return the dest_path
        with patch.object(s3_store, "download", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = dest_path
            
            result = await s3_store.download_file(timestamp, satellite, dest_path)
            
            # Verify
            assert result == dest_path
            mock_download.assert_called_once_with(timestamp, satellite, dest_path)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exception_type", [
        (ResourceNotFoundError, "File not found"),
        (AuthenticationError, "Invalid credentials"),
        (RemoteStoreError, "Server error"),
    ])
    async def test_s3_store_download_error_propagation(self, mock_s3_client, temp_directory, exception_type):
        """Test S3 store download error propagation."""
        s3_client_mock, session_mock = mock_s3_client
        exception_class, error_message = exception_type
        
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
            patch("aioboto3.Session", return_value=session_mock),
        ):
            s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
        
        timestamp = datetime(2023, 6, 15, 12, 0, 0)
        satellite = SatellitePattern.GOES_16
        dest_path = temp_directory / "test_download.nc"
        
        # Mock the download method to raise exception
        with patch.object(s3_store, "download", new_callable=AsyncMock) as mock_download:
            mock_download.side_effect = exception_class(error_message)
            
            with pytest.raises(exception_class):
                await s3_store.download_file(timestamp, satellite, dest_path)

    @pytest.mark.asyncio
    async def test_store_close_operations(self, mock_cdn_session, mock_s3_client):
        """Test store close operations."""
        session_mock, _ = mock_cdn_session
        s3_client_mock, s3_session_mock = mock_s3_client
        
        # Test CDN store close
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        cdn_store._session = session_mock
        
        await cdn_store.close()
        session_mock.close.assert_called_once()
        assert cdn_store._session is None
        
        # Test S3 store close
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
            patch("aioboto3.Session", return_value=s3_session_mock),
        ):
            s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
            s3_store._s3_client = s3_client_mock
            
            await s3_store.close()
            s3_client_mock.__aexit__.assert_called_once()
            assert s3_store._s3_client is None

    def test_performance_bulk_store_operations(self, store_configurations, timestamp_scenarios):
        """Test performance of bulk store operations."""
        import time
        
        # Test store creation performance
        start_time = time.time()
        
        stores = []
        for config_name, config in store_configurations.items():
            if config["store_type"] == "cdn":
                store = CDNStore(resolution=config["resolution"], timeout=config["timeout"])
            else:  # s3
                with (
                    patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
                    patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
                ):
                    store = S3Store(
                        aws_profile=config["aws_profile"],
                        aws_region=config["aws_region"],
                        timeout=config["timeout"]
                    )
            stores.append(store)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should create stores quickly
        assert duration < 1.0, f"Store creation too slow: {duration:.3f}s for {len(stores)} stores"
        assert len(stores) == len(store_configurations)

    def test_memory_efficiency_store_operations(self):
        """Test memory efficiency during store operations."""
        import sys
        
        initial_refs = sys.getrefcount(dict)
        
        # Create and destroy many stores
        for i in range(100):
            if i % 2 == 0:
                store = CDNStore(resolution="1000m", timeout=5)
            else:
                with (
                    patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
                    patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
                ):
                    store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
            
            # Verify store exists
            assert store is not None
            
            # Check memory periodically
            if i % 20 == 0:
                current_refs = sys.getrefcount(dict)
                assert abs(current_refs - initial_refs) <= 20, f"Memory leak at iteration {i}"
        
        final_refs = sys.getrefcount(dict)
        assert abs(final_refs - initial_refs) <= 50, f"Memory leak detected: {initial_refs} -> {final_refs}"

    def test_cross_store_functionality_validation(self, satellite_test_cases, timestamp_scenarios):
        """Test cross-validation of store functionality patterns."""
        # Verify both stores support the same basic interface
        cdn_store = CDNStore(resolution="1000m", timeout=5)
        
        with (
            patch("goesvfi.integrity_check.remote.s3_store.get_system_network_info"),
            patch("goesvfi.integrity_check.remote.s3_store.socket.gethostbyname", return_value="127.0.0.1"),
        ):
            s3_store = S3Store(aws_profile=None, aws_region="us-east-1", timeout=30)
        
        # Both should have required methods
        required_methods = ["check_file_exists", "download_file", "close"]
        
        for method_name in required_methods:
            assert hasattr(cdn_store, method_name), f"CDN store missing method: {method_name}"
            assert hasattr(s3_store, method_name), f"S3 store missing method: {method_name}"
            assert callable(getattr(cdn_store, method_name)), f"CDN store {method_name} not callable"
            assert callable(getattr(s3_store, method_name)), f"S3 store {method_name} not callable"
        
        # Both should support the same satellite patterns
        for satellite_name, satellite_config in satellite_test_cases.items():
            satellite = satellite_config["satellite"]
            
            # Should be able to call _get_bucket_and_key for S3 store
            timestamp = datetime(2023, 6, 15, 12, 0, 0)
            try:
                bucket, key = s3_store._get_bucket_and_key(timestamp, satellite)
                assert bucket is not None
                assert key is not None
            except Exception as e:
                pytest.fail(f"S3 store failed to generate bucket/key for {satellite_name}: {e}")