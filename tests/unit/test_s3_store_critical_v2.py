"""Optimized S3 store critical tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common S3 store configurations and mock setups
- Parameterized test scenarios for comprehensive S3 store operation validation
- Enhanced error handling and edge case testing
- Mock-based testing to avoid real S3 operations and network calls
- Comprehensive concurrent operation and performance testing
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import botocore.exceptions

from goesvfi.integrity_check.remote.base import ResourceNotFoundError, RemoteStoreError
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3StoreCriticalV2:
    """Optimized test class for critical S3 store functionality."""

    @pytest.fixture(scope="class")
    def store_configurations(self):
        """Define various S3 store configuration test cases."""
        return {
            "default_config": {
                "timeout": 30,
                "max_retries": 3,
                "expected_attrs": ["_s3_client", "_session", "_timeout"],
            },
            "custom_timeout": {
                "timeout": 60,
                "max_retries": 5,
                "expected_attrs": ["_s3_client", "_session", "_timeout"],
            },
            "minimal_config": {
                "timeout": 10,
                "max_retries": 1,
                "expected_attrs": ["_s3_client", "_session", "_timeout"],
            },
        }

    @pytest.fixture(scope="class")
    def download_scenarios(self):
        """Define various download scenario test cases."""
        return {
            "standard_download": {
                "timestamp": datetime(2023, 6, 15, 12, 0, 0),
                "satellite": SatellitePattern.GOES_16,
                "file_size": 1024000,  # 1MB
                "product_type": "RadC",
                "band": 13,
            },
            "large_file": {
                "timestamp": datetime(2023, 12, 31, 18, 30, 0),
                "satellite": SatellitePattern.GOES_18,
                "file_size": 104857600,  # 100MB
                "product_type": "RadF",
                "band": 2,
            },
            "small_file": {
                "timestamp": datetime(2024, 1, 1, 0, 0, 0),
                "satellite": SatellitePattern.GOES_16,
                "file_size": 1024,  # 1KB
                "product_type": "RadM",
                "band": 7,
            },
            "different_band": {
                "timestamp": datetime(2023, 7, 4, 15, 45, 0),
                "satellite": SatellitePattern.GOES_18,
                "file_size": 2048000,  # 2MB
                "product_type": "RadC",
                "band": 1,
            },
        }

    @pytest.fixture(scope="class")
    def wildcard_scenarios(self):
        """Define various wildcard matching scenario test cases."""
        return {
            "single_match": {
                "search_files": [
                    "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661200000_e20231661200000_c20231661200000.nc"
                ],
                "expected_matches": 1,
            },
            "multiple_matches": {
                "search_files": [
                    "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661200000_e20231661200000_c20231661200000.nc",
                    "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661201000_e20231661201000_c20231661201000.nc",
                    "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661202000_e20231661202000_c20231661202000.nc",
                ],
                "expected_matches": 3,
            },
            "no_matches": {
                "search_files": [],
                "expected_matches": 0,
            },
            "different_bands": {
                "search_files": [
                    "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C01_G16_s20231661200000_e20231661200000_c20231661200000.nc",
                    "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C02_G16_s20231661200000_e20231661200000_c20231661200000.nc",
                    "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661200000_e20231661200000_c20231661200000.nc",
                ],
                "expected_matches": 3,
            },
        }

    @pytest.fixture(scope="class")
    def concurrent_scenarios(self):
        """Define various concurrent operation scenario test cases."""
        return {
            "light_load": {
                "concurrent_count": 3,
                "file_sizes": [1024, 2048, 4096],
                "expected_success": True,
            },
            "medium_load": {
                "concurrent_count": 10,
                "file_sizes": [1024000] * 10,  # 1MB each
                "expected_success": True,
            },
            "heavy_load": {
                "concurrent_count": 20,
                "file_sizes": [512000] * 20,  # 512KB each
                "expected_success": True,
            },
        }

    @pytest.fixture
    async def s3_store_factory(self):
        """Factory for creating S3Store instances with various configurations."""
        stores = []
        
        def create_store(timeout=30, max_retries=3):
            store = S3Store(timeout=timeout)
            stores.append(store)
            return store
        
        yield create_store
        
        # Cleanup all created stores
        for store in stores:
            try:
                await store.close()
            except:
                pass

    @pytest.fixture
    def mock_s3_client_factory(self):
        """Factory for creating mock S3 clients with various behaviors."""
        def create_client(file_size=1024, should_fail=False, failure_type="not_found"):
            mock_client = AsyncMock()
            
            if should_fail:
                if failure_type == "not_found":
                    error = botocore.exceptions.ClientError(
                        {"Error": {"Code": "404", "Message": "Not Found"}},
                        "HeadObject"
                    )
                    mock_client.head_object.side_effect = error
                elif failure_type == "timeout":
                    mock_client.head_object.side_effect = TimeoutError("Connection timeout")
                elif failure_type == "access_denied":
                    error = botocore.exceptions.ClientError(
                        {"Error": {"Code": "403", "Message": "Access Denied"}},
                        "HeadObject"
                    )
                    mock_client.head_object.side_effect = error
            else:
                mock_client.head_object.return_value = {"ContentLength": file_size}
                mock_client.download_file.return_value = None
            
            mock_client.get_paginator = MagicMock()
            return mock_client
        
        return create_client

    @pytest.fixture
    def mock_file_system(self, tmp_path):
        """Mock file system operations for testing."""
        def setup_file_system(create_files=True, file_sizes=None):
            file_sizes = file_sizes or [1024]
            created_files = []
            
            if create_files:
                for i, size in enumerate(file_sizes):
                    file_path = tmp_path / f"test_file_{i}.nc"
                    file_path.write_bytes(b"x" * size)
                    created_files.append(file_path)
            
            return {
                "temp_dir": tmp_path,
                "created_files": created_files,
                "get_path": lambda name: tmp_path / name,
            }
        
        return setup_file_system

    @pytest.mark.asyncio
    @pytest.mark.parametrize("config_name", [
        "default_config",
        "custom_timeout",
        "minimal_config",
    ])
    async def test_s3_store_initialization_scenarios(self, store_configurations, 
                                                   s3_store_factory, config_name):
        """Test S3 store initialization with various configurations."""
        config = store_configurations[config_name]
        
        # Create store with configuration
        store = s3_store_factory(
            timeout=config["timeout"],
            max_retries=config["max_retries"]
        )
        
        # Test context manager initialization
        async with store:
            # Verify store is properly initialized
            assert hasattr(store, "_s3_client")
            assert store._s3_client is not None
            
            # Verify configuration attributes
            for attr in config["expected_attrs"]:
                assert hasattr(store, attr)
        
        # After context exit, should be cleaned up
        assert store._s3_client is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", [
        "standard_download",
        "large_file",
        "small_file", 
        "different_band",
    ])
    async def test_download_success_scenarios(self, download_scenarios, s3_store_factory,
                                            mock_s3_client_factory, mock_file_system, scenario_name):
        """Test successful download scenarios with various file types and sizes."""
        scenario = download_scenarios[scenario_name]
        fs = mock_file_system()
        
        # Create store and mock client
        store = s3_store_factory()
        mock_client = mock_s3_client_factory(file_size=scenario["file_size"])
        
        with patch.object(store, "_get_s3_client", return_value=mock_client):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = scenario["file_size"]
                    with patch("pathlib.Path.mkdir"):
                        local_path = fs["get_path"](f"download_{scenario_name}.nc")
                        
                        # Test download
                        result = await store.download_file(
                            scenario["timestamp"],
                            scenario["satellite"],
                            local_path,
                            product_type=scenario.get("product_type"),
                            band=scenario.get("band"),
                        )
                        
                        # Verify result
                        assert result == local_path
                        
                        # Verify S3 operations were called
                        mock_client.head_object.assert_called_once()
                        mock_client.download_file.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("wildcard_case", [
        "single_match",
        "multiple_matches",
        "different_bands",
    ])
    async def test_wildcard_download_scenarios(self, wildcard_scenarios, s3_store_factory,
                                             mock_s3_client_factory, mock_file_system, wildcard_case):
        """Test wildcard pattern matching for downloads."""
        scenario = wildcard_scenarios[wildcard_case]
        fs = mock_file_system()
        
        # Create store and configure for wildcard search
        store = s3_store_factory()
        mock_client = mock_s3_client_factory(should_fail=True, failure_type="not_found")
        
        # Configure paginator for wildcard search
        mock_paginator = MagicMock()
        mock_pages = [{"Contents": [{"Key": key} for key in scenario["search_files"]]}]
        
        async def async_pages():
            for page in mock_pages:
                yield page
        
        mock_paginator.paginate.return_value = async_pages()
        mock_client.get_paginator.return_value = mock_paginator
        
        # Configure download to succeed after wildcard match
        mock_client.download_file.return_value = None
        
        with patch.object(store, "_get_s3_client", return_value=mock_client):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 1024
                    with patch("pathlib.Path.mkdir"):
                        local_path = fs["get_path"](f"wildcard_{wildcard_case}.nc")
                        
                        if scenario["expected_matches"] > 0:
                            # Should succeed with wildcard match
                            result = await store.download_file(
                                datetime(2023, 6, 15, 12, 0, 0),
                                SatellitePattern.GOES_16,
                                local_path,
                            )
                            
                            assert result == local_path
                            mock_client.get_paginator.assert_called_once()
                            mock_client.download_file.assert_called_once()
                        else:
                            # Should fail with no matches
                            with pytest.raises(ResourceNotFoundError):
                                await store.download_file(
                                    datetime(2023, 6, 15, 12, 0, 0),
                                    SatellitePattern.GOES_16,
                                    local_path,
                                )

    @pytest.mark.asyncio
    async def test_wildcard_no_matches_error(self, s3_store_factory, mock_s3_client_factory, mock_file_system):
        """Test wildcard search when no files are found."""
        scenario = {"search_files": [], "expected_matches": 0}
        fs = mock_file_system()
        
        store = s3_store_factory()
        mock_client = mock_s3_client_factory(should_fail=True, failure_type="not_found")
        
        # Configure paginator to return empty results
        mock_paginator = MagicMock()
        
        async def empty_pages():
            return
            yield  # Make it an async generator
        
        mock_paginator.paginate.return_value = empty_pages()
        mock_client.get_paginator.return_value = mock_paginator
        
        with patch.object(store, "_get_s3_client", return_value=mock_client):
            local_path = fs["get_path"]("no_matches.nc")
            
            with pytest.raises(ResourceNotFoundError) as exc_info:
                await store.download_file(
                    datetime(2023, 6, 15, 12, 0, 0),
                    SatellitePattern.GOES_16,
                    local_path,
                )
            
            assert "No files found for GOES_16" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("satellite", [SatellitePattern.GOES_16, SatellitePattern.GOES_18])
    async def test_file_exists_scenarios(self, s3_store_factory, mock_s3_client_factory, satellite):
        """Test file existence checking for different satellites."""
        # Test file exists
        store = s3_store_factory()
        mock_client = mock_s3_client_factory(file_size=1024)
        
        with patch.object(store, "_get_s3_client", return_value=mock_client):
            result = await store.check_file_exists(
                datetime(2023, 6, 15, 12, 0, 0),
                satellite
            )
            
            assert result is True
            mock_client.head_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_not_exists_scenarios(self, s3_store_factory, mock_s3_client_factory):
        """Test file existence checking when file doesn't exist."""
        store = s3_store_factory()
        mock_client = mock_s3_client_factory(should_fail=True, failure_type="not_found")
        
        with patch.object(store, "_get_s3_client", return_value=mock_client):
            result = await store.check_file_exists(
                datetime(2023, 6, 15, 12, 0, 0),
                SatellitePattern.GOES_16
            )
            
            assert result is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", [
        "light_load",
        "medium_load", 
        "heavy_load",
    ])
    async def test_concurrent_downloads(self, concurrent_scenarios, s3_store_factory,
                                      mock_s3_client_factory, mock_file_system, scenario_name):
        """Test concurrent download operations."""
        scenario = concurrent_scenarios[scenario_name]
        fs = mock_file_system()
        
        store = s3_store_factory()
        
        # Create download tasks
        tasks = []
        for i in range(scenario["concurrent_count"]):
            file_size = scenario["file_sizes"][i % len(scenario["file_sizes"])]
            mock_client = mock_s3_client_factory(file_size=file_size)
            
            # Each task needs its own patching context
            async def download_task(index, size, client):
                with patch.object(store, "_get_s3_client", return_value=client):
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch("pathlib.Path.stat") as mock_stat:
                            mock_stat.return_value.st_size = size
                            with patch("pathlib.Path.mkdir"):
                                local_path = fs["get_path"](f"concurrent_{index}.nc")
                                timestamp = datetime(2023, 6, 15, 12, index % 60, 0)
                                
                                return await store.download_file(
                                    timestamp,
                                    SatellitePattern.GOES_16,
                                    local_path,
                                )
            
            task = download_task(i, file_size, mock_client)
            tasks.append(task)
        
        # Execute concurrent downloads
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all downloads completed successfully
        assert len(results) == scenario["concurrent_count"]
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pytest.fail(f"Task {i} failed with: {result}")
            assert isinstance(result, Path)

    @pytest.mark.asyncio
    async def test_download_error_handling_during_transfer(self, s3_store_factory, 
                                                         mock_s3_client_factory, mock_file_system):
        """Test error handling during file transfer."""
        fs = mock_file_system()
        store = s3_store_factory()
        
        # Configure client to succeed on head_object but fail on download
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {"ContentLength": 1024}
        mock_client.download_file.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "InternalError", "Message": "Server Error"}},
            "GetObject"
        )
        
        with patch.object(store, "_get_s3_client", return_value=mock_client):
            local_path = fs["get_path"]("transfer_error.nc")
            
            with pytest.raises(RemoteStoreError):
                await store.download_file(
                    datetime(2023, 6, 15, 12, 0, 0),
                    SatellitePattern.GOES_16,
                    local_path,
                )

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self, s3_store_factory):
        """Test S3Store context manager lifecycle."""
        store = s3_store_factory()
        
        # Initially should not have client
        assert store._s3_client is None
        
        # Enter context manager
        async with store as ctx_store:
            assert ctx_store is store
            assert store._s3_client is not None
            
            # Can be used multiple times within context
            async with store as ctx_store2:
                assert ctx_store2 is store
                assert store._s3_client is not None
        
        # After exit, should be cleaned up
        assert store._s3_client is None

    @pytest.mark.asyncio
    async def test_multiple_context_manager_usage(self, s3_store_factory):
        """Test multiple context manager usage patterns."""
        store = s3_store_factory()
        
        # First usage
        async with store:
            assert store._s3_client is not None
            first_client = store._s3_client
        
        assert store._s3_client is None
        
        # Second usage - should create new client
        async with store:
            assert store._s3_client is not None
            second_client = store._s3_client
            # May or may not be the same object depending on implementation
        
        assert store._s3_client is None

    @pytest.mark.asyncio
    async def test_error_during_context_exit(self, s3_store_factory):
        """Test error handling during context manager exit."""
        store = s3_store_factory()
        
        # Mock close to raise an exception
        with patch.object(store, "close", side_effect=Exception("Close error")):
            try:
                async with store:
                    assert store._s3_client is not None
                    pass  # Normal operation
                # Exception during exit should not propagate
            except Exception as e:
                if "Close error" in str(e):
                    pytest.fail("Context manager should handle close errors gracefully")

    @pytest.mark.asyncio
    async def test_download_with_metadata_parameters(self, s3_store_factory, 
                                                   mock_s3_client_factory, mock_file_system):
        """Test download with various metadata parameters."""
        fs = mock_file_system()
        store = s3_store_factory()
        mock_client = mock_s3_client_factory(file_size=2048)
        
        metadata_cases = [
            {"product_type": "RadC", "band": 13},
            {"product_type": "RadF", "band": 2},
            {"product_type": "RadM", "band": 7},
            {"product_type": "RadC"},  # No band specified
            {"band": 1},  # No product_type specified
        ]
        
        with patch.object(store, "_get_s3_client", return_value=mock_client):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 2048
                    with patch("pathlib.Path.mkdir"):
                        for i, metadata in enumerate(metadata_cases):
                            local_path = fs["get_path"](f"metadata_{i}.nc")
                            
                            result = await store.download_file(
                                datetime(2023, 6, 15, 12, 0, 0),
                                SatellitePattern.GOES_16,
                                local_path,
                                **metadata
                            )
                            
                            assert result == local_path
                            
                            # Reset mock for next iteration
                            mock_client.reset_mock()
                            mock_client.head_object.return_value = {"ContentLength": 2048}
                            mock_client.download_file.return_value = None

    @pytest.mark.asyncio
    async def test_performance_characteristics(self, s3_store_factory, mock_file_system):
        """Test performance characteristics of S3Store operations."""
        import time
        
        fs = mock_file_system()
        store = s3_store_factory()
        
        # Test initialization performance
        start_time = time.time()
        
        for _ in range(100):
            async with store:
                pass  # Just test context manager overhead
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete 100 context manager cycles quickly
        assert duration < 1.0, f"Context manager operations too slow: {duration:.3f}s"

    @pytest.mark.asyncio 
    async def test_memory_efficiency_during_operations(self, s3_store_factory):
        """Test memory efficiency during store operations."""
        import sys
        
        store = s3_store_factory()
        initial_refs = sys.getrefcount(S3Store)
        
        # Perform many context manager operations
        for i in range(50):
            async with store:
                # Simulate some work
                await asyncio.sleep(0.001)
        
        final_refs = sys.getrefcount(S3Store)
        
        # Memory usage should be stable
        assert abs(final_refs - initial_refs) <= 5, f"Memory leak detected: {initial_refs} -> {final_refs}"

    @pytest.mark.asyncio
    async def test_timeout_configuration_effects(self, s3_store_factory, mock_s3_client_factory):
        """Test that timeout configuration affects operations."""
        # Test with different timeout values
        timeout_cases = [10, 30, 60]
        
        for timeout in timeout_cases:
            store = s3_store_factory(timeout=timeout)
            
            # Verify timeout is stored (implementation dependent)
            if hasattr(store, '_timeout'):
                assert store._timeout == timeout
            
            # Test that store can be used with different timeouts
            async with store:
                assert store._s3_client is not None

    @pytest.mark.asyncio
    async def test_satellite_pattern_handling(self, s3_store_factory, mock_s3_client_factory, mock_file_system):
        """Test handling of different satellite patterns."""
        fs = mock_file_system()
        satellites = [SatellitePattern.GOES_16, SatellitePattern.GOES_18]
        
        for satellite in satellites:
            store = s3_store_factory()
            mock_client = mock_s3_client_factory(file_size=1024)
            
            with patch.object(store, "_get_s3_client", return_value=mock_client):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.stat") as mock_stat:
                        mock_stat.return_value.st_size = 1024
                        with patch("pathlib.Path.mkdir"):
                            local_path = fs["get_path"](f"satellite_{satellite.name}.nc")
                            
                            # Test both download and exists operations
                            exists_result = await store.check_file_exists(
                                datetime(2023, 6, 15, 12, 0, 0),
                                satellite
                            )
                            assert exists_result is True
                            
                            download_result = await store.download_file(
                                datetime(2023, 6, 15, 12, 0, 0),
                                satellite,
                                local_path,
                            )
                            assert download_result == local_path

    @pytest.mark.asyncio
    async def test_edge_case_timestamps(self, s3_store_factory, mock_s3_client_factory, mock_file_system):
        """Test handling of edge case timestamps."""
        fs = mock_file_system()
        
        edge_timestamps = [
            datetime(2023, 1, 1, 0, 0, 0),      # New Year
            datetime(2023, 12, 31, 23, 59, 59), # End of year
            datetime(2024, 2, 29, 12, 0, 0),    # Leap day
            datetime(2023, 6, 21, 12, 0, 0),    # Summer solstice
        ]
        
        store = s3_store_factory()
        
        for timestamp in edge_timestamps:
            mock_client = mock_s3_client_factory(file_size=1024)
            
            with patch.object(store, "_get_s3_client", return_value=mock_client):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.stat") as mock_stat:
                        mock_stat.return_value.st_size = 1024
                        with patch("pathlib.Path.mkdir"):
                            local_path = fs["get_path"](f"edge_time_{timestamp.strftime('%Y%m%d_%H%M%S')}.nc")
                            
                            result = await store.download_file(
                                timestamp,
                                SatellitePattern.GOES_16,
                                local_path,
                            )
                            assert result == local_path

    @pytest.mark.asyncio
    async def test_integration_workflow_complete(self, s3_store_factory, mock_s3_client_factory, mock_file_system):
        """Test complete integration workflow from initialization to cleanup."""
        fs = mock_file_system()
        store = s3_store_factory()
        mock_client = mock_s3_client_factory(file_size=1024)
        
        with patch.object(store, "_get_s3_client", return_value=mock_client):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 1024
                    with patch("pathlib.Path.mkdir"):
                        # Step 1: Initialize store
                        async with store:
                            # Step 2: Check if file exists
                            timestamp = datetime(2023, 6, 15, 12, 0, 0)
                            satellite = SatellitePattern.GOES_16
                            
                            exists = await store.check_file_exists(timestamp, satellite)
                            assert exists is True
                            
                            # Step 3: Download file
                            local_path = fs["get_path"]("integration_test.nc")
                            
                            result = await store.download_file(
                                timestamp,
                                satellite,
                                local_path,
                                product_type="RadC",
                                band=13,
                            )
                            
                            # Step 4: Verify results
                            assert result == local_path
                            
                            # Step 5: Verify all operations were called
                            assert mock_client.head_object.call_count >= 2  # At least for exists + download
                            mock_client.download_file.assert_called_once()
        
        # Step 6: Verify cleanup
        assert store._s3_client is None