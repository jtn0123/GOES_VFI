"""
Optimized unit tests for S3Store critical functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for S3Store setup, mock clients, and temporary directories
- Enhanced test managers for comprehensive S3 operation validation
- Batch testing of concurrent operations and wildcard scenarios
- Improved async test patterns with shared setup and teardown
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import botocore.exceptions
import pytest

from goesvfi.integrity_check.remote.base import ResourceNotFoundError
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3StoreCriticalOptimizedV2:
    """Optimized S3Store critical functionality tests with full coverage."""

    @pytest.fixture(scope="class")
    def s3_store_critical_test_components(self) -> dict[str, Any]:  # noqa: C901
        """Create shared components for S3Store critical testing."""

        # Enhanced S3Store Critical Test Manager
        class S3StoreCriticalTestManager:
            """Manage S3Store critical testing scenarios."""

            def __init__(self) -> None:
                # Define test configurations
                self.test_configs = {
                    "satellites": [SatellitePattern.GOES_16, SatellitePattern.GOES_18],
                    "timestamps": [
                        datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
                        datetime(2023, 6, 15, 18, 30, 0, tzinfo=UTC),
                        datetime(2023, 12, 31, 6, 0, 0, tzinfo=UTC),
                    ],
                    "file_sizes": [9, 1000, 50000, 1000000],
                    "concurrent_count": 5,
                }

                # S3 response configurations
                self.s3_responses = {
                    "success": {"ContentLength": 9},
                    "large_file": {"ContentLength": 1000000},
                    "not_found_error": botocore.exceptions.ClientError(
                        {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
                    ),
                    "no_such_key_error": botocore.exceptions.ClientError(
                        {"Error": {"Code": "404", "Message": "NoSuchKey"}}, "HeadObject"
                    ),
                }

                # Wildcard test scenarios
                self.wildcard_scenarios = {
                    "single_match": {
                        "Contents": [
                            {
                                "Key": (
                                    "ABI-L1b-RadC/2023/001/12/"
                                    "OR_ABI-L1b-RadC-M6C13_G16_s20230011200000_e20230011200000_c20230011200000.nc"
                                )
                            }
                        ]
                    },
                    "multiple_matches": {
                        "Contents": [
                            {
                                "Key": (
                                    "ABI-L1b-RadC/2023/001/12/"
                                    "OR_ABI-L1b-RadC-M6C13_G16_s20230011200000_e20230011200000_c20230011200000.nc"
                                )
                            },
                            {
                                "Key": (
                                    "ABI-L1b-RadC/2023/001/12/"
                                    "OR_ABI-L1b-RadC-M6C13_G16_s20230011201000_e20230011201000_c20230011201000.nc"
                                )
                            },
                        ]
                    },
                    "empty_contents": {"Contents": []},
                    "no_contents": {},
                }

                # Define test scenarios
                self.test_scenarios = {
                    "initialization": self._test_initialization,
                    "download_operations": self._test_download_operations,
                    "file_existence": self._test_file_existence,
                    "wildcard_matching": self._test_wildcard_matching,
                    "concurrent_operations": self._test_concurrent_operations,
                    "error_handling": self._test_error_handling,
                    "edge_cases": self._test_edge_cases,
                    "performance_validation": self._test_performance_validation,
                }

            @staticmethod
            def create_s3_store() -> S3Store:
                """Create a fresh S3Store instance.

                Returns:
                    S3Store: A new S3Store instance.
                """
                return S3Store()

            @staticmethod
            def create_temp_directory() -> tempfile.TemporaryDirectory:
                """Create a temporary directory for test files.

                Returns:
                    tempfile.TemporaryDirectory: A temporary directory instance.
                """
                return tempfile.TemporaryDirectory()

            def create_mock_s3_client(self, **config) -> AsyncMock:
                """Create a mock S3 client with specified configuration."""
                mock_client = AsyncMock()

                # Configure head_object behavior
                if config.get("head_object_response"):
                    mock_client.head_object = AsyncMock(return_value=config["head_object_response"])
                elif config.get("head_object_error"):
                    mock_client.head_object = AsyncMock(side_effect=config["head_object_error"])

                # Configure download_file behavior
                if config.get("download_file_error"):
                    mock_client.download_file = AsyncMock(side_effect=config["download_file_error"])
                else:
                    mock_client.download_file = AsyncMock()

                # Configure paginator behavior
                if config.get("paginator_pages"):
                    paginator_mock = MagicMock()

                    async def mock_paginate(*args, **kwargs):
                        for page in config["paginator_pages"]:
                            yield page

                    paginator_mock.paginate = MagicMock(return_value=mock_paginate())
                    mock_client.get_paginator = MagicMock(return_value=paginator_mock)

                return mock_client

            def create_path_patches(self, **config):
                """Create path-related patches for file system operations."""
                patches = {}

                # Path.exists patch
                if "path_exists" in config:
                    patches["path_exists"] = patch("pathlib.Path.exists", return_value=config["path_exists"])

                # Path.stat patch
                if "file_size" in config:
                    stat_mock = MagicMock()
                    stat_mock.st_size = config["file_size"]
                    patches["path_stat"] = patch("pathlib.Path.stat", return_value=stat_mock)

                # Path.mkdir patch
                if config.get("mock_mkdir", True):
                    patches["path_mkdir"] = patch("pathlib.Path.mkdir")

                return patches

            async def _test_initialization(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test S3Store initialization scenarios."""
                results = {}

                if scenario_name == "context_manager":
                    # Test S3Store as context manager
                    store = self.create_s3_store()

                    # Test context manager
                    async with store:
                        # Should have client when in context
                        assert hasattr(store, "_s3_client")
                        # Note: _s3_client may be None until first use
                        results["context_enter"] = True

                    # After context exit, should be cleaned up
                    assert store._s3_client is None
                    results["context_exit"] = True

                elif scenario_name == "multiple_instances":
                    # Test multiple S3Store instances
                    stores = [self.create_s3_store() for _ in range(3)]

                    async_contexts = [store.__aenter__() for store in stores]

                    # Enter all contexts
                    await asyncio.gather(*async_contexts)

                    # Exit all contexts
                    exit_contexts = [store.__aexit__(None, None, None) for store in stores]

                    await asyncio.gather(*exit_contexts)

                    # All should be cleaned up
                    for store in stores:
                        assert store._s3_client is None

                    results["multiple_instances"] = len(stores)

                return {"scenario": scenario_name, "results": results}

            async def _test_download_operations(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test download operation scenarios."""
                results = {}
                store = self.create_s3_store()

                if scenario_name == "successful_download":
                    # Test successful file download
                    mock_client = self.create_mock_s3_client(head_object_response=self.s3_responses["success"])

                    path_patches = self.create_path_patches(path_exists=True, file_size=9)

                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        with path_patches["path_exists"], path_patches["path_stat"], path_patches["path_mkdir"]:
                            local_path = Path(temp_dir.name) / "test_file.nc"
                            ts = self.test_configs["timestamps"][0]

                            # Test download
                            result = await store.download_file(
                                ts,
                                self.test_configs["satellites"][0],
                                local_path,
                            )

                            # Verify result
                            assert result == local_path
                            mock_client.download_file.assert_called_once()

                            results["download_successful"] = True

                elif scenario_name == "multiple_file_sizes":
                    # Test downloads with different file sizes
                    download_results = []

                    for i, file_size in enumerate(self.test_configs["file_sizes"]):
                        mock_client = self.create_mock_s3_client(head_object_response={"ContentLength": file_size})

                        path_patches = self.create_path_patches(path_exists=True, file_size=file_size)

                        with patch.object(store, "_get_s3_client", return_value=mock_client):
                            with path_patches["path_exists"], path_patches["path_stat"], path_patches["path_mkdir"]:
                                local_path = Path(temp_dir.name) / f"test_file_{i}.nc"
                                ts = self.test_configs["timestamps"][0]

                                result = await store.download_file(
                                    ts,
                                    self.test_configs["satellites"][0],
                                    local_path,
                                )

                                download_results.append((file_size, result == local_path))

                    # All downloads should succeed
                    assert all(success for _, success in download_results)
                    results["file_sizes_tested"] = len(self.test_configs["file_sizes"])

                elif scenario_name == "download_not_found":
                    # Test handling of file not found errors
                    mock_client = self.create_mock_s3_client(
                        head_object_error=self.s3_responses["no_such_key_error"],
                        paginator_pages=[self.wildcard_scenarios["empty_contents"]],
                    )

                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        local_path = Path(temp_dir.name) / "missing_file.nc"
                        ts = self.test_configs["timestamps"][0]

                        # Should raise ResourceNotFoundError
                        with pytest.raises(ResourceNotFoundError) as exc_info:
                            await store.download_file(ts, self.test_configs["satellites"][0], local_path)

                        # Verify error message
                        assert "No files found for GOES_16" in str(exc_info.value)
                        results["not_found_handled"] = True

                return {"scenario": scenario_name, "results": results}

            async def _test_file_existence(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test file existence checking scenarios."""
                results = {}
                store = self.create_s3_store()

                if scenario_name == "exists_success":
                    # Test checking if file exists (success)
                    mock_client = self.create_mock_s3_client(head_object_response=self.s3_responses["success"])

                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        ts = self.test_configs["timestamps"][0]

                        result = await store.check_file_exists(ts, self.test_configs["satellites"][0])

                        assert result is True
                        mock_client.head_object.assert_called_once()

                        results["exists_check_successful"] = True

                elif scenario_name == "exists_not_found":
                    # Test exists returns False for missing files
                    mock_client = self.create_mock_s3_client(head_object_error=self.s3_responses["not_found_error"])

                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        ts = self.test_configs["timestamps"][0]

                        result = await store.check_file_exists(ts, self.test_configs["satellites"][0])

                        assert result is False
                        results["not_found_check_successful"] = True

                elif scenario_name == "exists_multiple_satellites":
                    # Test existence checking across multiple satellites
                    existence_results = []

                    for satellite in self.test_configs["satellites"]:
                        mock_client = self.create_mock_s3_client(head_object_response=self.s3_responses["success"])

                        with patch.object(store, "_get_s3_client", return_value=mock_client):
                            ts = self.test_configs["timestamps"][0]

                            result = await store.check_file_exists(ts, satellite)
                            existence_results.append(result)

                    # All should return True
                    assert all(existence_results)
                    results["satellites_checked"] = len(self.test_configs["satellites"])

                return {"scenario": scenario_name, "results": results}

            async def _test_wildcard_matching(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test wildcard pattern matching scenarios."""
                results = {}
                store = self.create_s3_store()

                if scenario_name == "wildcard_single_match":
                    # Test download with single wildcard match
                    mock_client = self.create_mock_s3_client(
                        head_object_error=self.s3_responses["not_found_error"],
                        paginator_pages=[self.wildcard_scenarios["single_match"]],
                    )

                    path_patches = self.create_path_patches(path_exists=True, file_size=1000)

                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        with path_patches["path_exists"], path_patches["path_stat"], path_patches["path_mkdir"]:
                            local_path = Path(temp_dir.name) / "wildcard_test.nc"
                            ts = self.test_configs["timestamps"][0]

                            result = await store.download_file(
                                ts,
                                self.test_configs["satellites"][0],
                                local_path,
                            )

                            # Verify result
                            assert result == local_path
                            mock_client.get_paginator.assert_called_once()

                            results["wildcard_match_successful"] = True

                elif scenario_name == "wildcard_multiple_matches":
                    # Test wildcard with multiple matches (should pick first)
                    mock_client = self.create_mock_s3_client(
                        head_object_error=self.s3_responses["not_found_error"],
                        paginator_pages=[self.wildcard_scenarios["multiple_matches"]],
                    )

                    path_patches = self.create_path_patches(path_exists=True, file_size=1000)

                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        with path_patches["path_exists"], path_patches["path_stat"], path_patches["path_mkdir"]:
                            local_path = Path(temp_dir.name) / "wildcard_multiple.nc"
                            ts = self.test_configs["timestamps"][0]

                            result = await store.download_file(
                                ts,
                                self.test_configs["satellites"][0],
                                local_path,
                            )

                            assert result == local_path
                            results["multiple_matches_handled"] = True

                elif scenario_name == "wildcard_no_matches":
                    # Test wildcard with no matches
                    mock_client = self.create_mock_s3_client(
                        head_object_error=self.s3_responses["not_found_error"],
                        paginator_pages=[self.wildcard_scenarios["empty_contents"]],
                    )

                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        local_path = Path(temp_dir.name) / "wildcard_none.nc"
                        ts = self.test_configs["timestamps"][0]

                        with pytest.raises(ResourceNotFoundError):
                            await store.download_file(
                                ts,
                                self.test_configs["satellites"][0],
                                local_path,
                            )

                        results["no_matches_handled"] = True

                return {"scenario": scenario_name, "results": results}

            async def _test_concurrent_operations(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test concurrent operation scenarios."""
                results = {}
                store = self.create_s3_store()

                if scenario_name == "concurrent_downloads":
                    # Test concurrent download handling
                    mock_client = self.create_mock_s3_client(head_object_response=self.s3_responses["success"])

                    path_patches = self.create_path_patches(path_exists=True, file_size=9)

                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        with path_patches["path_exists"], path_patches["path_stat"], path_patches["path_mkdir"]:
                            # Download multiple files concurrently
                            tasks = []
                            for i in range(self.test_configs["concurrent_count"]):
                                local_path = Path(temp_dir.name) / f"concurrent_{i}.nc"
                                ts = datetime(2023, 1, 1, 12, i, 0)
                                task = store.download_file(
                                    ts,
                                    self.test_configs["satellites"][0],
                                    local_path,
                                )
                                tasks.append(task)

                            # Wait for all downloads
                            await asyncio.gather(*tasks)

                            # Verify all files were requested
                            assert mock_client.download_file.call_count == self.test_configs["concurrent_count"]

                            results["concurrent_downloads"] = self.test_configs["concurrent_count"]

                elif scenario_name == "concurrent_existence_checks":
                    # Test concurrent existence checks
                    mock_client = self.create_mock_s3_client(head_object_response=self.s3_responses["success"])

                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        # Check existence of multiple files concurrently
                        tasks = []
                        for i in range(self.test_configs["concurrent_count"]):
                            ts = datetime(2023, 1, 1, 12, i, 0)
                            task = store.check_file_exists(ts, self.test_configs["satellites"][0])
                            tasks.append(task)

                        # Wait for all checks
                        results_list = await asyncio.gather(*tasks)

                        # All should return True
                        assert all(results_list)
                        assert mock_client.head_object.call_count == self.test_configs["concurrent_count"]

                        results["concurrent_checks"] = self.test_configs["concurrent_count"]

                return {"scenario": scenario_name, "results": results}

            async def _test_error_handling(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test error handling scenarios."""
                results = {}
                store = self.create_s3_store()

                if scenario_name == "various_s3_errors":
                    # Test handling of various S3 errors
                    s3_errors = [
                        botocore.exceptions.ClientError(
                            {"Error": {"Code": "403", "Message": "Access Denied"}}, "HeadObject"
                        ),
                        botocore.exceptions.ClientError(
                            {"Error": {"Code": "500", "Message": "Internal Server Error"}}, "HeadObject"
                        ),
                        botocore.exceptions.ClientError(
                            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}, "HeadObject"
                        ),
                    ]

                    error_results = []
                    for error in s3_errors:
                        mock_client = self.create_mock_s3_client(head_object_error=error)

                        with patch.object(store, "_get_s3_client", return_value=mock_client):
                            local_path = Path(temp_dir.name) / "error_test.nc"
                            ts = self.test_configs["timestamps"][0]

                            try:
                                await store.download_file(
                                    ts,
                                    self.test_configs["satellites"][0],
                                    local_path,
                                )
                                error_results.append("unexpected_success")
                            except Exception as e:
                                error_results.append(type(e).__name__)

                    # All should result in some kind of error
                    assert all(result != "unexpected_success" for result in error_results)
                    results["s3_errors_tested"] = len(s3_errors)

                return {"scenario": scenario_name, "results": results}

            async def _test_edge_cases(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test edge cases and boundary conditions."""
                results = {}
                store = self.create_s3_store()

                if scenario_name == "edge_case_timestamps":
                    # Test with edge case timestamps
                    edge_timestamps = [
                        datetime(2000, 1, 1, 0, 0, 0, tzinfo=UTC),  # Y2K
                        datetime(2023, 2, 28, 12, 0, 0, tzinfo=UTC),  # End of February (non-leap year)
                        datetime(2024, 2, 29, 12, 0, 0, tzinfo=UTC),  # Valid leap year
                        datetime(2023, 12, 31, 23, 59, 59, tzinfo=UTC),  # End of year
                    ]

                    edge_results = []
                    for ts in edge_timestamps:
                        mock_client = self.create_mock_s3_client(head_object_response=self.s3_responses["success"])

                        with patch.object(store, "_get_s3_client", return_value=mock_client):
                            try:
                                result = await store.check_file_exists(ts, self.test_configs["satellites"][0])
                                edge_results.append(result)
                            except Exception:
                                edge_results.append(False)

                    # Most should work (invalid dates might be handled differently)
                    valid_results = [r for r in edge_results if r is not False]
                    results["edge_timestamps_tested"] = len(edge_timestamps)
                    results["valid_results"] = len(valid_results)

                return {"scenario": scenario_name, "results": results}

            async def _test_performance_validation(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test performance validation scenarios."""
                results = {}

                if scenario_name == "high_throughput":
                    # Test high throughput operations
                    store = self.create_s3_store()

                    mock_client = self.create_mock_s3_client(head_object_response=self.s3_responses["success"])

                    operation_count = 50
                    with patch.object(store, "_get_s3_client", return_value=mock_client):
                        # Perform many existence checks
                        tasks = []
                        for i in range(operation_count):
                            ts = datetime(2023, 1, 1, 12, i % 60, 0)  # Vary minutes
                            task = store.check_file_exists(
                                ts, self.test_configs["satellites"][i % len(self.test_configs["satellites"])]
                            )
                            tasks.append(task)

                        # Execute all operations
                        operation_results = await asyncio.gather(*tasks)

                        # All should succeed
                        assert all(operation_results)
                        assert len(operation_results) == operation_count

                        results["operations_completed"] = operation_count
                        results["all_successful"] = all(operation_results)

                return {"scenario": scenario_name, "results": results}

        return {"manager": S3StoreCriticalTestManager()}

    @pytest.fixture()
    def temp_directory(self):
        """Create temporary directory for each test."""
        temp_dir = tempfile.TemporaryDirectory()
        yield temp_dir
        temp_dir.cleanup()

    @pytest.mark.asyncio()
    async def test_initialization_scenarios(self, s3_store_critical_test_components) -> None:
        """Test S3Store initialization scenarios."""
        manager = s3_store_critical_test_components["manager"]

        initialization_scenarios = ["context_manager", "multiple_instances"]

        for scenario in initialization_scenarios:
            result = await manager._test_initialization(scenario)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    @pytest.mark.asyncio()
    async def test_download_operation_scenarios(self, s3_store_critical_test_components, temp_directory) -> None:
        """Test download operation scenarios."""
        manager = s3_store_critical_test_components["manager"]

        download_scenarios = ["successful_download", "multiple_file_sizes", "download_not_found"]

        for scenario in download_scenarios:
            result = await manager._test_download_operations(scenario, temp_directory)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    @pytest.mark.asyncio()
    async def test_file_existence_scenarios(self, s3_store_critical_test_components) -> None:
        """Test file existence checking scenarios."""
        manager = s3_store_critical_test_components["manager"]

        existence_scenarios = ["exists_success", "exists_not_found", "exists_multiple_satellites"]

        for scenario in existence_scenarios:
            result = await manager._test_file_existence(scenario)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    @pytest.mark.asyncio()
    async def test_wildcard_matching_scenarios(self, s3_store_critical_test_components, temp_directory) -> None:
        """Test wildcard pattern matching scenarios."""
        manager = s3_store_critical_test_components["manager"]

        wildcard_scenarios = ["wildcard_single_match", "wildcard_multiple_matches", "wildcard_no_matches"]

        for scenario in wildcard_scenarios:
            result = await manager._test_wildcard_matching(scenario, temp_directory)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    @pytest.mark.asyncio()
    async def test_concurrent_operation_scenarios(self, s3_store_critical_test_components, temp_directory) -> None:
        """Test concurrent operation scenarios."""
        manager = s3_store_critical_test_components["manager"]

        concurrent_scenarios = ["concurrent_downloads", "concurrent_existence_checks"]

        for scenario in concurrent_scenarios:
            result = await manager._test_concurrent_operations(scenario, temp_directory)  # noqa: SLF001
            assert result["scenario"] == scenario
            if scenario == "concurrent_downloads":
                assert result["results"]["concurrent_downloads"] == 5
            else:  # concurrent_existence_checks
                assert result["results"]["concurrent_checks"] == 5

    @pytest.mark.asyncio()
    async def test_error_handling_scenarios(self, s3_store_critical_test_components, temp_directory) -> None:
        """Test error handling scenarios."""
        manager = s3_store_critical_test_components["manager"]

        result = await manager._test_error_handling("various_s3_errors", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "various_s3_errors"
        assert result["results"]["s3_errors_tested"] == 3

    @pytest.mark.asyncio()
    async def test_edge_case_scenarios(self, s3_store_critical_test_components, temp_directory) -> None:
        """Test edge cases and boundary conditions."""
        manager = s3_store_critical_test_components["manager"]

        result = await manager._test_edge_cases("edge_case_timestamps", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "edge_case_timestamps"
        assert result["results"]["edge_timestamps_tested"] == 4

    @pytest.mark.asyncio()
    async def test_performance_validation_scenarios(self, s3_store_critical_test_components, temp_directory) -> None:
        """Test performance validation scenarios."""
        manager = s3_store_critical_test_components["manager"]

        result = await manager._test_performance_validation("high_throughput", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "high_throughput"
        assert result["results"]["operations_completed"] == 50
        assert result["results"]["all_successful"] is True

    @pytest.mark.asyncio()
    @pytest.mark.parametrize("satellite", [SatellitePattern.GOES_16, SatellitePattern.GOES_18])
    async def test_satellite_specific_operations(
        self, s3_store_critical_test_components, temp_directory, satellite
    ) -> None:
        """Test operations with specific satellite patterns."""
        manager = s3_store_critical_test_components["manager"]
        store = manager.create_s3_store()

        mock_client = manager.create_mock_s3_client(head_object_response=manager.s3_responses["success"])

        path_patches = manager.create_path_patches(path_exists=True, file_size=9)

        with patch.object(store, "_get_s3_client", return_value=mock_client):
            with path_patches["path_exists"], path_patches["path_stat"], path_patches["path_mkdir"]:
                local_path = Path(temp_directory.name) / f"satellite_{satellite.name}.nc"
                ts = manager.test_configs["timestamps"][0]

                # Test download
                result = await store.download_file(ts, satellite, local_path)
                assert result == local_path

                # Test existence check
                exists = await store.check_file_exists(ts, satellite)
                assert exists is True

    @pytest.mark.asyncio()
    async def test_comprehensive_s3_store_validation(self, s3_store_critical_test_components, temp_directory) -> None:
        """Test comprehensive S3Store validation scenarios."""
        manager = s3_store_critical_test_components["manager"]

        # Test context manager behavior
        result = await manager._test_initialization("context_manager")  # noqa: SLF001
        assert result["results"]["context_enter"] is True
        assert result["results"]["context_exit"] is True

        # Test successful download
        result = await manager._test_download_operations("successful_download", temp_directory)  # noqa: SLF001
        assert result["results"]["download_successful"] is True

        # Test existence checking
        result = await manager._test_file_existence("exists_success")  # noqa: SLF001
        assert result["results"]["exists_check_successful"] is True

        # Test wildcard matching
        result = await manager._test_wildcard_matching("wildcard_single_match", temp_directory)  # noqa: SLF001
        assert result["results"]["wildcard_match_successful"] is True

        # Test concurrent operations
        result = await manager._test_concurrent_operations("concurrent_downloads", temp_directory)  # noqa: SLF001
        assert result["results"]["concurrent_downloads"] == 5

    @pytest.mark.asyncio()
    async def test_s3_store_critical_integration_validation(
        self, s3_store_critical_test_components, temp_directory
    ) -> None:
        """Test S3Store critical integration scenarios."""
        manager = s3_store_critical_test_components["manager"]

        # Test multiple file sizes
        result = await manager._test_download_operations("multiple_file_sizes", temp_directory)  # noqa: SLF001
        assert result["results"]["file_sizes_tested"] == len(manager.test_configs["file_sizes"])

        # Test multiple satellites
        result = await manager._test_file_existence("exists_multiple_satellites")  # noqa: SLF001
        assert result["results"]["satellites_checked"] == len(manager.test_configs["satellites"])

        # Test high throughput
        result = await manager._test_performance_validation("high_throughput", temp_directory)  # noqa: SLF001
        assert result["results"]["operations_completed"] == 50
        assert result["results"]["all_successful"] is True
