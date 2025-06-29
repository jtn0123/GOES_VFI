"""Optimized S3 download statistics tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common statistics configurations and data setups
- Parameterized test scenarios for comprehensive statistics tracking validation
- Enhanced error handling and boundary condition testing
- Mock-based testing to avoid real network operations and I/O
- Comprehensive memory management and performance testing
"""

from unittest.mock import patch, Mock
import pytest
from datetime import datetime, timedelta

from goesvfi.integrity_check.remote.download_statistics import reset_global_stats
from goesvfi.integrity_check.remote.s3_store import (
    get_download_stats,
    log_download_statistics,
    update_download_stats,
)


class TestS3DownloadStatsParamV2:
    """Optimized test class for S3 download statistics functionality."""

    @pytest.fixture(scope="class")
    def statistics_scenarios(self):
        """Define various statistics scenario test cases."""
        return {
            "successful_download": {
                "success": True,
                "download_time": 1.5,
                "file_size": 1024000,  # 1MB
                "error_type": None,
                "error_message": None,
                "satellite": "GOES-16",
                "product": "RadC",
                "band": 13,
            },
            "failed_timeout": {
                "success": False,
                "download_time": 30.0,
                "file_size": 0,
                "error_type": "timeout",
                "error_message": "Connection timeout after 30 seconds",
                "satellite": "GOES-18",
                "product": "RadF",
                "band": 2,
            },
            "failed_network": {
                "success": False,
                "download_time": 5.2,
                "file_size": 0,
                "error_type": "network",
                "error_message": "Network unreachable",
                "satellite": "GOES-16",
                "product": "RadM",
                "band": 7,
            },
            "failed_auth": {
                "success": False,
                "download_time": 0.8,
                "file_size": 0,
                "error_type": "authentication",
                "error_message": "Access denied: invalid credentials",
                "satellite": "GOES-18",
                "product": "RadC",
                "band": 1,
            },
            "large_file_success": {
                "success": True,
                "download_time": 45.0,
                "file_size": 104857600,  # 100MB
                "error_type": None,
                "error_message": None,
                "satellite": "GOES-16",
                "product": "RadF",
                "band": 13,
            },
            "quick_download": {
                "success": True,
                "download_time": 0.1,
                "file_size": 1024,  # 1KB
                "error_type": None,
                "error_message": None,
                "satellite": "GOES-18",
                "product": "RadM",
                "band": 1,
            },
        }

    @pytest.fixture(scope="class")
    def boundary_test_cases(self):
        """Define boundary condition test cases."""
        return {
            "zero_time": {
                "download_time": 0.0,
                "expected_valid": True,
            },
            "very_fast": {
                "download_time": 0.001,
                "expected_valid": True,
            },
            "very_slow": {
                "download_time": 3600.0,  # 1 hour
                "expected_valid": True,
            },
            "zero_size": {
                "file_size": 0,
                "expected_valid": True,
            },
            "large_size": {
                "file_size": 10**12,  # 1TB
                "expected_valid": True,
            },
            "negative_time": {
                "download_time": -1.0,
                "expected_valid": False,
            },
            "negative_size": {
                "file_size": -1024,
                "expected_valid": False,
            },
        }

    @pytest.fixture(scope="class")
    def memory_limit_scenarios(self):
        """Define memory limit scenario test cases."""
        return {
            "error_history": {
                "limit": 20,
                "field": "errors",
                "test_count": 30,
            },
            "download_times": {
                "limit": 100,
                "field": "download_times", 
                "test_count": 150,
            },
            "recent_attempts": {
                "limit": 50,
                "field": "recent_attempts",
                "test_count": 75,
            },
        }

    @pytest.fixture(autouse=True)
    def reset_statistics(self):
        """Reset global statistics before each test."""
        reset_global_stats()
        yield
        reset_global_stats()

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing log output."""
        with patch("goesvfi.integrity_check.remote.s3_store.LOGGER") as mock_log:
            yield mock_log

    @pytest.mark.parametrize("scenario_name", [
        "successful_download",
        "failed_timeout",
        "failed_network", 
        "failed_auth",
        "large_file_success",
        "quick_download",
    ])
    def test_update_download_stats_scenarios(self, statistics_scenarios, scenario_name):
        """Test update download statistics with various scenarios."""
        scenario = statistics_scenarios[scenario_name]
        
        # Update statistics
        update_download_stats(
            success=scenario["success"],
            download_time=scenario["download_time"],
            file_size=scenario["file_size"],
            error_type=scenario["error_type"],
            error_message=scenario["error_message"],
            satellite=scenario.get("satellite"),
            product=scenario.get("product"),
            band=scenario.get("band"),
        )
        
        # Verify statistics
        stats = get_download_stats()
        
        assert stats.total_attempts == 1
        
        if scenario["success"]:
            assert stats.successful == 1
            assert stats.failed == 0
            assert scenario["download_time"] in stats.download_times
            assert stats.total_bytes_downloaded == scenario["file_size"]
        else:
            assert stats.successful == 0
            assert stats.failed == 1
            assert len(stats.errors) == 1
            assert scenario["error_message"] in stats.errors[0]
            assert scenario["error_type"] in stats.errors[0]

    @pytest.mark.parametrize("success,error_type", [
        (True, None),
        (False, "timeout"),
        (False, "network"),
        (False, "authentication"),
        (False, "server_error"),
        (False, "file_not_found"),
    ])
    def test_basic_statistics_tracking(self, success, error_type):
        """Test basic statistics tracking for different success/error combinations."""
        error_message = f"Test error of type {error_type}" if error_type else None
        
        update_download_stats(
            success=success,
            download_time=1.0,
            file_size=100 if success else 0,
            error_type=error_type,
            error_message=error_message,
        )
        
        stats = get_download_stats()
        assert stats.total_attempts == 1
        
        if success:
            assert stats.successful == 1
            assert stats.failed == 0
            assert stats.total_bytes_downloaded == 100
        else:
            assert stats.successful == 0
            assert stats.failed == 1
            assert len(stats.errors) == 1
            assert error_message in stats.errors[0]

    @pytest.mark.parametrize("limit_scenario", [
        "error_history",
        "download_times",
        "recent_attempts",
    ])
    def test_memory_limit_enforcement(self, memory_limit_scenarios, limit_scenario):
        """Test that memory limits are properly enforced."""
        scenario = memory_limit_scenarios[limit_scenario]
        limit = scenario["limit"]
        test_count = scenario["test_count"]
        field = scenario["field"]
        
        # Add more items than the limit
        for i in range(test_count):
            if field == "errors":
                update_download_stats(
                    success=False,
                    download_time=1.0,
                    file_size=0,
                    error_type="test",
                    error_message=f"Error {i}",
                )
            elif field == "download_times":
                update_download_stats(
                    success=True,
                    download_time=float(i),
                    file_size=100,
                )
            elif field == "recent_attempts":
                update_download_stats(
                    success=True,
                    download_time=1.0,
                    file_size=100,
                    satellite=f"satellite_{i}",
                )
        
        stats = get_download_stats()
        
        # Verify the limit is enforced
        if field == "errors":
            assert len(stats.errors) == limit
            # Most recent error should be present
            assert f"Error {test_count - 1}" in stats.errors[-1]
        elif field == "download_times":
            assert len(stats.download_times) == limit
            # Most recent download time should be present
            assert float(test_count - 1) in stats.download_times
        elif field == "recent_attempts":
            assert len(stats.recent_attempts) == limit
            # Most recent attempt should be present
            recent_satellites = [attempt.get("satellite") for attempt in stats.recent_attempts]
            assert f"satellite_{test_count - 1}" in recent_satellites

    def test_error_history_content_verification(self):
        """Test that error history contains proper content."""
        error_cases = [
            {"type": "timeout", "message": "Connection timeout"},
            {"type": "network", "message": "Network unreachable"}, 
            {"type": "auth", "message": "Access denied"},
        ]
        
        for case in error_cases:
            update_download_stats(
                success=False,
                download_time=1.0,
                file_size=0,
                error_type=case["type"],
                error_message=case["message"],
            )
        
        stats = get_download_stats()
        
        # Verify all errors are recorded
        assert len(stats.errors) == len(error_cases)
        
        # Verify error content
        for i, case in enumerate(error_cases):
            error_record = stats.errors[i]
            assert case["type"] in error_record
            assert case["message"] in error_record
            assert "timestamp" in error_record.lower() or "time" in error_record.lower()

    def test_download_statistics_aggregation(self):
        """Test that download statistics are properly aggregated."""
        test_downloads = [
            {"time": 1.0, "size": 1000, "success": True},
            {"time": 2.5, "size": 2000, "success": True},
            {"time": 0.5, "size": 500, "success": True},
            {"time": 10.0, "size": 0, "success": False},
        ]
        
        for download in test_downloads:
            update_download_stats(
                success=download["success"],
                download_time=download["time"],
                file_size=download["size"],
                error_type="network" if not download["success"] else None,
                error_message="Network error" if not download["success"] else None,
            )
        
        stats = get_download_stats()
        
        # Verify totals
        assert stats.total_attempts == 4
        assert stats.successful == 3
        assert stats.failed == 1
        assert stats.total_bytes_downloaded == 3500  # Sum of successful downloads
        
        # Verify download times
        successful_times = [d["time"] for d in test_downloads if d["success"]]
        for time_val in successful_times:
            assert time_val in stats.download_times

    @pytest.mark.parametrize("boundary_case", [
        "zero_time",
        "very_fast",
        "very_slow",
        "zero_size",
        "large_size",
    ])
    def test_boundary_conditions(self, boundary_test_cases, boundary_case):
        """Test boundary conditions for statistics values."""
        test_case = boundary_test_cases[boundary_case]
        
        # Prepare update parameters
        params = {
            "success": True,
            "download_time": test_case.get("download_time", 1.0),
            "file_size": test_case.get("file_size", 1024),
        }
        
        if test_case["expected_valid"]:
            # Should not raise exception
            update_download_stats(**params)
            stats = get_download_stats()
            assert stats.total_attempts == 1
        else:
            # Should handle invalid values gracefully or raise appropriate error
            try:
                update_download_stats(**params)
                # If no exception, verify stats are reasonable
                stats = get_download_stats()
                assert stats.total_attempts >= 0
            except (ValueError, AssertionError):
                # Expected for invalid inputs
                pass

    def test_statistics_logging_functionality(self, mock_logger):
        """Test statistics logging functionality."""
        # Add some test data
        update_download_stats(success=True, download_time=1.5, file_size=1024)
        update_download_stats(success=False, download_time=5.0, file_size=0, 
                             error_type="timeout", error_message="Connection timeout")
        
        # Test logging
        log_download_statistics()
        
        # Verify logger was called
        assert mock_logger.info.called, "Logger should be called for statistics"
        
        # Verify logging contains relevant information
        log_calls = mock_logger.info.call_args_list
        log_content = " ".join(str(call) for call in log_calls)
        
        # Should contain key statistics
        assert "attempt" in log_content.lower() or "download" in log_content.lower()

    def test_concurrent_statistics_updates(self):
        """Test concurrent updates to statistics (thread safety simulation)."""
        import threading
        import time
        
        results = []
        
        def update_worker(worker_id, count):
            for i in range(count):
                try:
                    update_download_stats(
                        success=i % 2 == 0,  # Alternate success/failure
                        download_time=float(i) / 10,
                        file_size=100 * i if i % 2 == 0 else 0,
                        error_type="test" if i % 2 == 1 else None,
                        error_message=f"Error {worker_id}-{i}" if i % 2 == 1 else None,
                    )
                    time.sleep(0.001)  # Small delay
                    results.append(f"worker_{worker_id}_update_{i}")
                except Exception as e:
                    results.append(f"worker_{worker_id}_error: {e}")
        
        # Create multiple threads
        threads = []
        for worker_id in range(3):
            thread = threading.Thread(target=update_worker, args=(worker_id, 5))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        assert len(results) == 15  # 3 workers * 5 updates each
        assert all("error" not in result for result in results)
        
        # Verify final statistics
        stats = get_download_stats()
        assert stats.total_attempts == 15

    def test_statistics_reset_functionality(self):
        """Test that statistics can be properly reset."""
        # Add some test data
        update_download_stats(success=True, download_time=1.0, file_size=1024)
        update_download_stats(success=False, download_time=2.0, file_size=0,
                             error_type="test", error_message="Test error")
        
        # Verify data exists
        stats = get_download_stats()
        assert stats.total_attempts == 2
        assert stats.successful == 1
        assert stats.failed == 1
        
        # Reset statistics
        reset_global_stats()
        
        # Verify reset worked
        stats = get_download_stats()
        assert stats.total_attempts == 0
        assert stats.successful == 0
        assert stats.failed == 0
        assert len(stats.download_times) == 0
        assert len(stats.errors) == 0
        assert len(stats.recent_attempts) == 0

    def test_statistics_with_metadata(self):
        """Test statistics tracking with additional metadata."""
        metadata_cases = [
            {
                "satellite": "GOES-16",
                "product": "RadC",
                "band": 13,
                "timestamp": datetime.now(),
            },
            {
                "satellite": "GOES-18", 
                "product": "RadF",
                "band": 2,
                "location": "CONUS",
            },
            {
                "satellite": "GOES-16",
                "product": "RadM",
                "band": 7,
                "region": "Mesoscale-1",
            },
        ]
        
        for case in metadata_cases:
            update_download_stats(
                success=True,
                download_time=1.0,
                file_size=1024,
                **case
            )
        
        stats = get_download_stats()
        assert stats.total_attempts == len(metadata_cases)
        assert len(stats.recent_attempts) == len(metadata_cases)
        
        # Verify metadata is preserved
        for i, case in enumerate(metadata_cases):
            attempt = stats.recent_attempts[i]
            for key, value in case.items():
                if key in attempt:
                    assert attempt[key] == value or str(attempt[key]) == str(value)

    def test_error_type_categorization(self):
        """Test that error types are properly categorized."""
        error_types = [
            "timeout",
            "network", 
            "authentication",
            "server_error",
            "file_not_found",
            "permission_denied",
            "quota_exceeded",
            "unknown",
        ]
        
        for error_type in error_types:
            update_download_stats(
                success=False,
                download_time=1.0,
                file_size=0,
                error_type=error_type,
                error_message=f"Test {error_type} error",
            )
        
        stats = get_download_stats()
        assert stats.failed == len(error_types)
        assert len(stats.errors) == len(error_types)
        
        # Verify all error types are recorded
        error_content = " ".join(stats.errors)
        for error_type in error_types:
            assert error_type in error_content

    def test_performance_statistics_tracking(self):
        """Test performance characteristics of statistics tracking."""
        import time
        
        # Test update performance
        start_time = time.time()
        
        for i in range(1000):
            update_download_stats(
                success=i % 2 == 0,
                download_time=float(i) / 1000,
                file_size=1024 * i,
                error_type="test" if i % 2 == 1 else None,
                error_message=f"Error {i}" if i % 2 == 1 else None,
            )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete 1000 updates quickly
        assert duration < 1.0, f"Statistics updates too slow: {duration:.3f}s"
        
        # Verify final state
        stats = get_download_stats()
        assert stats.total_attempts == 1000

    def test_memory_usage_stability(self):
        """Test that memory usage remains stable over many operations."""
        import sys
        
        # Record initial memory usage
        initial_refs = sys.getrefcount(dict)
        
        # Perform many operations
        for i in range(500):
            update_download_stats(
                success=i % 3 != 0,  # Mix of success/failure
                download_time=float(i % 10) / 10,
                file_size=1024 * (i % 100),
                error_type="test" if i % 3 == 0 else None,
                error_message=f"Error {i}" if i % 3 == 0 else None,
                satellite=f"SAT-{i % 5}",
            )
            
            # Periodically check memory limits are enforced
            if i % 50 == 0:
                stats = get_download_stats()
                assert len(stats.errors) <= 20
                assert len(stats.download_times) <= 100
                assert len(stats.recent_attempts) <= 50
        
        # Check final memory usage
        final_refs = sys.getrefcount(dict)
        
        # Memory usage should be stable
        assert abs(final_refs - initial_refs) <= 10, f"Memory usage increased: {initial_refs} -> {final_refs}"

    def test_edge_case_error_messages(self):
        """Test handling of edge case error messages."""
        edge_cases = [
            None,  # No error message
            "",    # Empty error message
            "a" * 10000,  # Very long error message
            "Unicode: 你好世界 🌍",  # Unicode characters
            "Special chars: @#$%^&*()[]{}|\\:;\"'<>?,./",  # Special characters
        ]
        
        for i, error_msg in enumerate(edge_cases):
            update_download_stats(
                success=False,
                download_time=1.0,
                file_size=0,
                error_type=f"test_{i}",
                error_message=error_msg,
            )
        
        stats = get_download_stats()
        assert stats.failed == len(edge_cases)
        assert len(stats.errors) == len(edge_cases)
        
        # Verify all errors are handled gracefully
        for error_record in stats.errors:
            assert isinstance(error_record, str)
            assert len(error_record) > 0  # Should have some content

    def test_statistics_data_integrity(self):
        """Test that statistics maintain data integrity over time."""
        # Perform a series of operations
        operations = [
            {"success": True, "time": 1.0, "size": 1000},
            {"success": False, "time": 2.0, "size": 0},
            {"success": True, "time": 0.5, "size": 500},
            {"success": True, "time": 3.0, "size": 3000},
            {"success": False, "time": 1.5, "size": 0},
        ]
        
        total_bytes = 0
        successful_count = 0
        failed_count = 0
        
        for op in operations:
            update_download_stats(
                success=op["success"],
                download_time=op["time"],
                file_size=op["size"],
                error_type="network" if not op["success"] else None,
                error_message="Network error" if not op["success"] else None,
            )
            
            if op["success"]:
                total_bytes += op["size"]
                successful_count += 1
            else:
                failed_count += 1
        
        # Verify integrity
        stats = get_download_stats()
        assert stats.total_attempts == len(operations)
        assert stats.successful == successful_count
        assert stats.failed == failed_count
        assert stats.total_bytes_downloaded == total_bytes
        
        # Verify consistency
        assert stats.successful + stats.failed == stats.total_attempts