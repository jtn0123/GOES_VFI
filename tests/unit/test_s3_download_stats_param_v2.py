"""
Optimized unit tests for S3 download statistics functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for stats management and reset functionality
- Enhanced test managers for comprehensive statistics validation
- Batch testing of multiple download scenarios and error conditions
- Parameterized testing for different success/failure combinations
"""

import time
from typing import Any
from unittest.mock import patch

import pytest

from goesvfi.integrity_check.remote import s3_store
from goesvfi.integrity_check.remote.s3_store import (
    log_download_statistics,
    update_download_stats,
)


class TestS3DownloadStatsParamOptimizedV2:
    """Optimized S3 download statistics tests with full coverage."""

    @pytest.fixture(scope="class")
    def s3_stats_test_components(self) -> dict[str, Any]:  # noqa: PLR6301, C901
        """Create shared components for S3 download statistics testing.

        Returns:
            dict[str, Any]: Dictionary containing S3 download statistics testing components.
        """

        # Enhanced S3 Download Stats Test Manager
        class S3DownloadStatsTestManager:
            """Manage S3 download statistics testing scenarios."""

            def __init__(self) -> None:
                # Define default stats structure
                self.default_stats = {
                    "total_attempts": 0,
                    "successful": 0,
                    "failed": 0,
                    "retry_count": 0,
                    "not_found": 0,
                    "auth_errors": 0,
                    "timeouts": 0,
                    "network_errors": 0,
                    "download_times": [],
                    "download_rates": [],
                    "start_time": time.time(),
                    "last_success_time": 0,
                    "largest_file_size": 0,
                    "smallest_file_size": float("inf"),
                    "total_bytes": 0,
                    "errors": [],
                }

                # Test scenarios configuration
                self.test_scenarios = [
                    # (success, error_type, download_time, file_size, error_message)
                    (True, None, 1.0, 100, None),
                    (False, "timeout", 5.0, 0, "Connection timeout"),
                    (True, None, 0.5, 200, None),
                    (False, "network", 2.0, 0, "Network error"),
                    (True, None, 2.5, 500, None),
                    (False, "not_found", 1.0, 0, "File not found"),
                    (False, "auth", 0.1, 0, "Authentication failed"),
                    (True, None, 3.0, 1000, None),
                ]

                # Error type mappings
                self.error_type_stats = {
                    "timeout": "timeouts",
                    "network": "network_errors",
                    "not_found": "not_found",
                    "auth": "auth_errors",
                }

                # Define test methods
                self.test_methods = {
                    "basic_stats_update": self._test_basic_stats_update,
                    "error_history_management": self._test_error_history_management,
                    "download_rate_calculation": self._test_download_rate_calculation,
                    "file_size_tracking": self._test_file_size_tracking,
                    "time_tracking": self._test_time_tracking,
                    "statistics_logging": self._test_statistics_logging,
                    "batch_operations": self._test_batch_operations,
                    "edge_cases": self._test_edge_cases,
                    "performance_validation": self._test_performance_validation,
                }

            def reset_stats(self) -> None:
                """Reset download statistics to default state."""
                s3_store.DOWNLOAD_STATS.clear()
                s3_store.DOWNLOAD_STATS.update(self.default_stats.copy())

            def get_current_stats(self) -> dict[str, Any]:  # noqa: PLR6301
                """Get current download statistics.

                Returns:
                    dict[str, Any]: Current download statistics dictionary.
                """
                return s3_store.DOWNLOAD_STATS.copy()

            def _test_basic_stats_update(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test basic statistics update scenarios.

                Returns:
                    dict[str, Any]: Test results for basic statistics update scenarios.
                """
                results = {}

                if scenario_name == "single_update":
                    # Test single stat update
                    success = kwargs.get("success", True)
                    error_type = kwargs.get("error_type")
                    download_time = kwargs.get("download_time", 1.0)
                    file_size = kwargs.get("file_size", 100)
                    error_message = kwargs.get("error_message")

                    self.reset_stats()

                    update_download_stats(
                        success=success,
                        download_time=download_time,
                        file_size=file_size,
                        error_type=error_type,
                        error_message=error_message,
                    )

                    stats = self.get_current_stats()

                    # Verify basic counters
                    assert stats["total_attempts"] == 1

                    if success:
                        assert stats["successful"] == 1
                        assert stats["failed"] == 0
                        assert download_time in stats["download_times"]
                        assert file_size > 0  # Should have file size for successful downloads
                    else:
                        assert stats["successful"] == 0
                        assert stats["failed"] == 1

                        # Check error type specific counter
                        if error_type and error_type in self.error_type_stats:
                            error_stat_key = self.error_type_stats[error_type]
                            assert stats[error_stat_key] == 1

                        # Check error history
                        if error_message:
                            assert len(stats["errors"]) == 1
                            assert error_message in str(stats["errors"][0])

                    results["basic_update_verified"] = True

                elif scenario_name == "parameterized_scenarios":
                    # Test all parameterized scenarios
                    scenario_results = []

                    for i, (success, error_type, download_time, file_size, error_message) in enumerate(
                        self.test_scenarios
                    ):
                        self.reset_stats()

                        update_download_stats(
                            success=success,
                            download_time=download_time,
                            file_size=file_size,
                            error_type=error_type,
                            error_message=error_message,
                        )

                        stats = self.get_current_stats()

                        # Verify each scenario
                        scenario_result = {
                            "scenario_index": i,
                            "success": success,
                            "total_attempts": stats["total_attempts"],
                            "successful": stats["successful"],
                            "failed": stats["failed"],
                        }

                        assert stats["total_attempts"] == 1
                        if success:
                            assert stats["successful"] == 1
                        else:
                            assert stats["failed"] == 1

                        scenario_results.append(scenario_result)

                    results["parameterized_scenarios"] = scenario_results
                    results["scenarios_tested"] = len(self.test_scenarios)

                return {"scenario": scenario_name, "results": results}

            def _test_error_history_management(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test error history management scenarios.

                Returns:
                    dict[str, Any]: Test results for error history management scenarios.
                """
                results = {}

                if scenario_name == "error_limit_enforcement":
                    # Test error history limit (should be 20)
                    self.reset_stats()

                    # Add 25 errors to test limit
                    for i in range(25):
                        update_download_stats(success=False, error_type="network", error_message=f"Error {i}")

                    stats = self.get_current_stats()

                    # Should only keep last 20 errors
                    assert len(stats["errors"]) == 20
                    assert stats["failed"] == 25  # But total count should still be accurate
                    assert stats["network_errors"] == 25

                    # Verify the errors are the most recent ones
                    error_messages = [str(error) for error in stats["errors"]]
                    assert "Error 24" in str(error_messages[-1])  # Most recent
                    assert "Error 5" in str(error_messages[0])  # Oldest kept (25-20+1=6, so index 5)

                    results["error_limit_verified"] = True

                elif scenario_name == "error_type_tracking":
                    # Test tracking of different error types
                    self.reset_stats()

                    error_scenarios = [
                        ("timeout", "Connection timeout", 3),
                        ("network", "Network failure", 2),
                        ("not_found", "File not found", 4),
                        ("auth", "Authentication failed", 1),
                    ]

                    total_errors = 0
                    for error_type, error_message, count in error_scenarios:
                        for i in range(count):
                            update_download_stats(
                                success=False, error_type=error_type, error_message=f"{error_message} {i}"
                            )
                            total_errors += 1

                    stats = self.get_current_stats()

                    # Verify error type counters
                    assert stats["timeouts"] == 3
                    assert stats["network_errors"] == 2
                    assert stats["not_found"] == 4
                    assert stats["auth_errors"] == 1
                    assert stats["failed"] == total_errors
                    assert len(stats["errors"]) == total_errors  # All should fit within limit

                    results["error_types_tracked"] = len(error_scenarios)
                    results["total_errors"] = total_errors

                return {"scenario": scenario_name, "results": results}

            def _test_download_rate_calculation(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test download rate calculation scenarios.

                Returns:
                    dict[str, Any]: Test results for download rate calculation scenarios.
                """
                results = {}

                if scenario_name == "rate_calculations":
                    # Test download rate calculations
                    self.reset_stats()

                    download_scenarios = [
                        (1.0, 1000),  # 1000 bytes/sec
                        (2.0, 2000),  # 1000 bytes/sec
                        (0.5, 500),  # 1000 bytes/sec
                        (4.0, 2000),  # 500 bytes/sec
                    ]

                    calculated_rates = []
                    for download_time, file_size in download_scenarios:
                        update_download_stats(success=True, download_time=download_time, file_size=file_size)

                        expected_rate = file_size / download_time
                        calculated_rates.append(expected_rate)

                    stats = self.get_current_stats()

                    # Verify rates were calculated and stored
                    assert len(stats["download_rates"]) == len(download_scenarios)

                    # Check that rates are reasonable
                    for i, expected_rate in enumerate(calculated_rates):
                        actual_rate = stats["download_rates"][i]
                        assert abs(actual_rate - expected_rate) < 0.01  # Allow small floating point differences

                    results["rates_calculated"] = len(calculated_rates)
                    results["average_rate"] = sum(stats["download_rates"]) / len(stats["download_rates"])

                return {"scenario": scenario_name, "results": results}

            def _test_file_size_tracking(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test file size tracking scenarios.

                Returns:
                    dict[str, Any]: Test results for file size tracking scenarios.
                """
                results = {}

                if scenario_name == "size_extremes":
                    # Test tracking of largest and smallest file sizes
                    self.reset_stats()

                    file_sizes = [100, 50, 1000, 25, 500, 2000, 10]

                    for size in file_sizes:
                        update_download_stats(success=True, download_time=1.0, file_size=size)

                    stats = self.get_current_stats()

                    # Verify size tracking
                    assert stats["largest_file_size"] == max(file_sizes)
                    assert stats["smallest_file_size"] == min(file_sizes)
                    assert stats["total_bytes"] == sum(file_sizes)

                    results["largest_size"] = stats["largest_file_size"]
                    results["smallest_size"] = stats["smallest_file_size"]
                    results["total_bytes"] = stats["total_bytes"]

                elif scenario_name == "size_accumulation":
                    # Test byte accumulation over multiple downloads
                    self.reset_stats()

                    sizes = [100, 200, 300, 400, 500]
                    running_total = 0

                    for size in sizes:
                        update_download_stats(success=True, download_time=1.0, file_size=size)
                        running_total += size

                        stats = self.get_current_stats()
                        assert stats["total_bytes"] == running_total

                    results["final_total"] = running_total
                    results["downloads"] = len(sizes)

                return {"scenario": scenario_name, "results": results}

            def _test_time_tracking(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test time tracking scenarios.

                Returns:
                    dict[str, Any]: Test results for time tracking scenarios.
                """
                results = {}

                if scenario_name == "download_times":
                    # Test download time tracking
                    self.reset_stats()

                    download_times = [1.0, 2.5, 0.5, 3.0, 1.5]

                    for download_time in download_times:
                        update_download_stats(success=True, download_time=download_time, file_size=100)

                    stats = self.get_current_stats()

                    # Verify all download times were recorded
                    assert len(stats["download_times"]) == len(download_times)
                    for expected_time in download_times:
                        assert expected_time in stats["download_times"]

                    results["times_recorded"] = len(stats["download_times"])
                    results["average_time"] = sum(stats["download_times"]) / len(stats["download_times"])

                elif scenario_name == "success_time_tracking":
                    # Test last success time tracking
                    self.reset_stats()
                    initial_time = stats["last_success_time"] = 0

                    # Record a successful download
                    before_time = time.time()
                    update_download_stats(success=True, download_time=1.0, file_size=100)
                    after_time = time.time()

                    stats = self.get_current_stats()

                    # Last success time should be updated
                    assert stats["last_success_time"] > initial_time
                    assert before_time <= stats["last_success_time"] <= after_time

                    results["success_time_updated"] = True

                return {"scenario": scenario_name, "results": results}

            def _test_statistics_logging(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test statistics logging scenarios.

                Returns:
                    dict[str, Any]: Test results for statistics logging scenarios.
                """
                results = {}

                if scenario_name == "log_output":
                    # Test statistics logging output
                    self.reset_stats()

                    # Add some statistics to log
                    update_download_stats(success=True, download_time=1.0, file_size=50)
                    update_download_stats(success=False, error_type="timeout", error_message="Test timeout")

                    with patch("goesvfi.integrity_check.remote.s3_store.LOGGER.info") as mock_log:
                        log_download_statistics()

                        # Verify logging was called
                        mock_log.assert_called_once()

                        # Check that log call contains relevant statistics
                        log_call_args = mock_log.call_args[0]
                        log_message = str(log_call_args)

                        # Should contain basic stats
                        assert "successful" in log_message.lower() or "total" in log_message.lower()

                        results["log_called"] = True
                        results["log_message_length"] = len(log_message)

                elif scenario_name == "log_with_no_data":
                    # Test logging when no downloads have occurred
                    self.reset_stats()

                    with patch("goesvfi.integrity_check.remote.s3_store.LOGGER.info") as mock_log:
                        log_download_statistics()

                        # Should still log (even if no data)
                        mock_log.assert_called_once()

                        results["empty_log_called"] = True

                return {"scenario": scenario_name, "results": results}

            def _test_batch_operations(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test batch operations scenarios.

                Returns:
                    dict[str, Any]: Test results for batch operations scenarios.
                """
                results = {}

                if scenario_name == "mixed_outcomes":
                    # Test batch of mixed successful/failed downloads
                    self.reset_stats()

                    successful_count = 0
                    failed_count = 0

                    for success, error_type, download_time, file_size, error_message in self.test_scenarios:
                        update_download_stats(
                            success=success,
                            download_time=download_time,
                            file_size=file_size,
                            error_type=error_type,
                            error_message=error_message,
                        )

                        if success:
                            successful_count += 1
                        else:
                            failed_count += 1

                    stats = self.get_current_stats()

                    # Verify final counts
                    assert stats["total_attempts"] == len(self.test_scenarios)
                    assert stats["successful"] == successful_count
                    assert stats["failed"] == failed_count
                    assert stats["successful"] + stats["failed"] == stats["total_attempts"]

                    results["total_scenarios"] = len(self.test_scenarios)
                    results["successful_count"] = successful_count
                    results["failed_count"] = failed_count

                elif scenario_name == "large_batch":
                    # Test large batch processing
                    self.reset_stats()

                    batch_size = 100
                    success_rate = 0.8  # 80% success rate

                    for i in range(batch_size):
                        success = i < (batch_size * success_rate)

                        update_download_stats(
                            success=success,
                            download_time=1.0 + (i % 5) * 0.1,  # Varying download times
                            file_size=100 + (i % 10) * 50,  # Varying file sizes
                            error_type=None if success else "network",
                            error_message=None if success else f"Error {i}",
                        )

                    stats = self.get_current_stats()

                    # Verify batch processing
                    assert stats["total_attempts"] == batch_size
                    assert stats["successful"] == int(batch_size * success_rate)
                    assert stats["failed"] == batch_size - int(batch_size * success_rate)

                    # Error history should be limited to 20
                    assert len(stats["errors"]) == min(20, stats["failed"])

                    results["batch_size"] = batch_size
                    results["success_rate"] = stats["successful"] / stats["total_attempts"]

                return {"scenario": scenario_name, "results": results}

            def _test_edge_cases(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test edge cases and boundary conditions.

                Returns:
                    dict[str, Any]: Test results for edge cases scenarios.
                """
                results = {}

                if scenario_name == "zero_values":
                    # Test with zero/empty values
                    self.reset_stats()

                    edge_cases = [
                        (True, 0.0, 0),  # Zero download time and size
                        (True, 0.001, 1),  # Very small values
                        (False, 0.0, 0),  # Failed with zero values
                    ]

                    for success, download_time, file_size in edge_cases:
                        update_download_stats(
                            success=success,
                            download_time=download_time,
                            file_size=file_size,
                            error_type=None if success else "unknown",
                            error_message=None if success else "Unknown error",
                        )

                    stats = self.get_current_stats()

                    # Should handle edge cases without crashing
                    assert stats["total_attempts"] == len(edge_cases)

                    results["edge_cases_handled"] = len(edge_cases)

                elif scenario_name == "very_large_values":
                    # Test with very large values
                    self.reset_stats()

                    large_values = [
                        (True, 1000.0, 1000000),  # Large time and size
                        (True, 0.001, 50000000),  # Large size, small time
                    ]

                    for success, download_time, file_size in large_values:
                        update_download_stats(success=success, download_time=download_time, file_size=file_size)

                    stats = self.get_current_stats()

                    # Should handle large values
                    assert stats["total_attempts"] == len(large_values)
                    assert stats["largest_file_size"] == 50000000

                    results["large_values_handled"] = True

                return {"scenario": scenario_name, "results": results}

            def _test_performance_validation(self, scenario_name: str, **kwargs: Any) -> dict[str, Any]:
                """Test performance validation scenarios.

                Returns:
                    dict[str, Any]: Test results for performance validation scenarios.
                """
                results = {}

                if scenario_name == "rapid_updates":
                    # Test rapid statistics updates
                    self.reset_stats()

                    start_time = time.time()
                    update_count = 1000

                    for i in range(update_count):
                        update_download_stats(
                            success=i % 2 == 0,  # Alternate success/failure
                            download_time=0.1,
                            file_size=100,
                            error_type=None if i % 2 == 0 else "test",
                            error_message=None if i % 2 == 0 else f"Error {i}",
                        )

                    end_time = time.time()
                    processing_time = end_time - start_time

                    stats = self.get_current_stats()

                    # Verify all updates were processed
                    assert stats["total_attempts"] == update_count
                    assert stats["successful"] == update_count // 2
                    assert stats["failed"] == update_count // 2

                    # Error history should be limited
                    assert len(stats["errors"]) == min(20, stats["failed"])

                    results["updates_processed"] = update_count
                    results["processing_time"] = processing_time
                    results["updates_per_second"] = update_count / processing_time

                return {"scenario": scenario_name, "results": results}

        return {"manager": S3DownloadStatsTestManager()}

    @pytest.fixture(autouse=True)
    def reset_stats_fixture(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Reset stats before each test.

        Yields:
            None: Test execution context.
        """
        manager = s3_stats_test_components["manager"]
        manager.reset_stats()
        yield
        # Cleanup after test
        manager.reset_stats()

    @pytest.mark.parametrize(
        "success,error_type,download_time,file_size,error_message",
        [
            (True, None, 1.0, 100, None),
            (False, "timeout", 5.0, 0, "Connection timeout"),
            (True, None, 0.5, 200, None),
            (False, "network", 2.0, 0, "Network error"),
            (True, None, 2.5, 500, None),
            (False, "not_found", 1.0, 0, "File not found"),
            (False, "auth", 0.1, 0, "Authentication failed"),
            (True, None, 3.0, 1000, None),
        ],
    )
    def test_update_download_stats_scenarios(  # noqa: PLR6301
        self, s3_stats_test_components: dict[str, Any], *, success: bool, error_type: str | None, download_time: float, file_size: int, error_message: str | None
    ) -> None:
        """Test update download stats with various scenarios."""
        manager = s3_stats_test_components["manager"]

        result = manager._test_basic_stats_update(  # noqa: SLF001
            "single_update",
            success=success,
            error_type=error_type,
            download_time=download_time,
            file_size=file_size,
            error_message=error_message,
        )

        assert result["results"]["basic_update_verified"] is True

    def test_basic_stats_update_scenarios(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test basic statistics update scenarios."""
        manager = s3_stats_test_components["manager"]

        basic_scenarios = ["single_update", "parameterized_scenarios"]

        for scenario in basic_scenarios:
            result = manager._test_basic_stats_update(scenario)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_error_history_management_scenarios(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test error history management scenarios."""
        manager = s3_stats_test_components["manager"]

        error_scenarios = ["error_limit_enforcement", "error_type_tracking"]

        for scenario in error_scenarios:
            result = manager._test_error_history_management(scenario)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_download_rate_calculation_scenarios(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test download rate calculation scenarios."""
        manager = s3_stats_test_components["manager"]

        result = manager._test_download_rate_calculation("rate_calculations")  # noqa: SLF001
        assert result["scenario"] == "rate_calculations"
        assert result["results"]["rates_calculated"] == 4
        assert result["results"]["average_rate"] > 0

    def test_file_size_tracking_scenarios(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test file size tracking scenarios."""
        manager = s3_stats_test_components["manager"]

        size_scenarios = ["size_extremes", "size_accumulation"]

        for scenario in size_scenarios:
            result = manager._test_file_size_tracking(scenario)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_time_tracking_scenarios(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test time tracking scenarios."""
        manager = s3_stats_test_components["manager"]

        time_scenarios = ["download_times", "success_time_tracking"]

        for scenario in time_scenarios:
            result = manager._test_time_tracking(scenario)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_statistics_logging_scenarios(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test statistics logging scenarios."""
        manager = s3_stats_test_components["manager"]

        logging_scenarios = ["log_output", "log_with_no_data"]

        for scenario in logging_scenarios:
            result = manager._test_statistics_logging(scenario)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_batch_operations_scenarios(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test batch operations scenarios."""
        manager = s3_stats_test_components["manager"]

        batch_scenarios = ["mixed_outcomes", "large_batch"]

        for scenario in batch_scenarios:
            result = manager._test_batch_operations(scenario)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_edge_case_scenarios(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test edge cases and boundary conditions."""
        manager = s3_stats_test_components["manager"]

        edge_scenarios = ["zero_values", "very_large_values"]

        for scenario in edge_scenarios:
            result = manager._test_edge_cases(scenario)  # noqa: SLF001
            assert result["scenario"] == scenario
            assert len(result["results"]) > 0

    def test_performance_validation_scenarios(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test performance validation scenarios."""
        manager = s3_stats_test_components["manager"]

        result = manager._test_performance_validation("rapid_updates")  # noqa: SLF001
        assert result["scenario"] == "rapid_updates"
        assert result["results"]["updates_processed"] == 1000
        assert result["results"]["updates_per_second"] > 100  # Should be fast

    def test_error_history_limit_validation(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test error history limit enforcement specifically."""
        manager = s3_stats_test_components["manager"]

        result = manager._test_error_history_management("error_limit_enforcement")  # noqa: SLF001
        assert result["results"]["error_limit_verified"] is True

    def test_comprehensive_statistics_validation(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test comprehensive statistics validation."""
        manager = s3_stats_test_components["manager"]

        # Test comprehensive scenario coverage
        result = manager._test_basic_stats_update("parameterized_scenarios")  # noqa: SLF001
        assert result["results"]["scenarios_tested"] == len(manager.test_scenarios)

        # Test error type tracking
        result = manager._test_error_history_management("error_type_tracking")  # noqa: SLF001
        assert result["results"]["error_types_tracked"] == 4

        # Test batch processing
        result = manager._test_batch_operations("large_batch")  # noqa: SLF001
        assert result["results"]["batch_size"] == 100
        assert 0.7 <= result["results"]["success_rate"] <= 0.9  # Should be around 80%

    def test_s3_download_stats_integration_validation(self, s3_stats_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test S3 download stats integration scenarios."""
        manager = s3_stats_test_components["manager"]

        # Test complete workflow
        manager.reset_stats()

        # Simulate mixed download session
        for i in range(20):
            success = i % 3 != 0  # Roughly 67% success rate
            update_download_stats(
                success=success,
                download_time=1.0 + i * 0.1,
                file_size=100 + i * 10,
                error_type=None if success else ["timeout", "network", "not_found"][i % 3],
                error_message=None if success else f"Error {i}",
            )

        stats = manager.get_current_stats()

        # Verify integration
        assert stats["total_attempts"] == 20
        assert stats["successful"] + stats["failed"] == 20
        assert len(stats["download_times"]) == stats["successful"]
        assert len(stats["download_rates"]) == stats["successful"]

        # Test logging integration
        with patch("goesvfi.integrity_check.remote.s3_store.LOGGER.info") as mock_log:
            log_download_statistics()
            mock_log.assert_called_once()
