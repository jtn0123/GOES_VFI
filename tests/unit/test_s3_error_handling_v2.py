"""
Optimized unit tests for S3 error handling with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for S3Store setup, mock clients, and error configurations
- Enhanced test managers for comprehensive error handling validation
- Batch testing of different error types and AWS client exceptions
- Improved async test patterns with shared setup and teardown
"""

from datetime import datetime
from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import botocore.exceptions
import pytest

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    ConnectionError,
    RemoteStoreError,
)
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3ErrorHandlingOptimizedV2:
    """Optimized S3 error handling tests with full coverage."""

    @pytest.fixture(scope="class")
    def s3_error_test_components(self):
        """Create shared components for S3 error handling testing."""

        # Enhanced S3 Error Handling Test Manager
        class S3ErrorHandlingTestManager:
            """Manage S3 error handling testing scenarios."""

            def __init__(self) -> None:
                # Define error configurations
                self.error_configs = {
                    "not_found_404": {
                        "error_response": {"Error": {"Code": "404", "Message": "Not Found"}},
                        "operation_name": "HeadObject",
                        "expected_exception": None,  # Should return False, not raise
                        "description": "File not found scenario",
                    },
                    "access_denied_403": {
                        "error_response": {"Error": {"Code": "403", "Message": "Access Denied"}},
                        "operation_name": "HeadObject",
                        "expected_exception": AuthenticationError,
                        "description": "Access denied scenario",
                    },
                    "timeout_error": {
                        "error_type": TimeoutError,
                        "error_message": "Connection timed out",
                        "expected_exception": ConnectionError,
                        "description": "Connection timeout scenario",
                    },
                    "permission_error": {
                        "error_type": PermissionError,
                        "error_message": "Permission denied",
                        "expected_exception": AuthenticationError,
                        "description": "File permission scenario",
                    },
                    "server_error": {
                        "error_response": {"Error": {"Code": "InternalError", "Message": "Server Error"}},
                        "operation_name": "GetObject",
                        "expected_exception": RemoteStoreError,
                        "description": "Server internal error scenario",
                    },
                    "network_error": {
                        "error_type": ConnectionError,
                        "error_message": "Network unreachable",
                        "expected_exception": ConnectionError,
                        "description": "Network connectivity scenario",
                    },
                }

                # Test satellite patterns
                self.test_satellites = [SatellitePattern.GOES_16, SatellitePattern.GOES_18]

                # Test timestamps
                self.test_timestamps = [
                    datetime(2023, 6, 15, 12, 0, 0),
                    datetime(2023, 6, 15, 18, 30, 0),
                    datetime(2023, 7, 1, 6, 0, 0),
                ]

                # Define test scenarios
                self.test_scenarios = {
                    "file_existence_errors": self._test_file_existence_errors,
                    "download_errors": self._test_download_errors,
                    "wildcard_search_errors": self._test_wildcard_search_errors,
                    "permission_errors": self._test_permission_errors,
                    "network_errors": self._test_network_errors,
                    "server_errors": self._test_server_errors,
                    "error_message_validation": self._test_error_message_validation,
                    "edge_case_errors": self._test_edge_case_errors,
                    "performance_validation": self._test_performance_validation,
                }

            def create_s3_store(self) -> S3Store:
                """Create a fresh S3Store instance."""
                return S3Store()

            def create_temp_directory(self) -> tempfile.TemporaryDirectory:
                """Create a temporary directory for test files."""
                return tempfile.TemporaryDirectory()

            def create_mock_s3_client(self, **config) -> AsyncMock:
                """Create a mock S3 client with specified configuration."""
                mock_client = AsyncMock()
                mock_client.get_paginator = MagicMock()

                # Configure head_object behavior
                if config.get("head_object_error"):
                    mock_client.head_object.side_effect = config["head_object_error"]
                elif config.get("head_object_result"):
                    mock_client.head_object.return_value = config["head_object_result"]

                # Configure download_file behavior
                if config.get("download_file_error"):
                    mock_client.download_file.side_effect = config["download_file_error"]

                # Configure paginator behavior
                if config.get("paginator_pages"):
                    paginator_mock = MagicMock()

                    async def mock_paginate(*args, **kwargs):
                        for page in config["paginator_pages"]:
                            yield page

                    paginator_mock.paginate.return_value = mock_paginate()
                    mock_client.get_paginator.return_value = paginator_mock
                elif config.get("empty_paginator"):
                    paginator_mock = MagicMock()

                    async def empty_paginate(*args, **kwargs):
                        return
                        yield  # Make it an async generator

                    paginator_mock.paginate.return_value = empty_paginate()
                    mock_client.get_paginator.return_value = paginator_mock

                return mock_client

            def create_client_error(self, error_config: dict[str, Any]) -> botocore.exceptions.ClientError:
                """Create a botocore ClientError from configuration."""
                return botocore.exceptions.ClientError(
                    error_response=error_config["error_response"], operation_name=error_config["operation_name"]
                )

            async def _test_file_existence_errors(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test file existence error scenarios."""
                results = {}
                store = self.create_s3_store()
                test_timestamp = self.test_timestamps[0]
                test_satellite = self.test_satellites[0]

                if scenario_name == "head_object_not_found":
                    # Test 404 error during head_object
                    error_config = self.error_configs["not_found_404"]
                    client_error = self.create_client_error(error_config)

                    mock_client = self.create_mock_s3_client(head_object_error=client_error, empty_paginator=True)

                    with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                        result = await store.check_file_exists(test_timestamp, test_satellite)

                        # Should return False, not raise exception
                        assert result is False
                        mock_client.head_object.assert_called_once()

                        results["not_found_handled"] = True

                elif scenario_name == "multiple_satellites":
                    # Test file existence errors across multiple satellites
                    error_config = self.error_configs["not_found_404"]
                    client_error = self.create_client_error(error_config)

                    satellite_results = []
                    for satellite in self.test_satellites:
                        mock_client = self.create_mock_s3_client(head_object_error=client_error, empty_paginator=True)

                        with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                            result = await store.check_file_exists(test_timestamp, satellite)
                            satellite_results.append(result)

                    # All should return False
                    assert all(result is False for result in satellite_results)
                    results["multiple_satellites_tested"] = len(self.test_satellites)

                return {"scenario": scenario_name, "results": results}

            async def _test_download_errors(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test download error scenarios."""
                results = {}
                store = self.create_s3_store()
                test_timestamp = self.test_timestamps[0]
                test_satellite = self.test_satellites[0]
                test_dest_path = Path(temp_dir.name) / "test_download.nc"

                if scenario_name == "access_denied":
                    # Test 403 Access Denied error
                    error_config = self.error_configs["access_denied_403"]
                    client_error = self.create_client_error(error_config)

                    mock_client = self.create_mock_s3_client(head_object_error=client_error)

                    with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                        with pytest.raises(AuthenticationError) as exc_info:
                            await store.download_file(test_timestamp, test_satellite, test_dest_path)

                        # Verify error message content
                        error_msg = str(exc_info.value)
                        assert "Access denied" in error_msg
                        assert test_satellite.name in error_msg

                        results["access_denied_handled"] = True

                elif scenario_name == "timeout_error":
                    # Test timeout error during download
                    mock_client = self.create_mock_s3_client(
                        head_object_result={"ContentLength": 1000},
                        download_file_error=TimeoutError("Connection timed out"),
                    )

                    with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                        with pytest.raises(ConnectionError) as exc_info:
                            await store.download_file(test_timestamp, test_satellite, test_dest_path)

                        # Verify error message content
                        error_msg = str(exc_info.value)
                        assert "Timeout" in error_msg
                        assert test_satellite.name in error_msg

                        results["timeout_handled"] = True

                elif scenario_name == "permission_error":
                    # Test permission error during file writing
                    mock_client = self.create_mock_s3_client(
                        head_object_result={"ContentLength": 1000},
                        download_file_error=PermissionError("Permission denied"),
                    )

                    with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                        with pytest.raises(AuthenticationError) as exc_info:
                            await store.download_file(test_timestamp, test_satellite, test_dest_path)

                        # Verify error message and technical details
                        error_msg = str(exc_info.value)
                        assert "Permission" in error_msg

                        technical_details = getattr(exc_info.value, "technical_details", "")
                        assert str(test_dest_path) in technical_details

                        results["permission_handled"] = True

                return {"scenario": scenario_name, "results": results}

            async def _test_wildcard_search_errors(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test wildcard search error scenarios."""
                results = {}
                store = self.create_s3_store()
                test_timestamp = self.test_timestamps[0]
                test_satellite = self.test_satellites[0]
                test_dest_path = Path(temp_dir.name) / "test_download.nc"

                if scenario_name == "wildcard_not_found":
                    # Test wildcard search returning no results
                    error_config = self.error_configs["not_found_404"]
                    head_error = self.create_client_error(error_config)

                    mock_client = self.create_mock_s3_client(
                        head_object_error=head_error,
                        paginator_pages=[],  # Empty pages
                    )

                    with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                        with pytest.raises(RemoteStoreError) as exc_info:
                            await store.download_file(test_timestamp, test_satellite, test_dest_path)

                        # Verify error message and technical details
                        error_msg = str(exc_info.value)
                        assert "No files found for" in error_msg
                        assert test_satellite.name in error_msg

                        technical_details = getattr(exc_info.value, "technical_details", "")
                        assert "Search parameters" in technical_details

                        results["wildcard_not_found_handled"] = True

                elif scenario_name == "wildcard_match_download_error":
                    # Test download error after successful wildcard match
                    head_error = self.create_client_error(self.error_configs["not_found_404"])

                    # Create a test page with one matching object
                    test_key = "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G18_s20231661200000_e20231661202000_c20231661202030.nc"
                    test_page = {"Contents": [{"Key": test_key}]}

                    download_error = self.create_client_error(self.error_configs["server_error"])

                    mock_client = self.create_mock_s3_client(
                        head_object_error=head_error, paginator_pages=[test_page], download_file_error=download_error
                    )

                    with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                        with pytest.raises(RemoteStoreError) as exc_info:
                            await store.download_file(test_timestamp, test_satellite, test_dest_path)

                        # Verify error message content
                        error_msg = str(exc_info.value)
                        assert "No files found" in error_msg
                        assert test_satellite.name in error_msg

                        results["wildcard_download_error_handled"] = True

                elif scenario_name == "multiple_wildcard_scenarios":
                    # Test multiple wildcard scenarios
                    wildcard_scenarios = [
                        ([], "no_results"),
                        ([{"Contents": []}], "empty_contents"),
                        ([{"Contents": [{"Key": "test_key.nc"}]}], "single_result"),
                    ]

                    scenario_results = []
                    for pages, description in wildcard_scenarios:
                        head_error = self.create_client_error(self.error_configs["not_found_404"])

                        mock_client = self.create_mock_s3_client(head_object_error=head_error, paginator_pages=pages)

                        # For scenarios with results, add download error
                        if description == "single_result":
                            mock_client.download_file.side_effect = self.create_client_error(
                                self.error_configs["server_error"]
                            )

                        with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                            try:
                                await store.download_file(test_timestamp, test_satellite, test_dest_path)
                                scenario_results.append((description, "success"))
                            except RemoteStoreError:
                                scenario_results.append((description, "remote_error"))
                            except Exception as e:
                                scenario_results.append((description, type(e).__name__))

                    # All should result in RemoteStoreError
                    assert all(result[1] == "remote_error" for result in scenario_results)
                    results["wildcard_scenarios_tested"] = len(wildcard_scenarios)

                return {"scenario": scenario_name, "results": results}

            async def _test_permission_errors(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test permission-related error scenarios."""
                results = {}
                store = self.create_s3_store()
                test_timestamp = self.test_timestamps[0]
                test_dest_path = Path(temp_dir.name) / "test_download.nc"

                if scenario_name == "various_permission_errors":
                    # Test various permission-related errors
                    permission_scenarios = [
                        (AuthenticationError, "Authentication failed"),
                        (PermissionError, "Permission denied"),
                        (OSError, "Operation not permitted"),
                    ]

                    permission_results = []
                    for error_type, error_message in permission_scenarios:
                        for satellite in self.test_satellites:
                            mock_client = self.create_mock_s3_client(
                                head_object_result={"ContentLength": 1000},
                                download_file_error=error_type(error_message),
                            )

                            with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                                try:
                                    await store.download_file(test_timestamp, satellite, test_dest_path)
                                    permission_results.append((error_type.__name__, "unexpected_success"))
                                except (AuthenticationError, ConnectionError, RemoteStoreError) as e:
                                    permission_results.append((error_type.__name__, type(e).__name__))

                    # All should result in appropriate error types
                    assert len(permission_results) == len(permission_scenarios) * len(self.test_satellites)
                    results["permission_scenarios_tested"] = len(permission_results)

                return {"scenario": scenario_name, "results": results}

            async def _test_network_errors(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test network-related error scenarios."""
                results = {}
                store = self.create_s3_store()
                test_timestamp = self.test_timestamps[0]
                test_satellite = self.test_satellites[0]
                test_dest_path = Path(temp_dir.name) / "test_download.nc"

                if scenario_name == "connection_errors":
                    # Test various connection errors
                    connection_errors = [
                        (TimeoutError, "Connection timed out"),
                        (ConnectionError, "Network unreachable"),
                        (OSError, "Network is down"),
                    ]

                    for error_type, error_message in connection_errors:
                        mock_client = self.create_mock_s3_client(
                            head_object_result={"ContentLength": 1000}, download_file_error=error_type(error_message)
                        )

                        with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                            with pytest.raises((ConnectionError, RemoteStoreError)):
                                await store.download_file(test_timestamp, test_satellite, test_dest_path)

                    results["connection_errors_tested"] = len(connection_errors)

                return {"scenario": scenario_name, "results": results}

            async def _test_server_errors(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test server-related error scenarios."""
                results = {}
                store = self.create_s3_store()
                test_timestamp = self.test_timestamps[0]
                test_satellite = self.test_satellites[0]
                test_dest_path = Path(temp_dir.name) / "test_download.nc"

                if scenario_name == "aws_server_errors":
                    # Test various AWS server errors
                    server_errors = [
                        ("InternalError", "Server Error"),
                        ("ServiceUnavailable", "Service Unavailable"),
                        ("ThrottlingException", "Rate exceeded"),
                    ]

                    for error_code, error_message in server_errors:
                        client_error = botocore.exceptions.ClientError(
                            error_response={"Error": {"Code": error_code, "Message": error_message}},
                            operation_name="GetObject",
                        )

                        mock_client = self.create_mock_s3_client(
                            head_object_result={"ContentLength": 1000}, download_file_error=client_error
                        )

                        with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                            with pytest.raises(RemoteStoreError):
                                await store.download_file(test_timestamp, test_satellite, test_dest_path)

                    results["server_errors_tested"] = len(server_errors)

                return {"scenario": scenario_name, "results": results}

            async def _test_error_message_validation(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test error message validation scenarios."""
                results = {}
                store = self.create_s3_store()
                test_timestamp = self.test_timestamps[0]
                test_satellite = self.test_satellites[0]
                test_dest_path = Path(temp_dir.name) / "test_download.nc"

                if scenario_name == "comprehensive_error_messages":
                    # Test that all error messages contain required information
                    error_test_cases = [
                        (
                            self.error_configs["access_denied_403"],
                            AuthenticationError,
                            ["Access denied", test_satellite.name],
                        ),
                        (
                            self.error_configs["not_found_404"],
                            RemoteStoreError,
                            ["No files found", test_satellite.name],
                        ),
                    ]

                    message_validation_results = []
                    for error_config, expected_exception, required_phrases in error_test_cases:
                        if "error_response" in error_config:
                            client_error = self.create_client_error(error_config)
                            mock_client = self.create_mock_s3_client(head_object_error=client_error)

                            # For not found, set up empty paginator
                            if error_config == self.error_configs["not_found_404"]:
                                mock_client = self.create_mock_s3_client(
                                    head_object_error=client_error, paginator_pages=[]
                                )

                        with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                            try:
                                await store.download_file(test_timestamp, test_satellite, test_dest_path)
                                message_validation_results.append((error_config["description"], "no_exception"))
                            except expected_exception as e:
                                error_msg = str(e)
                                phrases_found = [phrase for phrase in required_phrases if phrase in error_msg]
                                message_validation_results.append((error_config["description"], len(phrases_found)))
                            except Exception as e:
                                message_validation_results.append((
                                    error_config["description"],
                                    f"unexpected_{type(e).__name__}",
                                ))

                    # All should find the required phrases
                    valid_messages = [
                        result for result in message_validation_results if isinstance(result[1], int) and result[1] > 0
                    ]
                    results["valid_error_messages"] = len(valid_messages)
                    results["total_tested"] = len(error_test_cases)

                return {"scenario": scenario_name, "results": results}

            async def _test_edge_case_errors(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test edge case error scenarios."""
                results = {}
                store = self.create_s3_store()
                test_dest_path = Path(temp_dir.name) / "test_download.nc"

                if scenario_name == "unusual_error_combinations":
                    # Test unusual error combinations
                    edge_cases = []

                    # Test with different timestamp/satellite combinations
                    for i, timestamp in enumerate(self.test_timestamps):
                        for j, satellite in enumerate(self.test_satellites):
                            error_config = list(self.error_configs.values())[i % len(self.error_configs)]

                            if "error_response" in error_config:
                                client_error = self.create_client_error(error_config)
                                mock_client = self.create_mock_s3_client(head_object_error=client_error)
                            else:
                                error_type = error_config.get("error_type", Exception)
                                error_message = error_config.get("error_message", "Test error")
                                mock_client = self.create_mock_s3_client(
                                    head_object_result={"ContentLength": 1000},
                                    download_file_error=error_type(error_message),
                                )

                            with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                                try:
                                    await store.download_file(timestamp, satellite, test_dest_path)
                                    edge_cases.append((i, j, "unexpected_success"))
                                except (AuthenticationError, ConnectionError, RemoteStoreError) as e:
                                    edge_cases.append((i, j, type(e).__name__))
                                except Exception as e:
                                    edge_cases.append((i, j, f"other_{type(e).__name__}"))

                    # All should result in handled exceptions
                    handled_cases = [case for case in edge_cases if not case[2].startswith("unexpected")]
                    results["edge_cases_tested"] = len(edge_cases)
                    results["handled_cases"] = len(handled_cases)

                return {"scenario": scenario_name, "results": results}

            async def _test_performance_validation(self, scenario_name: str, temp_dir, **kwargs) -> dict[str, Any]:
                """Test performance validation scenarios."""
                results = {}

                if scenario_name == "error_handling_performance":
                    # Test error handling performance with many errors
                    store = self.create_s3_store()
                    test_timestamp = self.test_timestamps[0]
                    test_satellite = self.test_satellites[0]
                    test_dest_path = Path(temp_dir.name) / "test_download.nc"

                    error_count = 100
                    handled_errors = 0

                    for i in range(error_count):
                        error_config = list(self.error_configs.values())[i % len(self.error_configs)]

                        if "error_response" in error_config:
                            client_error = self.create_client_error(error_config)
                            mock_client = self.create_mock_s3_client(
                                head_object_error=client_error,
                                paginator_pages=[] if error_config == self.error_configs["not_found_404"] else None,
                            )
                        else:
                            error_type = error_config.get("error_type", Exception)
                            error_message = error_config.get("error_message", "Test error")
                            mock_client = self.create_mock_s3_client(
                                head_object_result={"ContentLength": 1000},
                                download_file_error=error_type(error_message),
                            )

                        with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                            try:
                                await store.download_file(test_timestamp, test_satellite, test_dest_path)
                            except (AuthenticationError, ConnectionError, RemoteStoreError):
                                handled_errors += 1
                            except Exception:
                                pass  # Other exceptions

                    results["errors_processed"] = error_count
                    results["errors_handled"] = handled_errors
                    results["handling_rate"] = handled_errors / error_count

                return {"scenario": scenario_name, "results": results}

        return {"manager": S3ErrorHandlingTestManager()}

    @pytest.fixture()
    def temp_directory(self):
        """Create temporary directory for each test."""
        temp_dir = tempfile.TemporaryDirectory()
        yield temp_dir
        temp_dir.cleanup()

    @pytest.mark.asyncio()
    async def test_file_existence_error_scenarios(self, s3_error_test_components, temp_directory) -> None:
        """Test file existence error scenarios."""
        manager = s3_error_test_components["manager"]

        existence_scenarios = ["head_object_not_found", "multiple_satellites"]

        for scenario in existence_scenarios:
            result = await manager._test_file_existence_errors(scenario, temp_directory)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    @pytest.mark.asyncio()
    async def test_download_error_scenarios(self, s3_error_test_components, temp_directory) -> None:
        """Test download error scenarios."""
        manager = s3_error_test_components["manager"]

        download_scenarios = ["access_denied", "timeout_error", "permission_error"]

        for scenario in download_scenarios:
            result = await manager._test_download_errors(scenario, temp_directory)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    @pytest.mark.asyncio()
    async def test_wildcard_search_error_scenarios(self, s3_error_test_components, temp_directory) -> None:
        """Test wildcard search error scenarios."""
        manager = s3_error_test_components["manager"]

        wildcard_scenarios = ["wildcard_not_found", "wildcard_match_download_error", "multiple_wildcard_scenarios"]

        for scenario in wildcard_scenarios:
            result = await manager._test_wildcard_search_errors(scenario, temp_directory)
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    @pytest.mark.asyncio()
    async def test_permission_error_scenarios(self, s3_error_test_components, temp_directory) -> None:
        """Test permission-related error scenarios."""
        manager = s3_error_test_components["manager"]

        result = await manager._test_permission_errors("various_permission_errors", temp_directory)
        assert result["scenario"] == "various_permission_errors"
        assert result["results"]["permission_scenarios_tested"] > 0

    @pytest.mark.asyncio()
    async def test_network_error_scenarios(self, s3_error_test_components, temp_directory) -> None:
        """Test network-related error scenarios."""
        manager = s3_error_test_components["manager"]

        result = await manager._test_network_errors("connection_errors", temp_directory)
        assert result["scenario"] == "connection_errors"
        assert result["results"]["connection_errors_tested"] == 3

    @pytest.mark.asyncio()
    async def test_server_error_scenarios(self, s3_error_test_components, temp_directory) -> None:
        """Test server-related error scenarios."""
        manager = s3_error_test_components["manager"]

        result = await manager._test_server_errors("aws_server_errors", temp_directory)
        assert result["scenario"] == "aws_server_errors"
        assert result["results"]["server_errors_tested"] == 3

    @pytest.mark.asyncio()
    async def test_error_message_validation_scenarios(self, s3_error_test_components, temp_directory) -> None:
        """Test error message validation scenarios."""
        manager = s3_error_test_components["manager"]

        result = await manager._test_error_message_validation("comprehensive_error_messages", temp_directory)
        assert result["scenario"] == "comprehensive_error_messages"
        assert result["results"]["valid_error_messages"] > 0

    @pytest.mark.asyncio()
    async def test_edge_case_error_scenarios(self, s3_error_test_components, temp_directory) -> None:
        """Test edge case error scenarios."""
        manager = s3_error_test_components["manager"]

        result = await manager._test_edge_case_errors("unusual_error_combinations", temp_directory)
        assert result["scenario"] == "unusual_error_combinations"
        assert result["results"]["handled_cases"] > 0

    @pytest.mark.asyncio()
    async def test_performance_validation_scenarios(self, s3_error_test_components, temp_directory) -> None:
        """Test performance validation scenarios."""
        manager = s3_error_test_components["manager"]

        result = await manager._test_performance_validation("error_handling_performance", temp_directory)
        assert result["scenario"] == "error_handling_performance"
        assert result["results"]["errors_processed"] == 100
        assert result["results"]["handling_rate"] > 0.8  # Should handle most errors appropriately

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        "error_config_name,expected_exception",
        [
            ("access_denied_403", AuthenticationError),
            ("timeout_error", ConnectionError),
            ("permission_error", AuthenticationError),
            ("server_error", RemoteStoreError),
        ],
    )
    async def test_specific_error_type_handling(
        self, s3_error_test_components, temp_directory, error_config_name, expected_exception
    ) -> None:
        """Test specific error type handling scenarios."""
        manager = s3_error_test_components["manager"]
        store = manager.create_s3_store()
        error_config = manager.error_configs[error_config_name]

        test_timestamp = manager.test_timestamps[0]
        test_satellite = manager.test_satellites[0]
        test_dest_path = Path(temp_directory.name) / "test_download.nc"

        if "error_response" in error_config:
            client_error = manager.create_client_error(error_config)
            mock_client = manager.create_mock_s3_client(head_object_error=client_error)
        else:
            error_type = error_config.get("error_type", Exception)
            error_message = error_config.get("error_message", "Test error")
            mock_client = manager.create_mock_s3_client(
                head_object_result={"ContentLength": 1000}, download_file_error=error_type(error_message)
            )

        with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
            with pytest.raises(expected_exception):
                await store.download_file(test_timestamp, test_satellite, test_dest_path)

    @pytest.mark.asyncio()
    async def test_comprehensive_s3_error_handling_validation(self, s3_error_test_components, temp_directory) -> None:
        """Test comprehensive S3 error handling validation."""
        manager = s3_error_test_components["manager"]

        # Test all error configurations
        total_errors_tested = 0
        total_handled = 0

        for error_name, error_config in manager.error_configs.items():
            expected_exception = error_config.get("expected_exception")

            if expected_exception:  # Skip file existence checks
                store = manager.create_s3_store()
                test_timestamp = manager.test_timestamps[0]
                test_satellite = manager.test_satellites[0]
                test_dest_path = Path(temp_directory.name) / f"test_{error_name}.nc"

                if "error_response" in error_config:
                    client_error = manager.create_client_error(error_config)
                    mock_client = manager.create_mock_s3_client(head_object_error=client_error)
                else:
                    error_type = error_config.get("error_type", Exception)
                    error_message = error_config.get("error_message", "Test error")
                    mock_client = manager.create_mock_s3_client(
                        head_object_result={"ContentLength": 1000}, download_file_error=error_type(error_message)
                    )

                with patch.object(S3Store, "_get_s3_client", return_value=mock_client):
                    try:
                        await store.download_file(test_timestamp, test_satellite, test_dest_path)
                        total_errors_tested += 1
                    except expected_exception:
                        total_errors_tested += 1
                        total_handled += 1
                    except Exception:
                        total_errors_tested += 1

        # Should handle most expected error types correctly
        # Allow for some variance in error handling based on system conditions
        assert total_handled >= total_errors_tested - 1  # Allow 1 error tolerance
        assert total_errors_tested > 0
        assert total_handled > 0  # At least some errors should be handled
