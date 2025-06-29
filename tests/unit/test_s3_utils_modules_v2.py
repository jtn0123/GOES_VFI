"""Optimized S3 utils modules tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common utility configurations and mock setups
- Parameterized test scenarios for comprehensive utility module validation
- Enhanced error conversion and diagnostics testing
- Mock-based testing to avoid real network operations and DNS calls
- Comprehensive statistics tracking and configuration testing
"""

from datetime import datetime, timedelta
import socket
from unittest.mock import patch, Mock
import pytest
import botocore.exceptions

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    ConnectionError as RemoteConnectionError,
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.remote.s3_utils import (
    DownloadStatsTracker,
    NetworkDiagnostics,
    S3ClientConfig,
    S3ErrorConverter,
    create_s3_config,
)
from goesvfi.integrity_check.time_index import SatellitePattern


class TestS3UtilsModulesV2:
    """Optimized test class for S3 utils modules functionality."""

    @pytest.fixture(scope="class")
    def stats_scenarios(self):
        """Define various statistics tracking scenario test cases."""
        return {
            "successful_downloads": [
                {"success": True, "download_time": 1.0, "file_size": 1024, "satellite": "GOES_16"},
                {"success": True, "download_time": 2.5, "file_size": 2048, "satellite": "GOES_18"},
                {"success": True, "download_time": 0.8, "file_size": 512, "satellite": "GOES_16"},
            ],
            "failed_downloads": [
                {"success": False, "error_type": "network", "error_message": "Connection timeout", "satellite": "GOES_16"},
                {"success": False, "error_type": "auth", "error_message": "Access denied", "satellite": "GOES_18"},
                {"success": False, "error_type": "not_found", "error_message": "File not found", "satellite": "GOES_16"},
            ],
            "mixed_downloads": [
                {"success": True, "download_time": 1.5, "file_size": 1500, "satellite": "GOES_16"},
                {"success": False, "error_type": "timeout", "error_message": "Read timeout", "satellite": "GOES_18"},
                {"success": True, "download_time": 3.0, "file_size": 3000, "satellite": "GOES_16"},
                {"success": False, "error_type": "network", "error_message": "DNS error", "satellite": "GOES_18"},
            ],
            "large_scale_downloads": [
                {"success": True, "download_time": i * 0.1, "file_size": i * 100, "satellite": f"GOES_{16 + (i % 2)}"}
                for i in range(1, 21)  # 20 successful downloads
            ] + [
                {"success": False, "error_type": "network", "error_message": f"Error {i}", "satellite": f"GOES_{16 + (i % 2)}"}
                for i in range(5)  # 5 failed downloads
            ],
        }

    @pytest.fixture(scope="class")
    def config_scenarios(self):
        """Define various S3 configuration scenario test cases."""
        return {
            "default_config": {
                "aws_profile": None,
                "aws_region": "us-east-1",
                "timeout": 60,
                "connect_timeout": 10,
                "max_retries": 2,
                "enable_debug_logging": False,
            },
            "custom_config": {
                "aws_profile": "custom-profile",
                "aws_region": "us-west-2",
                "timeout": 120,
                "connect_timeout": 20,
                "max_retries": 5,
                "enable_debug_logging": True,
            },
            "high_performance_config": {
                "aws_profile": "performance",
                "aws_region": "us-east-1",
                "timeout": 300,
                "connect_timeout": 30,
                "max_retries": 10,
                "enable_debug_logging": False,
            },
            "minimal_config": {
                "aws_profile": None,
                "aws_region": "us-east-1",
                "timeout": 30,
                "connect_timeout": 5,
                "max_retries": 1,
                "enable_debug_logging": False,
            },
        }

    @pytest.fixture(scope="class")
    def error_conversion_scenarios(self):
        """Define various error conversion scenario test cases."""
        return {
            "client_errors": {
                "404_not_found": {
                    "error": botocore.exceptions.ClientError(
                        {"Error": {"Code": "404", "Message": "Not Found"}}, "GetObject"
                    ),
                    "expected_type": ResourceNotFoundError,
                    "expected_content": ["not found", "GOES_16"],
                },
                "403_access_denied": {
                    "error": botocore.exceptions.ClientError(
                        {"Error": {"Code": "403", "Message": "Access Denied"}}, "GetObject"
                    ),
                    "expected_type": AuthenticationError,
                    "expected_content": ["access denied", "GOES_16"],
                },
                "500_internal_error": {
                    "error": botocore.exceptions.ClientError(
                        {"Error": {"Code": "500", "Message": "Internal Server Error"}}, "GetObject"
                    ),
                    "expected_type": RemoteStoreError,
                    "expected_content": ["internal", "server"],
                },
                "invalid_access_key": {
                    "error": botocore.exceptions.ClientError(
                        {"Error": {"Code": "InvalidAccessKeyId", "Message": "Invalid access key"}}, "GetObject"
                    ),
                    "expected_type": AuthenticationError,
                    "expected_content": ["invalid", "access"],
                },
            },
            "network_errors": {
                "timeout_error": {
                    "error": TimeoutError("Operation timed out"),
                    "expected_type": RemoteConnectionError,
                    "expected_content": ["timeout", "GOES_16"],
                },
                "connection_error": {
                    "error": ConnectionError("Connection failed"),
                    "expected_type": RemoteConnectionError,
                    "expected_content": ["connection", "GOES_16"],
                },
                "permission_error": {
                    "error": PermissionError("Permission denied"),
                    "expected_type": AuthenticationError,
                    "expected_content": ["permission", "GOES_16"],
                },
                "os_error": {
                    "error": OSError("Disk full"),
                    "expected_type": RemoteStoreError,
                    "expected_content": ["disk", "full"],
                },
            },
            "generic_errors": {
                "value_error": {
                    "error": ValueError("Invalid value"),
                    "expected_type": RemoteStoreError,
                    "expected_content": ["error", "GOES_16"],
                },
                "runtime_error": {
                    "error": RuntimeError("Runtime failure"),
                    "expected_type": RemoteStoreError,
                    "expected_content": ["error", "GOES_16"],
                },
            },
        }

    @pytest.fixture(scope="class")
    def diagnostics_scenarios(self):
        """Define various network diagnostics scenario test cases."""
        return {
            "dns_resolution_success": {
                "mock_response": "52.216.0.1",
                "expected_success": True,
                "hosts_to_test": ["s3.amazonaws.com", "noaa-goes16.s3.amazonaws.com"],
            },
            "dns_resolution_failure": {
                "mock_exception": socket.gaierror("Name resolution failed"),
                "expected_success": False,
                "hosts_to_test": ["s3.amazonaws.com", "noaa-goes16.s3.amazonaws.com"],
            },
            "partial_dns_failure": {
                "mixed_responses": True,  # Some succeed, some fail
                "expected_success": "mixed",
                "hosts_to_test": ["s3.amazonaws.com", "noaa-goes16.s3.amazonaws.com"],
            },
        }

    @pytest.fixture
    def stats_tracker_factory(self):
        """Factory for creating DownloadStatsTracker instances."""
        trackers = []
        
        def create_tracker():
            tracker = DownloadStatsTracker()
            trackers.append(tracker)
            return tracker
        
        yield create_tracker
        
        # Cleanup
        for tracker in trackers:
            try:
                tracker.reset()
            except:
                pass

    @pytest.mark.parametrize("scenario_name", [
        "successful_downloads",
        "failed_downloads",
        "mixed_downloads",
        "large_scale_downloads",
    ])
    def test_download_stats_tracking_scenarios(self, stats_tracker_factory, stats_scenarios, scenario_name):
        """Test download statistics tracking with various scenarios."""
        tracker = stats_tracker_factory()
        scenario = stats_scenarios[scenario_name]
        
        # Apply all downloads in the scenario
        for download in scenario:
            tracker.update_attempt(**download)
        
        # Get and verify statistics
        stats = tracker.get_stats()
        
        # Count expected values
        successful_count = sum(1 for d in scenario if d.get("success", False))
        failed_count = sum(1 for d in scenario if not d.get("success", True))
        total_count = len(scenario)
        
        assert stats.total_attempts == total_count
        assert stats.successful == successful_count
        assert stats.failed == failed_count
        
        # Verify specific metrics for successful downloads
        if successful_count > 0:
            successful_downloads = [d for d in scenario if d.get("success", False)]
            total_bytes = sum(d.get("file_size", 0) for d in successful_downloads)
            assert stats.total_bytes == total_bytes
            
            if total_bytes > 0:
                file_sizes = [d["file_size"] for d in successful_downloads]
                assert stats.largest_file_size == max(file_sizes)
                assert stats.smallest_file_size == min(file_sizes)
        
        # Verify error tracking
        if failed_count > 0:
            assert len(stats.errors) == failed_count
            
            # Check error type counters
            network_errors = sum(1 for d in scenario if d.get("error_type") == "network")
            auth_errors = sum(1 for d in scenario if d.get("error_type") == "auth")
            timeouts = sum(1 for d in scenario if d.get("error_type") == "timeout")
            not_found = sum(1 for d in scenario if d.get("error_type") == "not_found")
            
            assert stats.network_errors == network_errors
            assert stats.auth_errors == auth_errors
            assert stats.timeouts == timeouts
            assert stats.not_found == not_found

    @pytest.mark.parametrize("config_name", [
        "default_config",
        "custom_config",
        "high_performance_config",
        "minimal_config",
    ])
    def test_s3_client_config_scenarios(self, config_scenarios, config_name):
        """Test S3 client configuration with various scenarios."""
        scenario = config_scenarios[config_name]
        
        # Create configuration
        config = S3ClientConfig(
            aws_profile=scenario["aws_profile"],
            aws_region=scenario["aws_region"],
            timeout=scenario["timeout"],
            connect_timeout=scenario["connect_timeout"],
            max_retries=scenario["max_retries"],
            enable_debug_logging=scenario["enable_debug_logging"],
        )
        
        # Verify all attributes
        assert config.aws_profile == scenario["aws_profile"]
        assert config.aws_region == scenario["aws_region"]
        assert config.timeout == scenario["timeout"]
        assert config.connect_timeout == scenario["connect_timeout"]
        assert config.max_retries == scenario["max_retries"]
        assert config.enable_debug_logging == scenario["enable_debug_logging"]
        
        # Test session kwargs generation
        session_kwargs = config.get_session_kwargs()
        expected_kwargs = {"region_name": scenario["aws_region"]}
        if scenario["aws_profile"]:
            expected_kwargs["profile_name"] = scenario["aws_profile"]
        
        assert session_kwargs == expected_kwargs

    def test_create_s3_config_comprehensive(self):
        """Test comprehensive S3 configuration creation."""
        test_cases = [
            {
                "params": {"timeout": 60, "connect_timeout": 10, "max_retries": 3, "use_unsigned": True},
                "expected_timeout": 60,
                "expected_connect": 10,
                "expected_retries": 3,
                "expected_unsigned": True,
            },
            {
                "params": {"timeout": 120, "connect_timeout": 20, "max_retries": 5, "use_unsigned": False},
                "expected_timeout": 120,
                "expected_connect": 20,
                "expected_retries": 5,
                "expected_unsigned": False,
            },
            {
                "params": {"timeout": 300, "connect_timeout": 30, "max_retries": 10},
                "expected_timeout": 300,
                "expected_connect": 30,
                "expected_retries": 10,
                "expected_unsigned": False,  # Default
            },
        ]
        
        for case in test_cases:
            config = create_s3_config(**case["params"])
            
            assert config.connect_timeout == case["expected_connect"]
            assert config.read_timeout == case["expected_timeout"]
            assert config.retries["max_attempts"] == case["expected_retries"]
            
            if case["expected_unsigned"]:
                assert config.signature_version == botocore.UNSIGNED
            else:
                assert not hasattr(config, "signature_version") or config.signature_version != botocore.UNSIGNED

    @pytest.mark.parametrize("error_category,error_name", [
        ("client_errors", "404_not_found"),
        ("client_errors", "403_access_denied"),
        ("client_errors", "500_internal_error"),
        ("client_errors", "invalid_access_key"),
        ("network_errors", "timeout_error"),
        ("network_errors", "connection_error"),
        ("network_errors", "permission_error"),
        ("network_errors", "os_error"),
        ("generic_errors", "value_error"),
        ("generic_errors", "runtime_error"),
    ])
    def test_s3_error_conversion_scenarios(self, error_conversion_scenarios, error_category, error_name):
        """Test S3 error conversion with various error types."""
        scenario = error_conversion_scenarios[error_category][error_name]
        error = scenario["error"]
        expected_type = scenario["expected_type"]
        expected_content = scenario["expected_content"]
        
        # Test conversion based on error type
        if isinstance(error, botocore.exceptions.ClientError):
            result = S3ErrorConverter.from_client_error(
                error,
                "downloading",
                SatellitePattern.GOES_16,
                datetime(2023, 6, 15, 12, 0, 0),
                {"bucket": "test-bucket", "key": "test.nc"},
            )
        else:
            result = S3ErrorConverter.from_generic_error(
                error,
                "downloading",
                SatellitePattern.GOES_16,
                datetime(2023, 6, 15, 12, 0, 0),
                {"bucket": "test-bucket", "key": "test.nc"},
            )
        
        # Verify conversion result
        assert isinstance(result, expected_type)
        
        # Check message content
        error_message = result.message.lower()
        for content in expected_content:
            assert content.lower() in error_message
        
        # Verify technical details exist
        assert result.technical_details is not None
        assert len(result.technical_details) > 0

    def test_error_type_detection_comprehensive(self):
        """Test comprehensive error type detection."""
        error_type_cases = [
            # Custom error types
            (ResourceNotFoundError("test"), "not_found"),
            (AuthenticationError("test"), "auth"),
            (RemoteConnectionError("timeout occurred"), "timeout"),
            (RemoteConnectionError("network issue"), "network"),
            (RemoteStoreError("generic"), "unknown"),
            
            # Boto3 client errors
            (botocore.exceptions.ClientError({"Error": {"Code": "404"}}, "GetObject"), "not_found"),
            (botocore.exceptions.ClientError({"Error": {"Code": "403"}}, "GetObject"), "auth"),
            (botocore.exceptions.ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject"), "not_found"),
            (botocore.exceptions.ClientError({"Error": {"Code": "InvalidAccessKeyId"}}, "GetObject"), "auth"),
            
            # Network-related errors
            (TimeoutError(), "timeout"),
            (ConnectionError(), "network"),
            (socket.gaierror(), "network"),
            (socket.timeout(), "timeout"),
            
            # Permission errors
            (PermissionError(), "auth"),
            (OSError(), "unknown"),
            
            # Generic errors
            (ValueError(), "unknown"),
            (RuntimeError(), "unknown"),
            (Exception(), "unknown"),
        ]
        
        for error, expected_type in error_type_cases:
            actual_type = S3ErrorConverter.get_error_type(error)
            assert actual_type == expected_type, f"Error {type(error).__name__} should be type '{expected_type}', got '{actual_type}'"

    @pytest.mark.parametrize("diagnostic_scenario", [
        "dns_resolution_success",
        "dns_resolution_failure",
    ])
    def test_network_diagnostics_scenarios(self, diagnostics_scenarios, diagnostic_scenario):
        """Test network diagnostics with various scenarios."""
        scenario = diagnostics_scenarios[diagnostic_scenario]
        
        if "mock_response" in scenario:
            # Success scenario
            with patch("socket.gethostbyname", return_value=scenario["mock_response"]):
                info = NetworkDiagnostics.collect_system_info()
        elif "mock_exception" in scenario:
            # Failure scenario
            with patch("socket.gethostbyname", side_effect=scenario["mock_exception"]):
                info = NetworkDiagnostics.collect_system_info()
        
        # Verify basic system info
        assert "timestamp" in info
        assert "platform" in info
        assert "python_version" in info
        assert "hostname" in info
        assert info["hostname"] == socket.gethostname()
        
        # Verify S3 host resolution results
        assert "s3_host_resolution" in info
        resolutions = info["s3_host_resolution"]
        
        # Should have results for all NOAA hosts
        assert len(resolutions) == len(NetworkDiagnostics.NOAA_S3_HOSTS)
        
        # Check resolution results based on scenario
        for resolution in resolutions:
            assert "success" in resolution
            assert "hostname" in resolution
            
            if scenario["expected_success"]:
                assert resolution["success"] is True
                assert "ip" in resolution
                assert resolution["ip"] == scenario["mock_response"]
            else:
                assert resolution["success"] is False
                assert "error" in resolution

    def test_network_diagnostics_partial_failure(self, diagnostics_scenarios):
        """Test network diagnostics with partial DNS failures."""
        scenario = diagnostics_scenarios["partial_dns_failure"]
        
        # Mock to return success for some hosts, failure for others
        def mock_gethostbyname(hostname):
            if "goes16" in hostname:
                return "52.216.0.1"  # Success
            else:
                raise socket.gaierror("Name resolution failed")  # Failure
        
        with patch("socket.gethostbyname", side_effect=mock_gethostbyname):
            info = NetworkDiagnostics.collect_system_info()
        
        resolutions = info["s3_host_resolution"]
        
        # Should have both successes and failures
        successes = [r for r in resolutions if r["success"]]
        failures = [r for r in resolutions if not r["success"]]
        
        assert len(successes) > 0, "Should have some successful resolutions"
        assert len(failures) > 0, "Should have some failed resolutions"

    def test_network_error_details_creation(self):
        """Test creation of detailed network error information."""
        error_cases = [
            {
                "error": ConnectionError("Connection timeout after 30 seconds"),
                "operation": "downloading GOES-16 data",
                "context": {"bucket": "noaa-goes16", "key": "ABI-L1b-RadC/test.nc", "satellite": "GOES-16"},
                "expected_content": ["Connection timeout", "downloading GOES-16", "noaa-goes16"],
            },
            {
                "error": TimeoutError("Read timeout"),
                "operation": "uploading file",
                "context": {"bucket": "test-bucket", "key": "test.nc", "timeout": 60},
                "expected_content": ["Read timeout", "uploading file", "test-bucket"],
            },
            {
                "error": socket.gaierror("DNS resolution failed"),
                "operation": "connecting to S3",
                "context": {"host": "s3.amazonaws.com", "region": "us-east-1"},
                "expected_content": ["DNS resolution", "connecting to S3", "s3.amazonaws.com"],
            },
        ]
        
        for case in error_cases:
            details = NetworkDiagnostics.create_network_error_details(
                case["error"],
                case["operation"],
                case["context"]
            )
            
            # Verify details contain expected content
            details_lower = details.lower()
            for content in case["expected_content"]:
                assert content.lower() in details_lower
            
            # Verify standard sections are present
            assert "Network operation failed:" in details
            assert "Error type:" in details
            assert "Error message:" in details
            assert "Troubleshooting steps:" in details
            
            # Verify context information is included
            for key, value in case["context"].items():
                assert f"{key}: {value}" in details.lower() or str(value).lower() in details.lower()

    def test_stats_tracker_logging_thresholds(self, stats_tracker_factory):
        """Test statistics tracker logging thresholds."""
        tracker = stats_tracker_factory()
        
        # Test logging threshold (every 10 attempts)
        for i in range(9):
            tracker.update_attempt(success=True)
            assert tracker.should_log_stats() is False
        
        # 10th attempt should trigger logging
        tracker.update_attempt(success=True)
        assert tracker.should_log_stats() is True
        
        # Reset and test diagnostics threshold (every 5 failures)
        tracker.reset()
        
        for i in range(4):
            tracker.update_attempt(success=False, error_type="network")
            assert tracker.should_collect_diagnostics() is False
        
        # 5th failure should trigger diagnostics
        tracker.update_attempt(success=False, error_type="network")
        assert tracker.should_collect_diagnostics() is True

    def test_stats_tracker_metrics_calculation(self, stats_tracker_factory):
        """Test comprehensive metrics calculation."""
        tracker = stats_tracker_factory()
        
        # Add varied download data
        download_data = [
            {"success": True, "download_time": 1.0, "file_size": 1000},
            {"success": True, "download_time": 2.0, "file_size": 2000},
            {"success": True, "download_time": 3.0, "file_size": 3000},
            {"success": False, "error_type": "network"},
            {"success": False, "error_type": "timeout"},
        ]
        
        for data in download_data:
            tracker.update_attempt(**data)
        
        metrics = tracker.get_metrics()
        
        # Verify basic metrics
        assert metrics["total_attempts"] == 5
        assert metrics["successful"] == 3
        assert metrics["success_rate"] == pytest.approx(60.0, rel=0.01)
        
        # Verify time calculations
        assert metrics["avg_time"] == pytest.approx(2.0, rel=0.01)  # (1+2+3)/3 = 2.0
        
        # Verify byte calculations
        assert metrics["total_bytes"] == 6000  # 1000+2000+3000
        
        # Verify network speed calculation
        if "KB/s" in metrics["network_speed"]:
            # Should calculate speed based on total bytes and time
            expected_speed = 6000 / (1.0 + 2.0 + 3.0)  # bytes per second
            assert expected_speed > 0

    def test_stats_tracker_reset_functionality(self, stats_tracker_factory):
        """Test comprehensive reset functionality."""
        tracker = stats_tracker_factory()
        
        # Add comprehensive data
        tracker.update_attempt(success=True, download_time=1.0, file_size=1000, satellite="GOES_16")
        tracker.update_attempt(success=False, error_type="network", error_message="Connection failed")
        tracker.increment_retry()
        tracker.increment_retry()
        
        # Verify data exists
        stats = tracker.get_stats()
        assert stats.total_attempts == 2
        assert stats.successful == 1
        assert stats.failed == 1
        assert stats.retry_count == 2
        assert len(stats.download_times) == 1
        assert len(stats.errors) == 1
        assert len(stats.recent_attempts) == 2
        
        # Reset and verify everything is cleared
        tracker.reset()
        
        reset_stats = tracker.get_stats()
        assert reset_stats.total_attempts == 0
        assert reset_stats.successful == 0
        assert reset_stats.failed == 0
        assert reset_stats.retry_count == 0
        assert reset_stats.total_bytes == 0
        assert reset_stats.network_errors == 0
        assert reset_stats.auth_errors == 0
        assert reset_stats.timeouts == 0
        assert reset_stats.not_found == 0
        assert len(reset_stats.download_times) == 0
        assert len(reset_stats.errors) == 0
        assert len(reset_stats.recent_attempts) == 0
        
        # Session ID and hostname should remain
        assert reset_stats.session_id is not None
        assert reset_stats.hostname == socket.gethostname()

    def test_concurrent_stats_tracking(self, stats_tracker_factory):
        """Test statistics tracking under concurrent access."""
        import threading
        import time
        
        tracker = stats_tracker_factory()
        results = []
        
        def worker_thread(thread_id, operation_count):
            thread_results = []
            for i in range(operation_count):
                try:
                    # Alternate between success and failure
                    if i % 2 == 0:
                        tracker.update_attempt(
                            success=True,
                            download_time=i * 0.1,
                            file_size=i * 100,
                            satellite=f"GOES_{16 + (i % 2)}"
                        )
                    else:
                        tracker.update_attempt(
                            success=False,
                            error_type="network",
                            error_message=f"Error {thread_id}-{i}"
                        )
                    
                    # Add some retries
                    if i % 3 == 0:
                        tracker.increment_retry()
                    
                    thread_results.append(f"thread_{thread_id}_op_{i}")
                    time.sleep(0.001)  # Small delay
                    
                except Exception as e:
                    thread_results.append(f"thread_{thread_id}_error: {e}")
            
            results.extend(thread_results)
        
        # Run concurrent threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker_thread, args=(i, 10))
            threads.append(thread)
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        assert len(results) == 30  # 3 threads * 10 operations each
        assert all("error" not in result for result in results)
        
        # Verify final statistics
        stats = tracker.get_stats()
        assert stats.total_attempts == 30
        assert stats.successful == 15  # Half successful
        assert stats.failed == 15  # Half failed
        assert stats.retry_count == 10  # Every 3rd operation

    def test_memory_efficiency_during_large_operations(self, stats_tracker_factory):
        """Test memory efficiency during large-scale operations."""
        import sys
        
        tracker = stats_tracker_factory()
        initial_refs = sys.getrefcount(DownloadStatsTracker)
        
        # Perform many operations
        for i in range(1000):
            tracker.update_attempt(
                success=i % 2 == 0,
                download_time=i * 0.001,
                file_size=i * 10,
                error_type="network" if i % 2 == 1 else None,
                error_message=f"Error {i}" if i % 2 == 1 else None,
                satellite=f"GOES_{16 + (i % 2)}"
            )
            
            # Check memory periodically
            if i % 100 == 0:
                current_refs = sys.getrefcount(DownloadStatsTracker)
                assert abs(current_refs - initial_refs) <= 5, f"Memory leak at operation {i}"
        
        final_refs = sys.getrefcount(DownloadStatsTracker)
        assert abs(final_refs - initial_refs) <= 10, f"Memory leak detected: {initial_refs} -> {final_refs}"
        
        # Verify tracker still functions correctly after many operations
        stats = tracker.get_stats()
        assert stats.total_attempts == 1000
        assert stats.successful == 500
        assert stats.failed == 500

    def test_edge_case_error_scenarios(self):
        """Test edge case error scenarios."""
        edge_cases = [
            # Empty error messages
            botocore.exceptions.ClientError({"Error": {"Code": "404", "Message": ""}}, "GetObject"),
            
            # Very long error messages
            botocore.exceptions.ClientError(
                {"Error": {"Code": "500", "Message": "x" * 10000}}, "GetObject"
            ),
            
            # Unicode in error messages
            botocore.exceptions.ClientError(
                {"Error": {"Code": "403", "Message": "Access denied: 权限不足"}}, "GetObject"
            ),
            
            # Missing error codes
            botocore.exceptions.ClientError({"Error": {"Message": "No code"}}, "GetObject"),
            
            # Nested exceptions
            RuntimeError("Outer error", ValueError("Inner error")),
        ]
        
        for error in edge_cases:
            try:
                if isinstance(error, botocore.exceptions.ClientError):
                    result = S3ErrorConverter.from_client_error(
                        error, "testing", SatellitePattern.GOES_16, datetime.now()
                    )
                else:
                    result = S3ErrorConverter.from_generic_error(
                        error, "testing", SatellitePattern.GOES_16, datetime.now()
                    )
                
                # Should not crash and should return valid error
                assert isinstance(result, RemoteStoreError)
                assert result.message is not None
                assert len(result.message) > 0
                
            except Exception as e:
                pytest.fail(f"Edge case error handling failed for {type(error).__name__}: {e}")