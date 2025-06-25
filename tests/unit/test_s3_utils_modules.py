"""Tests for S3 utilities modules."""

import asyncio
import socket
import time
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import botocore.exceptions
import pytest

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
)
from goesvfi.integrity_check.remote.base import ConnectionError as RemoteConnectionError
from goesvfi.integrity_check.remote.base import (
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.remote.s3_utils import (
    DownloadStats,
    DownloadStatsTracker,
    NetworkDiagnostics,
    S3ClientConfig,
    S3ErrorConverter,
    create_s3_config,
)
from goesvfi.integrity_check.time_index import SatellitePattern


class TestDownloadStatsTracker:
    """Test the DownloadStatsTracker class."""

    def test_initialization(self):
        """Test tracker initialization."""
        tracker = DownloadStatsTracker()
        stats = tracker.get_stats()

        assert stats.total_attempts == 0
        assert stats.successful == 0
        assert stats.failed == 0
        assert stats.retry_count == 0
        assert stats.download_times == []
        assert stats.errors == []
        assert stats.recent_attempts == []
        assert stats.session_id is not None
        assert stats.hostname == socket.gethostname()

    def test_successful_download(self):
        """Test tracking successful download."""
        tracker = DownloadStatsTracker()

        tracker.update_attempt(
            success=True,
            download_time=2.5,
            file_size=1024,
            satellite="GOES_16",
            bucket="noaa-goes16",
            key="test.nc",
        )

        stats = tracker.get_stats()
        assert stats.total_attempts == 1
        assert stats.successful == 1
        assert stats.failed == 0
        assert stats.download_times == [2.5]
        assert stats.total_bytes == 1024
        assert stats.largest_file_size == 1024
        assert stats.smallest_file_size == 1024
        assert len(stats.recent_attempts) == 1

        # Check recent attempt
        attempt = stats.recent_attempts[0]
        assert attempt["success"] is True
        assert attempt["download_time"] == 2.5
        assert attempt["file_size"] == 1024
        assert attempt["satellite"] == "GOES_16"

    def test_failed_download(self):
        """Test tracking failed download."""
        tracker = DownloadStatsTracker()

        tracker.update_attempt(
            success=False,
            error_type="network",
            error_message="Connection timeout",
            satellite="GOES_16",
        )

        stats = tracker.get_stats()
        assert stats.total_attempts == 1
        assert stats.successful == 0
        assert stats.failed == 1
        assert stats.network_errors == 1
        assert len(stats.errors) == 1
        assert "network: Connection timeout" in stats.errors[0]

    def test_error_type_counters(self):
        """Test different error type counters."""
        tracker = DownloadStatsTracker()

        # Test each error type
        error_types = [
            ("not_found", "not_found"),
            ("auth", "auth_errors"),
            ("timeout", "timeouts"),
            ("network", "network_errors"),
        ]

        for error_type, counter_name in error_types:
            tracker.update_attempt(
                success=False,
                error_type=error_type,
                error_message=f"{error_type} error",
            )

        stats = tracker.get_stats()
        assert stats.failed == 4
        assert stats.not_found == 1
        assert stats.auth_errors == 1
        assert stats.timeouts == 1
        assert stats.network_errors == 1

    def test_retry_counter(self):
        """Test retry counter."""
        tracker = DownloadStatsTracker()

        tracker.increment_retry()
        tracker.increment_retry()

        stats = tracker.get_stats()
        assert stats.retry_count == 2

    def test_metrics_calculation(self):
        """Test metrics calculation."""
        tracker = DownloadStatsTracker()

        # Add some successful downloads
        tracker.update_attempt(success=True, download_time=1.0, file_size=1000)
        tracker.update_attempt(success=True, download_time=2.0, file_size=2000)
        tracker.update_attempt(success=False, error_type="network")

        metrics = tracker.get_metrics()

        assert metrics["total_attempts"] == 3
        assert metrics["successful"] == 2
        assert metrics["success_rate"] == pytest.approx(66.67, rel=0.01)
        assert metrics["avg_time"] == 1.5
        assert metrics["total_bytes"] == 3000

        # Check network speed calculation
        assert "KB/s" in metrics["network_speed"] or metrics["network_speed"] == "N/A"

    def test_reset(self):
        """Test resetting statistics."""
        tracker = DownloadStatsTracker()

        # Add some data
        tracker.update_attempt(success=True, download_time=1.0, file_size=1000)
        tracker.increment_retry()

        # Reset
        tracker.reset()

        stats = tracker.get_stats()
        assert stats.total_attempts == 0
        assert stats.successful == 0
        assert stats.retry_count == 0

    def test_should_log_stats(self):
        """Test when to log statistics."""
        tracker = DownloadStatsTracker()

        # Should not log initially
        assert tracker.should_log_stats() is False

        # Add 9 attempts - still shouldn't log
        for i in range(9):
            tracker.update_attempt(success=True)
        assert tracker.should_log_stats() is False

        # 10th attempt should trigger logging
        tracker.update_attempt(success=True)
        assert tracker.should_log_stats() is True

    def test_should_collect_diagnostics(self):
        """Test when to collect diagnostics."""
        tracker = DownloadStatsTracker()

        # Should not collect initially
        assert tracker.should_collect_diagnostics() is False

        # Add 4 failures - still shouldn't collect
        for i in range(4):
            tracker.update_attempt(success=False)
        assert tracker.should_collect_diagnostics() is False

        # 5th failure should trigger diagnostics
        tracker.update_attempt(success=False)
        assert tracker.should_collect_diagnostics() is True


class TestS3ClientConfig:
    """Test S3 client configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = S3ClientConfig()

        assert config.aws_profile is None
        assert config.aws_region == "us-east-1"
        assert config.timeout == 60
        assert config.connect_timeout == 10
        assert config.max_retries == 2
        assert config.enable_debug_logging is False

    def test_custom_config(self):
        """Test custom configuration."""
        config = S3ClientConfig(
            aws_profile="custom",
            aws_region="us-west-2",
            timeout=120,
            connect_timeout=20,
            max_retries=5,
            enable_debug_logging=True,
        )

        assert config.aws_profile == "custom"
        assert config.aws_region == "us-west-2"
        assert config.timeout == 120
        assert config.connect_timeout == 20
        assert config.max_retries == 5
        assert config.enable_debug_logging is True

    def test_session_kwargs(self):
        """Test session kwargs generation."""
        # Without profile
        config = S3ClientConfig(aws_region="us-west-2")
        kwargs = config.get_session_kwargs()
        assert kwargs == {"region_name": "us-west-2"}

        # With profile
        config = S3ClientConfig(aws_profile="custom", aws_region="us-west-2")
        kwargs = config.get_session_kwargs()
        assert kwargs == {"region_name": "us-west-2", "profile_name": "custom"}

    def test_create_s3_config(self):
        """Test creating botocore config."""
        config = create_s3_config(
            timeout=120,
            connect_timeout=20,
            max_retries=3,
            use_unsigned=True,
        )

        assert config.connect_timeout == 20
        assert config.read_timeout == 120
        assert config.retries["max_attempts"] == 3
        assert config.signature_version == botocore.UNSIGNED

        # Test without unsigned
        config = create_s3_config(timeout=60, use_unsigned=False)
        assert hasattr(config, "signature_version") is False or config.signature_version != botocore.UNSIGNED


class TestNetworkDiagnostics:
    """Test network diagnostics functionality."""

    def test_collect_system_info(self):
        """Test system information collection."""
        info = NetworkDiagnostics.collect_system_info()

        assert "timestamp" in info
        assert "platform" in info
        assert "python_version" in info
        assert "hostname" in info
        assert info["hostname"] == socket.gethostname()

    @patch("socket.gethostbyname")
    def test_s3_resolution_success(self, mock_gethostbyname):
        """Test successful S3 hostname resolution."""
        mock_gethostbyname.return_value = "1.2.3.4"

        info = NetworkDiagnostics.collect_system_info()

        assert "s3_host_resolution" in info
        resolutions = info["s3_host_resolution"]

        # Should have results for all NOAA hosts
        assert len(resolutions) == len(NetworkDiagnostics.NOAA_S3_HOSTS)

        # All should be successful
        for resolution in resolutions:
            assert resolution["success"] is True
            assert resolution["ip"] == "1.2.3.4"

    @patch("socket.gethostbyname")
    def test_s3_resolution_failure(self, mock_gethostbyname):
        """Test failed S3 hostname resolution."""
        mock_gethostbyname.side_effect = socket.gaierror("Name resolution failed")

        info = NetworkDiagnostics.collect_system_info()

        resolutions = info["s3_host_resolution"]

        # All should fail
        for resolution in resolutions:
            assert resolution["success"] is False
            assert "error" in resolution

    def test_create_network_error_details(self):
        """Test creating network error details."""
        error = ConnectionError("Connection timeout")

        details = NetworkDiagnostics.create_network_error_details(
            error,
            "downloading file",
            {"bucket": "test-bucket", "key": "test.nc"},
        )

        assert "Network operation failed: downloading file" in details
        assert "Error type: ConnectionError" in details
        assert "Error message: Connection timeout" in details
        assert "bucket: test-bucket" in details
        assert "key: test.nc" in details
        assert "Troubleshooting steps:" in details


class TestS3ErrorConverter:
    """Test S3 error conversion."""

    def test_client_error_404(self):
        """Test converting 404 error."""
        error = botocore.exceptions.ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "GetObject",
        )

        result = S3ErrorConverter.from_client_error(
            error,
            "downloading",
            SatellitePattern.GOES_16,
            datetime(2023, 1, 1, 12, 0),
            {"bucket": "test-bucket", "key": "test.nc"},
        )

        assert isinstance(result, ResourceNotFoundError)
        assert "Resource not found for GOES_16" in result.message
        assert result.technical_details is not None and "404" in result.technical_details

    def test_client_error_403(self):
        """Test converting 403 error."""
        error = botocore.exceptions.ClientError(
            {"Error": {"Code": "403", "Message": "Access Denied"}},
            "GetObject",
        )

        result = S3ErrorConverter.from_client_error(
            error,
            "downloading",
            SatellitePattern.GOES_16,
            datetime(2023, 1, 1, 12, 0),
        )

        assert isinstance(result, AuthenticationError)
        assert "Access denied to GOES_16 data" in result.message
        assert result.technical_details is not None and "publicly accessible" in result.technical_details

    def test_timeout_error(self):
        """Test converting timeout error."""
        error = asyncio.TimeoutError("Operation timed out")

        result = S3ErrorConverter.from_generic_error(
            error,
            "downloading",
            SatellitePattern.GOES_16,
            datetime(2023, 1, 1, 12, 0),
        )

        assert isinstance(result, RemoteConnectionError)
        assert "Timeout downloading GOES_16 data" in result.message
        assert result.technical_details is not None and "internet connection speed" in result.technical_details

    def test_permission_error(self):
        """Test converting permission error."""
        error = PermissionError("Permission denied")

        result = S3ErrorConverter.from_generic_error(
            error,
            "downloading",
            SatellitePattern.GOES_16,
            datetime(2023, 1, 1, 12, 0),
        )

        assert isinstance(result, AuthenticationError)
        assert "Permission error downloading GOES_16 data" in result.message
        assert result.technical_details is not None and "file system permissions" in result.technical_details

    def test_generic_error(self):
        """Test converting generic error."""
        error = ValueError("Something went wrong")

        result = S3ErrorConverter.from_generic_error(
            error,
            "downloading",
            SatellitePattern.GOES_16,
            datetime(2023, 1, 1, 12, 0),
        )

        assert isinstance(result, RemoteStoreError)
        assert "Error downloading GOES_16 data" in result.message

    def test_get_error_type(self):
        """Test error type detection."""
        # Test with our error types
        assert S3ErrorConverter.get_error_type(ResourceNotFoundError("")) == "not_found"
        assert S3ErrorConverter.get_error_type(AuthenticationError("")) == "auth"
        assert S3ErrorConverter.get_error_type(RemoteConnectionError("timeout")) == "timeout"
        assert S3ErrorConverter.get_error_type(RemoteConnectionError("network")) == "network"

        # Test with boto3 errors
        error_404 = botocore.exceptions.ClientError({"Error": {"Code": "404"}}, "GetObject")
        assert S3ErrorConverter.get_error_type(error_404) == "not_found"

        error_403 = botocore.exceptions.ClientError({"Error": {"Code": "403"}}, "GetObject")
        assert S3ErrorConverter.get_error_type(error_403) == "auth"

        # Test with timeout errors
        assert S3ErrorConverter.get_error_type(asyncio.TimeoutError()) == "timeout"
        assert S3ErrorConverter.get_error_type(TimeoutError()) == "timeout"

        # Test unknown error
        assert S3ErrorConverter.get_error_type(ValueError()) == "unknown"
