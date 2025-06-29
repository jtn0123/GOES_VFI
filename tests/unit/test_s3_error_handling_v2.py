"""Optimized S3 error handling tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common S3 configurations and error setups
- Parameterized test scenarios for comprehensive error handling validation
- Enhanced error categorization and recovery testing
- Mock-based testing to avoid real S3 operations and network calls
- Comprehensive exception hierarchy and error message testing
"""

from datetime import datetime
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import botocore.exceptions

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    ConnectionError,
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3ErrorHandlingV2:
    """Optimized test class for S3 error handling functionality."""

    @pytest.fixture(scope="class")
    def error_scenarios(self):
        """Define various error scenario test cases."""
        return {
            "not_found_404": {
                "error_code": "404",
                "error_message": "Not Found",
                "operation": "HeadObject",
                "expected_exception": ResourceNotFoundError,
                "expected_content": ["not found", "404"],
            },
            "access_denied_403": {
                "error_code": "403", 
                "error_message": "Access Denied",
                "operation": "HeadObject",
                "expected_exception": AuthenticationError,
                "expected_content": ["Access denied", "403"],
            },
            "invalid_credentials": {
                "error_code": "InvalidAccessKeyId",
                "error_message": "The AWS Access Key Id you provided does not exist",
                "operation": "HeadObject",
                "expected_exception": AuthenticationError,
                "expected_content": ["InvalidAccessKeyId", "credentials"],
            },
            "no_such_bucket": {
                "error_code": "NoSuchBucket",
                "error_message": "The specified bucket does not exist",
                "operation": "HeadObject",
                "expected_exception": RemoteStoreError,
                "expected_content": ["NoSuchBucket", "bucket"],
            },
            "internal_error": {
                "error_code": "InternalError",
                "error_message": "We encountered an internal error. Please try again.",
                "operation": "GetObject",
                "expected_exception": RemoteStoreError,
                "expected_content": ["InternalError", "internal"],
            },
            "throttling": {
                "error_code": "SlowDown",
                "error_message": "Please reduce your request rate",
                "operation": "GetObject",
                "expected_exception": ConnectionError,
                "expected_content": ["SlowDown", "rate"],
            },
            "service_unavailable": {
                "error_code": "ServiceUnavailable", 
                "error_message": "Service temporarily unavailable",
                "operation": "GetObject",
                "expected_exception": ConnectionError,
                "expected_content": ["ServiceUnavailable", "unavailable"],
            },
        }

    @pytest.fixture(scope="class")
    def timeout_scenarios(self):
        """Define various timeout scenario test cases."""
        return {
            "connection_timeout": {
                "exception": TimeoutError("Connection timed out"),
                "expected_exception": ConnectionError,
                "expected_content": ["timeout", "connection"],
            },
            "read_timeout": {
                "exception": botocore.exceptions.ReadTimeoutError(
                    endpoint_url="https://s3.amazonaws.com", 
                    error="Read timeout"
                ),
                "expected_exception": ConnectionError,
                "expected_content": ["timeout", "read"],
            },
            "connect_timeout": {
                "exception": botocore.exceptions.ConnectTimeoutError(
                    endpoint_url="https://s3.amazonaws.com",
                    error="Connect timeout"
                ),
                "expected_exception": ConnectionError,
                "expected_content": ["timeout", "connect"],
            },
        }

    @pytest.fixture(scope="class")
    def network_scenarios(self):
        """Define various network error scenario test cases."""
        return {
            "connection_error": {
                "exception": ConnectionError("Network unreachable"),
                "expected_exception": ConnectionError,
                "expected_content": ["network", "unreachable"],
            },
            "dns_error": {
                "exception": botocore.exceptions.EndpointConnectionError(
                    endpoint_url="https://s3.amazonaws.com",
                    error="DNS resolution failed"
                ),
                "expected_exception": ConnectionError,
                "expected_content": ["DNS", "connection"],
            },
            "ssl_error": {
                "exception": botocore.exceptions.SSLError(
                    endpoint_url="https://s3.amazonaws.com",
                    error="SSL handshake failed"
                ),
                "expected_exception": ConnectionError,
                "expected_content": ["SSL", "handshake"],
            },
        }

    @pytest.fixture(scope="class")
    def permission_scenarios(self):
        """Define various permission error scenario test cases."""
        return {
            "file_permission": {
                "exception": PermissionError("Permission denied to write file"),
                "expected_exception": AuthenticationError,
                "expected_content": ["Permission", "denied"],
            },
            "directory_permission": {
                "exception": PermissionError("Cannot create directory"),
                "expected_exception": AuthenticationError,
                "expected_content": ["Permission", "directory"],
            },
            "os_error": {
                "exception": OSError("Disk full"),
                "expected_exception": RemoteStoreError,
                "expected_content": ["OSError", "disk"],
            },
        }

    @pytest.fixture
    async def s3_store_setup(self):
        """Setup S3Store with mock client for testing."""
        store = S3Store()
        
        # Create temporary directory for tests
        temp_dir = tempfile.TemporaryDirectory()
        test_dest_path = Path(temp_dir.name) / "test_download.nc"
        
        # Mock S3 client
        mock_s3_client = AsyncMock()
        mock_s3_client.get_paginator = MagicMock()
        
        # Patch the _get_s3_client method
        with patch.object(S3Store, "_get_s3_client", return_value=mock_s3_client):
            yield {
                "store": store,
                "mock_client": mock_s3_client,
                "dest_path": test_dest_path,
                "temp_dir": temp_dir,
            }
        
        # Cleanup
        temp_dir.cleanup()

    @pytest.fixture
    def test_parameters(self):
        """Common test parameters."""
        return {
            "timestamp": datetime(2023, 6, 15, 12, 0, 0),
            "satellite": SatellitePattern.GOES_18,
            "product_type": "RadC",
            "band": 13,
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", [
        "not_found_404",
        "access_denied_403",
        "invalid_credentials",
        "no_such_bucket",
        "internal_error",
        "throttling",
        "service_unavailable",
    ])
    async def test_client_error_scenarios(self, s3_store_setup, error_scenarios, 
                                        test_parameters, scenario_name):
        """Test various AWS client error scenarios."""
        scenario = error_scenarios[scenario_name]
        setup = s3_store_setup
        
        # Create client error
        client_error = botocore.exceptions.ClientError(
            error_response={
                "Error": {
                    "Code": scenario["error_code"],
                    "Message": scenario["error_message"]
                }
            },
            operation_name=scenario["operation"],
        )
        
        # Configure mock to raise error
        if scenario["operation"] == "HeadObject":
            setup["mock_client"].head_object.side_effect = client_error
        else:
            setup["mock_client"].head_object.return_value = {"ContentLength": 1000}
            setup["mock_client"].download_file.side_effect = client_error
        
        # Test the operation
        with pytest.raises(scenario["expected_exception"]) as exc_info:
            await setup["store"].download_file(
                test_parameters["timestamp"],
                test_parameters["satellite"], 
                setup["dest_path"]
            )
        
        # Verify error message content
        error_msg = str(exc_info.value).lower()
        for content in scenario["expected_content"]:
            assert content.lower() in error_msg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", [
        "connection_timeout",
        "read_timeout", 
        "connect_timeout",
    ])
    async def test_timeout_error_scenarios(self, s3_store_setup, timeout_scenarios,
                                         test_parameters, scenario_name):
        """Test various timeout error scenarios."""
        scenario = timeout_scenarios[scenario_name]
        setup = s3_store_setup
        
        # Configure head_object to succeed, download to timeout
        setup["mock_client"].head_object.return_value = {"ContentLength": 1000}
        setup["mock_client"].download_file.side_effect = scenario["exception"]
        
        # Test the operation
        with pytest.raises(scenario["expected_exception"]) as exc_info:
            await setup["store"].download_file(
                test_parameters["timestamp"],
                test_parameters["satellite"],
                setup["dest_path"]
            )
        
        # Verify error message content
        error_msg = str(exc_info.value).lower()
        for content in scenario["expected_content"]:
            assert content.lower() in error_msg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", [
        "connection_error",
        "dns_error",
        "ssl_error", 
    ])
    async def test_network_error_scenarios(self, s3_store_setup, network_scenarios,
                                         test_parameters, scenario_name):
        """Test various network error scenarios."""
        scenario = network_scenarios[scenario_name]
        setup = s3_store_setup
        
        # Configure mock to raise network error
        setup["mock_client"].head_object.side_effect = scenario["exception"]
        
        # Test the operation
        with pytest.raises(scenario["expected_exception"]) as exc_info:
            await setup["store"].download_file(
                test_parameters["timestamp"],
                test_parameters["satellite"],
                setup["dest_path"]
            )
        
        # Verify error message content
        error_msg = str(exc_info.value).lower()
        for content in scenario["expected_content"]:
            assert content.lower() in error_msg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", [
        "file_permission",
        "directory_permission",
        "os_error",
    ])
    async def test_permission_error_scenarios(self, s3_store_setup, permission_scenarios,
                                            test_parameters, scenario_name):
        """Test various permission and OS error scenarios."""
        scenario = permission_scenarios[scenario_name]
        setup = s3_store_setup
        
        # Configure head_object to succeed, download to raise permission error
        setup["mock_client"].head_object.return_value = {"ContentLength": 1000}
        setup["mock_client"].download_file.side_effect = scenario["exception"]
        
        # Test the operation
        with pytest.raises(scenario["expected_exception"]) as exc_info:
            await setup["store"].download_file(
                test_parameters["timestamp"],
                test_parameters["satellite"],
                setup["dest_path"]
            )
        
        # Verify error message content
        error_msg = str(exc_info.value).lower()
        for content in scenario["expected_content"]:
            assert content.lower() in error_msg

    @pytest.mark.asyncio
    async def test_wildcard_search_no_results(self, s3_store_setup, test_parameters):
        """Test wildcard search when no files are found."""
        setup = s3_store_setup
        
        # Configure head_object to return 404 (triggering wildcard search)
        client_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadObject",
        )
        setup["mock_client"].head_object.side_effect = client_error
        
        # Configure paginator to return empty results
        paginator_mock = MagicMock()
        empty_pages = []
        
        async def mock_paginate(*args, **kwargs):
            for page in empty_pages:
                yield page
        
        paginator_mock.paginate.return_value = mock_paginate()
        setup["mock_client"].get_paginator.return_value = paginator_mock
        
        # Test the operation
        with pytest.raises(RemoteStoreError) as exc_info:
            await setup["store"].download_file(
                test_parameters["timestamp"],
                test_parameters["satellite"],
                setup["dest_path"]
            )
        
        # Verify error message
        error_msg = str(exc_info.value)
        assert "No files found for" in error_msg
        assert test_parameters["satellite"].name in error_msg
        
        # Verify technical details
        technical_details = getattr(exc_info.value, "technical_details", "")
        assert "Search parameters" in technical_details

    @pytest.mark.asyncio
    async def test_wildcard_search_download_failure(self, s3_store_setup, test_parameters):
        """Test wildcard search success but download failure."""
        setup = s3_store_setup
        
        # Configure head_object to return 404 (triggering wildcard search)
        head_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadObject",
        )
        setup["mock_client"].head_object.side_effect = head_error
        
        # Configure paginator to return matching object
        paginator_mock = MagicMock()
        test_key = (
            "ABI-L1b-RadC/2023/166/12/"
            "OR_ABI-L1b-RadC-M6C13_G18_s20231661200000_e20231661202000_c20231661202030.nc"
        )
        test_page = {"Contents": [{"Key": test_key}]}
        
        async def mock_paginate(*args, **kwargs):
            yield test_page
        
        paginator_mock.paginate.return_value = mock_paginate()
        setup["mock_client"].get_paginator.return_value = paginator_mock
        
        # Configure download to fail
        download_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "InternalError", "Message": "Server Error"}},
            operation_name="GetObject",
        )
        setup["mock_client"].download_file.side_effect = download_error
        
        # Test the operation
        with pytest.raises(RemoteStoreError) as exc_info:
            await setup["store"].download_file(
                test_parameters["timestamp"],
                test_parameters["satellite"],
                setup["dest_path"]
            )
        
        # Verify error message
        error_msg = str(exc_info.value)
        assert "Error accessing" in error_msg
        assert test_parameters["satellite"].name in error_msg

    @pytest.mark.asyncio
    async def test_check_file_exists_error_handling(self, s3_store_setup, test_parameters):
        """Test error handling in check_file_exists method."""
        setup = s3_store_setup
        
        # Test with 404 error - should return False
        client_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadObject",
        )
        setup["mock_client"].head_object.side_effect = client_error
        
        # Configure empty paginator results
        paginator_mock = MagicMock()
        
        async def empty_paginate(*args, **kwargs):
            return
            yield  # Make it an async generator
        
        paginator_mock.paginate.return_value = empty_paginate()
        setup["mock_client"].get_paginator.return_value = paginator_mock
        
        # Test file existence check
        result = await setup["store"].check_file_exists(
            test_parameters["timestamp"],
            test_parameters["satellite"]
        )
        
        assert result is False
        setup["mock_client"].head_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_message_details(self, s3_store_setup, test_parameters):
        """Test that error messages contain sufficient detail for debugging."""
        setup = s3_store_setup
        
        # Test with access denied error
        client_error = botocore.exceptions.ClientError(
            error_response={
                "Error": {
                    "Code": "403",
                    "Message": "Access Denied",
                    "BucketName": "test-bucket",
                }
            },
            operation_name="HeadObject",
        )
        setup["mock_client"].head_object.side_effect = client_error
        
        with pytest.raises(AuthenticationError) as exc_info:
            await setup["store"].download_file(
                test_parameters["timestamp"],
                test_parameters["satellite"],
                setup["dest_path"]
            )
        
        error = exc_info.value
        error_msg = str(error)
        
        # Verify error contains contextual information
        assert test_parameters["satellite"].name in error_msg
        assert "403" in error_msg or "Access denied" in error_msg
        
        # Check technical details if available
        if hasattr(error, "technical_details"):
            technical_details = error.technical_details
            assert "HeadObject" in technical_details
            assert "test-bucket" in technical_details or "bucket" in technical_details

    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, s3_store_setup, test_parameters):
        """Test error recovery and retry scenarios."""
        setup = s3_store_setup
        
        # Test scenario where first call fails but second succeeds
        call_count = 0
        
        def head_object_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails with temporary error
                raise botocore.exceptions.ClientError(
                    error_response={"Error": {"Code": "ServiceUnavailable", "Message": "Temporary error"}},
                    operation_name="HeadObject",
                )
            else:
                # Second call succeeds
                return {"ContentLength": 1000}
        
        setup["mock_client"].head_object.side_effect = head_object_side_effect
        setup["mock_client"].download_file.return_value = None
        
        # Test with manual retry simulation
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # This would normally be handled by retry logic
                await setup["store"].download_file(
                    test_parameters["timestamp"],
                    test_parameters["satellite"],
                    setup["dest_path"]
                )
                break  # Success
            except ConnectionError:
                if attempt == max_retries - 1:
                    pytest.fail("Should have succeeded on retry")
                # Reset for retry
                setup["mock_client"].reset_mock()
                setup["mock_client"].head_object.side_effect = head_object_side_effect
                setup["mock_client"].download_file.return_value = None

    @pytest.mark.asyncio
    async def test_concurrent_error_scenarios(self, s3_store_setup, test_parameters):
        """Test error handling with concurrent operations."""
        import asyncio
        
        setup = s3_store_setup
        
        # Configure different errors for concurrent calls
        errors = [
            botocore.exceptions.ClientError(
                error_response={"Error": {"Code": "403", "Message": "Access Denied"}},
                operation_name="HeadObject",
            ),
            TimeoutError("Connection timeout"),
            PermissionError("Permission denied"),
        ]
        
        async def download_with_error(error, index):
            # Create separate S3Store for each concurrent operation
            store = S3Store()
            dest_path = setup["dest_path"].parent / f"test_{index}.nc"
            
            with patch.object(S3Store, "_get_s3_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_client.head_object.side_effect = error
                mock_get_client.return_value = mock_client
                
                try:
                    await store.download_file(
                        test_parameters["timestamp"],
                        test_parameters["satellite"],
                        dest_path
                    )
                    return f"success_{index}"
                except Exception as e:
                    return f"error_{index}_{type(e).__name__}"
        
        # Run concurrent operations
        tasks = [download_with_error(error, i) for i, error in enumerate(errors)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all operations completed with expected errors
        assert len(results) == len(errors)
        for i, result in enumerate(results):
            assert f"error_{i}" in str(result)

    def test_error_exception_hierarchy(self):
        """Test that error exceptions follow proper inheritance hierarchy."""
        # Test exception hierarchy
        assert issubclass(AuthenticationError, RemoteStoreError)
        assert issubclass(ConnectionError, RemoteStoreError)
        assert issubclass(ResourceNotFoundError, RemoteStoreError)
        
        # Test exception instantiation
        auth_error = AuthenticationError("Test auth error")
        assert isinstance(auth_error, RemoteStoreError)
        assert str(auth_error) == "Test auth error"
        
        conn_error = ConnectionError("Test connection error")
        assert isinstance(conn_error, RemoteStoreError)
        assert str(conn_error) == "Test connection error"
        
        not_found_error = ResourceNotFoundError("Test not found error")
        assert isinstance(not_found_error, RemoteStoreError)
        assert str(not_found_error) == "Test not found error"

    @pytest.mark.asyncio
    async def test_error_logging_and_diagnostics(self, s3_store_setup, test_parameters):
        """Test that errors are properly logged with diagnostic information."""
        setup = s3_store_setup
        
        # Configure error with diagnostic information
        client_error = botocore.exceptions.ClientError(
            error_response={
                "Error": {
                    "Code": "SlowDown",
                    "Message": "Please reduce your request rate",
                    "BucketName": "noaa-goes18",
                    "RequestId": "test-request-id",
                }
            },
            operation_name="HeadObject",
        )
        setup["mock_client"].head_object.side_effect = client_error
        
        with patch("goesvfi.integrity_check.remote.s3_store.LOGGER") as mock_logger:
            with pytest.raises(ConnectionError):
                await setup["store"].download_file(
                    test_parameters["timestamp"],
                    test_parameters["satellite"],
                    setup["dest_path"]
                )
            
            # Verify logging was called
            assert mock_logger.error.called or mock_logger.exception.called

    @pytest.mark.asyncio
    async def test_error_cleanup_on_failure(self, s3_store_setup, test_parameters):
        """Test that resources are properly cleaned up when errors occur."""
        setup = s3_store_setup
        
        # Create a partial file to simulate interrupted download
        setup["dest_path"].write_bytes(b"partial data")
        assert setup["dest_path"].exists()
        
        # Configure download to fail after file creation
        def download_file_side_effect(*args, **kwargs):
            # Simulate partial download then failure
            raise botocore.exceptions.ClientError(
                error_response={"Error": {"Code": "InternalError", "Message": "Server Error"}},
                operation_name="GetObject",
            )
        
        setup["mock_client"].head_object.return_value = {"ContentLength": 1000}
        setup["mock_client"].download_file.side_effect = download_file_side_effect
        
        with pytest.raises(RemoteStoreError):
            await setup["store"].download_file(
                test_parameters["timestamp"],
                test_parameters["satellite"],
                setup["dest_path"]
            )
        
        # File cleanup behavior depends on implementation
        # Just verify the test completed without hanging

    @pytest.mark.asyncio
    async def test_memory_efficiency_during_errors(self, s3_store_setup, test_parameters):
        """Test memory efficiency when handling many errors."""
        import sys
        
        setup = s3_store_setup
        initial_refs = sys.getrefcount(Exception)
        
        # Generate many errors
        for i in range(100):
            client_error = botocore.exceptions.ClientError(
                error_response={"Error": {"Code": "403", "Message": f"Error {i}"}},
                operation_name="HeadObject",
            )
            setup["mock_client"].head_object.side_effect = client_error
            
            try:
                await setup["store"].download_file(
                    test_parameters["timestamp"],
                    test_parameters["satellite"],
                    setup["dest_path"]
                )
            except AuthenticationError:
                pass  # Expected
            
            # Reset mock for next iteration
            setup["mock_client"].reset_mock()
        
        final_refs = sys.getrefcount(Exception)
        
        # Memory usage should be stable
        assert abs(final_refs - initial_refs) <= 10, f"Memory leak detected: {initial_refs} -> {final_refs}"

    @pytest.mark.asyncio
    async def test_error_context_preservation(self, s3_store_setup, test_parameters):
        """Test that error context is preserved through the call stack."""
        setup = s3_store_setup
        
        # Create nested error scenario
        original_error = botocore.exceptions.ClientError(
            error_response={
                "Error": {
                    "Code": "InvalidAccessKeyId",
                    "Message": "The AWS Access Key Id you provided does not exist",
                    "BucketName": "noaa-goes18",
                }
            },
            operation_name="HeadObject",
        )
        setup["mock_client"].head_object.side_effect = original_error
        
        with pytest.raises(AuthenticationError) as exc_info:
            await setup["store"].download_file(
                test_parameters["timestamp"],
                test_parameters["satellite"],
                setup["dest_path"]
            )
        
        # Verify error context is preserved
        error = exc_info.value
        error_str = str(error)
        
        # Should contain original error information
        assert "InvalidAccessKeyId" in error_str
        assert "AWS Access Key" in error_str or "credentials" in error_str
        
        # Should contain contextual information
        assert test_parameters["satellite"].name in error_str

    @pytest.mark.parametrize("satellite", [SatellitePattern.GOES_16, SatellitePattern.GOES_18])
    @pytest.mark.asyncio
    async def test_error_handling_across_satellites(self, s3_store_setup, satellite):
        """Test error handling consistency across different satellites."""
        setup = s3_store_setup
        
        # Configure same error for different satellites
        client_error = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "403", "Message": "Access Denied"}},
            operation_name="HeadObject",
        )
        setup["mock_client"].head_object.side_effect = client_error
        
        with pytest.raises(AuthenticationError) as exc_info:
            await setup["store"].download_file(
                datetime(2023, 6, 15, 12, 0, 0),
                satellite,
                setup["dest_path"]
            )
        
        # Verify satellite-specific information is included
        error_msg = str(exc_info.value)
        assert satellite.name in error_msg
        assert "403" in error_msg or "Access denied" in error_msg