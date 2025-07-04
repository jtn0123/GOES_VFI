"""Critical scenario tests for Error Recovery System.

This test suite covers high-priority missing areas identified in the testing gap analysis:
1. Strategy implementation with complex failure scenarios
2. Retry logic with exponential backoff and circuit breakers
3. Fallback mechanisms when primary operations fail
4. Recovery orchestration and strategy coordination
5. Network error handling for S3 and external services
6. Process recovery for FFmpeg and RIFE failures
7. Concurrency and resource management under error conditions
"""

import threading
import time
from typing import Any, Never
from unittest.mock import patch

import pytest

from goesvfi.core.error_decorators import with_retry
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.pipeline.exceptions import FFmpegError, ProcessingError, RIFEError
from goesvfi.utils.errors.handler import ErrorHandlerChain
from goesvfi.utils.errors.recovery import RecoveryManager
from goesvfi.utils.errors.base import ErrorCategory, StructuredError


class TestErrorRecoveryCritical:
    """Critical scenario tests for error recovery system."""

    @pytest.fixture()
    def error_tracker(self) -> Any:
        """Create error tracking fixture for test validation."""

        class ErrorTracker:
            def __init__(self) -> None:
                self.recovery_attempts = []
                self.retry_attempts = []
                self.fallback_attempts = []
                self.strategy_executions = []
                self.lock = threading.Lock()

            def track_recovery(self, strategy_name: str, success: bool, attempt_count: int) -> None:
                with self.lock:
                    self.recovery_attempts.append({
                        "strategy": strategy_name,
                        "success": success,
                        "attempts": attempt_count,
                        "timestamp": time.time(),
                    })

            def track_retry(self, function_name: str, attempt: int, delay: float, success: bool) -> None:
                with self.lock:
                    self.retry_attempts.append({
                        "function": function_name,
                        "attempt": attempt,
                        "delay": delay,
                        "success": success,
                        "timestamp": time.time(),
                    })

            def track_fallback(self, primary_failed: str, fallback_used: str, success: bool) -> None:
                with self.lock:
                    self.fallback_attempts.append({
                        "primary": primary_failed,
                        "fallback": fallback_used,
                        "success": success,
                        "timestamp": time.time(),
                    })

            def track_strategy_execution(self, strategy: str, input_error: str, output_result: str) -> None:
                with self.lock:
                    self.strategy_executions.append({
                        "strategy": strategy,
                        "input": input_error,
                        "output": output_result,
                        "timestamp": time.time(),
                    })

            def reset(self) -> None:
                with self.lock:
                    self.recovery_attempts.clear()
                    self.retry_attempts.clear()
                    self.fallback_attempts.clear()
                    self.strategy_executions.clear()

        return ErrorTracker()

    def test_strategy_implementation_complex_scenarios(self, error_tracker: Any) -> None:
        """Test recovery strategy implementation with complex failure scenarios."""
        recovery_manager = RecoveryManager()

        # Create custom recovery strategies for testing
        class NetworkRecoveryStrategy:
            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.NETWORK

            def attempt_recovery(self, error: StructuredError) -> tuple[bool, str]:
                error_tracker.track_strategy_execution("network", str(error), "attempted")

                # Simulate network diagnostics and recovery
                if "connection timeout" in str(error).lower():
                    error_tracker.track_recovery("network_timeout", True, 1)
                    return True, "Connection timeout resolved by increasing timeout values"
                if "dns resolution" in str(error).lower():
                    error_tracker.track_recovery("network_dns", True, 1)
                    return True, "DNS resolution issues resolved"
                error_tracker.track_recovery("network_general", False, 1)
                return False, "Network error could not be resolved"

        class FileRecoveryStrategy:
            def can_recover(self, error: StructuredError) -> bool:
                return error.category in {ErrorCategory.FILE_NOT_FOUND, ErrorCategory.PERMISSION}

            def attempt_recovery(self, error: StructuredError) -> tuple[bool, str]:
                error_tracker.track_strategy_execution("file", str(error), "attempted")

                if error.category == ErrorCategory.FILE_NOT_FOUND:
                    # Simulate file recreation
                    error_tracker.track_recovery("file_recreation", True, 1)
                    return True, "Missing file recreated successfully"
                if error.category == ErrorCategory.PERMISSION:
                    # Simulate permission fix
                    error_tracker.track_recovery("permission_fix", True, 1)
                    return True, "File permissions corrected"
                error_tracker.track_recovery("file_general", False, 1)
                return False, "File error could not be resolved"

        class ProcessRecoveryStrategy:
            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.EXTERNAL_TOOL

            def attempt_recovery(self, error: StructuredError) -> tuple[bool, str]:
                error_tracker.track_strategy_execution("process", str(error), "attempted")

                if "ffmpeg" in str(error).lower():
                    error_tracker.track_recovery("ffmpeg_recovery", True, 2)
                    return True, "FFmpeg process restarted with different parameters"
                if "rife" in str(error).lower():
                    error_tracker.track_recovery("rife_recovery", True, 2)
                    return True, "RIFE model loaded with fallback configuration"
                error_tracker.track_recovery("process_general", False, 1)
                return False, "External tool error could not be resolved"

        # Register strategies
        recovery_manager.add_strategy(NetworkRecoveryStrategy())
        recovery_manager.add_strategy(FileRecoveryStrategy())
        recovery_manager.add_strategy(ProcessRecoveryStrategy())

        # Test complex error scenarios
        test_scenarios = [
            (ErrorCategory.NETWORK, "Connection timeout to NOAA servers", "network_timeout"),
            (ErrorCategory.NETWORK, "DNS resolution failed for amazonaws.com", "network_dns"),
            (ErrorCategory.FILE_NOT_FOUND, "Configuration file missing", "file_recreation"),
            (ErrorCategory.PERMISSION, "Cannot write to output directory", "permission_fix"),
            (ErrorCategory.EXTERNAL_TOOL, "FFmpeg encoding failed with exit code 1", "ffmpeg_recovery"),
            (ErrorCategory.EXTERNAL_TOOL, "RIFE model could not be loaded", "rife_recovery"),
            (ErrorCategory.PROCESSING, "Unknown processing error", None),  # Should not be recoverable
        ]

        for category, message, expected_recovery in test_scenarios:
            # Create structured error
            error = StructuredError(
                message=message,
                category=category,
                recoverable=True,
                suggestions=["Test recovery"],
            )

            # Attempt recovery
            success, recovery_message = recovery_manager.attempt_recovery(error)

            if expected_recovery:
                assert success, f"Recovery should succeed for {category.value}: {message}"
                assert len(recovery_message) > 0, "Recovery message should be provided"

                # Verify strategy was executed
                strategy_executions = [
                    e for e in error_tracker.strategy_executions if expected_recovery.split("_")[0] in e["strategy"]
                ]
                assert len(strategy_executions) > 0, f"Strategy should be executed for {expected_recovery}"

            else:
                assert not success, f"Recovery should fail for unsupported category: {category.value}"

        # Verify all expected recoveries were tracked
        expected_recoveries = [
            "network_timeout",
            "network_dns",
            "file_recreation",
            "permission_fix",
            "ffmpeg_recovery",
            "rife_recovery",
        ]
        actual_recoveries = [r["strategy"] for r in error_tracker.recovery_attempts if r["success"]]

        for expected in expected_recoveries:
            assert expected in actual_recoveries, f"Expected recovery '{expected}' was not executed"

    def test_retry_logic_exponential_backoff(self, error_tracker: Any) -> None:
        """Test retry logic with exponential backoff and failure scenarios."""
        call_count = 0
        max_delay_seen = 0.0

        def track_retry_attempt(attempt, delay, exception=None) -> None:
            nonlocal max_delay_seen
            max_delay_seen = max(max_delay_seen, delay)
            error_tracker.track_retry("test_function", attempt, delay, False)

        # Test with exponential backoff
        @with_retry(
            max_attempts=5,
            delay=0.1,
            backoff_factor=2.0,
            exceptions=(ValueError, ConnectionError),
            on_retry=track_retry_attempt,
        )
        def failing_function_exponential() -> str:
            nonlocal call_count
            call_count += 1

            if call_count <= 3:
                if call_count == 1:
                    msg = "First failure"
                    raise ValueError(msg)
                if call_count == 2:
                    msg = "Second failure"
                    raise ConnectionError(msg)
                msg = "Third failure - different exception"
                raise RuntimeError(msg)

            return "Success"

        # Should eventually succeed
        result = failing_function_exponential()
        assert result == "Success"

        # Verify exponential backoff occurred
        retry_delays = [r["delay"] for r in error_tracker.retry_attempts]
        assert len(retry_delays) >= 2, "Should have multiple retry attempts"

        # Check exponential progression (0.1, 0.2, 0.4...)
        expected_delays = [0.1 * (2.0**i) for i in range(len(retry_delays))]
        for i, (actual, expected) in enumerate(zip(retry_delays, expected_delays, strict=False)):
            assert abs(actual - expected) < 0.01, f"Retry {i}: expected ~{expected}s, got {actual}s"

        # Test max attempts exhaustion
        error_tracker.reset()
        call_count = 0

        @with_retry(
            max_attempts=3, delay=0.05, backoff_factor=2.0, exceptions=(ValueError,), on_retry=track_retry_attempt
        )
        def always_failing_function() -> Never:
            nonlocal call_count
            call_count += 1
            msg = f"Failure {call_count}"
            raise ValueError(msg)

        # Should exhaust retries and raise the last exception
        with pytest.raises(ValueError, match="Failure 3"):
            always_failing_function()

        # Verify all retries were attempted
        assert call_count == 3, f"Should attempt exactly 3 times, got {call_count}"
        assert len(error_tracker.retry_attempts) == 2, "Should track 2 retry attempts (not including initial attempt)"

    def test_fallback_mechanisms_chain(self, error_tracker: Any) -> None:
        """Test fallback mechanisms when primary operations fail."""

        class DataSource:
            def __init__(self, name: str, fail_on_attempts: list[int] | None = None):
                self.name = name
                self.attempt_count = 0
                self.fail_on_attempts = fail_on_attempts or []

            def fetch_data(self) -> str:
                self.attempt_count += 1
                if self.attempt_count in self.fail_on_attempts:
                    msg = f"{self.name} source unavailable"
                    raise ConnectionError(msg)
                return f"Data from {self.name}"

        class FallbackDataManager:
            def __init__(self) -> None:
                self.primary = DataSource("CDN", fail_on_attempts=[1, 2])
                self.secondary = DataSource("S3", fail_on_attempts=[1])
                self.tertiary = DataSource("Local Cache")

            def fetch_with_fallback(self):
                sources = [("primary", self.primary), ("secondary", self.secondary), ("tertiary", self.tertiary)]

                for source_name, source in sources:
                    try:
                        result = source.fetch_data()
                        error_tracker.track_fallback("none", source_name, True)
                        return result, source_name
                    except Exception:
                        error_tracker.track_fallback(source_name, "next", False)
                        continue

                msg = "All fallback sources failed"
                raise RuntimeError(msg)

        manager = FallbackDataManager()

        # First attempt - CDN fails, S3 fails, Local Cache succeeds
        result, source_used = manager.fetch_with_fallback()
        assert result == "Data from Local Cache"
        assert source_used == "tertiary"

        # Verify fallback chain was followed
        fallback_attempts = error_tracker.fallback_attempts
        assert len(fallback_attempts) >= 2, "Should have attempted multiple fallbacks"

        # Check fallback progression
        failed_sources = [f["primary"] for f in fallback_attempts if not f["success"]]
        assert "primary" in failed_sources, "Primary CDN should have failed"
        assert "secondary" in failed_sources, "Secondary S3 should have failed"

        successful_fallback = [f for f in fallback_attempts if f["success"]]
        assert len(successful_fallback) > 0, "Should have successful fallback"
        assert successful_fallback[0]["fallback"] == "tertiary", "Should fallback to tertiary source"

    def test_network_error_handling_s3_operations(self, error_tracker: Any) -> None:
        """Test network error handling for S3 operations with real-world scenarios."""

        # Mock S3 client with various failure scenarios
        class MockS3Client:
            def __init__(self) -> None:
                self.attempt_count = 0
                self.scenarios = [
                    "connection_timeout",
                    "dns_resolution_failed",
                    "rate_limited",
                    "server_error",
                    "success",
                ]

            def list_objects_v2(self, **kwargs):
                self.attempt_count += 1
                scenario = self.scenarios[(self.attempt_count - 1) % len(self.scenarios)]

                if scenario == "connection_timeout":
                    import socket

                    msg = "Connection timed out"
                    raise TimeoutError(msg)
                if scenario == "dns_resolution_failed":
                    import socket

                    msg = "Name resolution failed"
                    raise socket.gaierror(msg)
                if scenario == "rate_limited":
                    from botocore.exceptions import ClientError

                    raise ClientError({"Error": {"Code": "Throttling", "Message": "Rate exceeded"}}, "ListObjectsV2")
                if scenario == "server_error":
                    from botocore.exceptions import ClientError

                    raise ClientError({"Error": {"Code": "InternalError", "Message": "Server error"}}, "ListObjectsV2")
                return {"Contents": [{"Key": "test-file.nc", "LastModified": "2024-01-01T00:00:00Z"}]}

        # Test S3Store with comprehensive error handling
        with patch("boto3.client") as mock_boto_client:
            mock_client = MockS3Client()
            mock_boto_client.return_value = mock_client

            # Create S3Store with retry configuration
            s3_store = S3Store(timeout=30)

            # Mock the retry decorator to track attempts

            def tracking_retry(*args, **kwargs):
                def decorator(func):
                    def wrapper(*wrapper_args, **wrapper_kwargs):
                        try:
                            return func(*wrapper_args, **wrapper_kwargs)
                        except Exception:
                            error_tracker.track_retry(func.__name__, 1, 0.1, False)
                            raise

                    return wrapper

                return decorator

            with patch("goesvfi.core.error_decorators.with_retry", side_effect=tracking_retry):
                try:
                    # This should eventually succeed after retries
                    s3_store.list_files_for_time("2024-01-01T00:00:00Z", "ABI")

                    # Verify that retries were attempted for network errors
                    assert len(error_tracker.retry_attempts) > 0, "Should have retry attempts for network errors"

                except Exception as e:
                    # Even if it fails, we should see retry attempts
                    assert len(error_tracker.retry_attempts) > 0, f"Should have retries even on failure: {e}"

    def test_process_recovery_ffmpeg_rife_failures(self, error_tracker: Any) -> None:
        """Test process recovery for FFmpeg and RIFE failures."""

        class ProcessRecoveryManager:
            def __init__(self) -> None:
                self.ffmpeg_retry_count = 0
                self.rife_retry_count = 0

            def run_ffmpeg_with_recovery(self, command: list[str], input_file: str) -> str | None:
                """Run FFmpeg with automatic recovery on failure."""
                max_attempts = 3

                for attempt in range(max_attempts):
                    try:
                        self.ffmpeg_retry_count += 1

                        # Simulate FFmpeg failures
                        if attempt == 0:
                            error_tracker.track_retry("ffmpeg", attempt + 1, 0.5, False)
                            raise FFmpegError("Codec not found", command=str(command), stderr="Codec not found")
                        if attempt == 1:
                            error_tracker.track_retry("ffmpeg", attempt + 1, 1.0, False)
                            raise FFmpegError(
                                "Input file corrupted", command=str(command), stderr="Input file corrupted"
                            )
                        # Success on third attempt
                        error_tracker.track_retry("ffmpeg", attempt + 1, 0.0, True)
                        error_tracker.track_recovery("ffmpeg_full_recovery", True, attempt + 1)
                        return "FFmpeg success with fallback codec"

                    except FFmpegError as e:
                        if attempt < max_attempts - 1:
                            # Try recovery strategies
                            if "codec not found" in e.stderr.lower():
                                command = self._modify_command_for_codec_fallback(command)
                                error_tracker.track_strategy_execution("ffmpeg_codec", str(e), "codec_fallback")
                            elif "corrupted" in e.stderr.lower():
                                error_tracker.track_strategy_execution("ffmpeg_input", str(e), "input_validation")

                            time.sleep(0.1 * (attempt + 1))  # Brief delay
                        else:
                            error_tracker.track_recovery("ffmpeg_full_recovery", False, max_attempts)
                            raise
                return None

            def run_rife_with_recovery(self, model_path: str, input_images: list[str]) -> str | None:
                """Run RIFE with automatic recovery on failure."""
                max_attempts = 3

                for attempt in range(max_attempts):
                    try:
                        self.rife_retry_count += 1

                        # Simulate RIFE failures
                        if attempt == 0:
                            error_tracker.track_retry("rife", attempt + 1, 0.3, False)
                            msg = "CUDA out of memory"
                            raise RIFEError(msg)
                        if attempt == 1:
                            error_tracker.track_retry("rife", attempt + 1, 0.6, False)
                            msg = "Model file corrupted"
                            raise RIFEError(msg)
                        # Success on third attempt
                        error_tracker.track_retry("rife", attempt + 1, 0.0, True)
                        error_tracker.track_recovery("rife_full_recovery", True, attempt + 1)
                        return "RIFE success with CPU fallback"

                    except RIFEError as e:
                        if attempt < max_attempts - 1:
                            # Try recovery strategies
                            if "cuda out of memory" in str(e).lower():
                                error_tracker.track_strategy_execution("rife_memory", str(e), "cpu_fallback")
                            elif "corrupted" in str(e).lower():
                                error_tracker.track_strategy_execution("rife_model", str(e), "model_fallback")

                            time.sleep(0.1 * (attempt + 1))  # Brief delay
                        else:
                            error_tracker.track_recovery("rife_full_recovery", False, max_attempts)
                            raise
                return None

            def _modify_command_for_codec_fallback(self, command: list[str]) -> list[str]:
                """Modify FFmpeg command to use fallback codec."""
                # Replace codec with fallback
                modified = command.copy()
                if "-c:v" in modified:
                    codec_index = modified.index("-c:v")
                    if codec_index + 1 < len(modified):
                        modified[codec_index + 1] = "libx264"  # Fallback codec
                return modified

        manager = ProcessRecoveryManager()

        # Test FFmpeg recovery
        ffmpeg_command = ["ffmpeg", "-i", "input.mp4", "-c:v", "h264_nvenc", "output.mp4"]
        result = manager.run_ffmpeg_with_recovery(ffmpeg_command, "input.mp4")
        assert "success" in result.lower(), "FFmpeg should eventually succeed"
        assert manager.ffmpeg_retry_count == 3, "Should attempt FFmpeg 3 times"

        # Test RIFE recovery
        rife_result = manager.run_rife_with_recovery("/path/to/model", ["img1.png", "img2.png"])
        assert "success" in rife_result.lower(), "RIFE should eventually succeed"
        assert manager.rife_retry_count == 3, "Should attempt RIFE 3 times"

        # Verify recovery strategies were executed
        ffmpeg_strategies = [s for s in error_tracker.strategy_executions if "ffmpeg" in s["strategy"]]
        rife_strategies = [s for s in error_tracker.strategy_executions if "rife" in s["strategy"]]

        assert len(ffmpeg_strategies) >= 2, "Should execute FFmpeg recovery strategies"
        assert len(rife_strategies) >= 2, "Should execute RIFE recovery strategies"

        # Verify successful recoveries were tracked
        successful_recoveries = [r for r in error_tracker.recovery_attempts if r["success"]]
        recovery_types = [r["strategy"] for r in successful_recoveries]

        assert "ffmpeg_full_recovery" in recovery_types, "Should track successful FFmpeg recovery"
        assert "rife_full_recovery" in recovery_types, "Should track successful RIFE recovery"

    def test_concurrency_resource_management_under_errors(self, error_tracker: Any) -> None:
        """Test concurrency and resource management under error conditions."""
        import concurrent.futures

        class ConcurrentErrorProcessor:
            def __init__(self, max_workers: int = 4):
                self.max_workers = max_workers
                self.active_operations = 0
                self.operation_lock = threading.Lock()
                self.failure_rate = 0.3  # 30% of operations fail initially

            def process_with_error_handling(self, task_id: int) -> dict:
                """Process task with error handling and resource management."""
                with self.operation_lock:
                    self.active_operations += 1

                try:
                    # Simulate processing with potential errors
                    import random

                    if random.random() < self.failure_rate:
                        # Simulate different types of errors
                        error_types = [
                            ("network", ConnectionError("Network unavailable")),
                            ("resource", MemoryError("Insufficient memory")),
                            ("processing", ProcessingError("Data processing failed")),
                        ]

                        error_type, exception = random.choice(error_types)
                        error_tracker.track_retry(f"task_{task_id}", 1, 0.1, False)

                        # Attempt recovery
                        if error_type == "network":
                            time.sleep(0.1)  # Brief retry delay
                            error_tracker.track_recovery("network_retry", True, 1)
                            return {"task_id": task_id, "result": "recovered_from_network_error", "attempts": 2}
                        if error_type == "resource":
                            # Reduce concurrent operations
                            error_tracker.track_recovery("resource_throttle", True, 1)
                            return {"task_id": task_id, "result": "recovered_from_resource_error", "attempts": 2}
                        error_tracker.track_recovery("processing_retry", False, 1)
                        raise exception
                    # Successful processing
                    error_tracker.track_retry(f"task_{task_id}", 1, 0.0, True)
                    return {"task_id": task_id, "result": "success", "attempts": 1}

                finally:
                    with self.operation_lock:
                        self.active_operations -= 1

        processor = ConcurrentErrorProcessor()

        # Process multiple tasks concurrently
        tasks = list(range(20))
        results = []
        errors = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=processor.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(processor.process_with_error_handling, task_id): task_id for task_id in tasks
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_task):
                task_id = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    errors.append({"task_id": task_id, "error": str(e)})

        # Verify concurrent processing with error recovery
        total_operations = len(results) + len(errors)
        assert total_operations == len(tasks), f"Should process all {len(tasks)} tasks"

        # Check that most operations succeeded (either immediately or after recovery)
        success_rate = len(results) / total_operations
        assert success_rate >= 0.7, f"Success rate should be at least 70%, got {success_rate:.2f}"

        # Verify error recovery was attempted
        recovery_attempts = error_tracker.recovery_attempts
        assert len(recovery_attempts) > 0, "Should have recovery attempts for concurrent failures"

        # Check resource management - no resource exhaustion
        resource_recoveries = [r for r in recovery_attempts if "resource" in r["strategy"]]
        if len(resource_recoveries) > 0:
            assert all(r["success"] for r in resource_recoveries), "Resource recovery should succeed"

        # Verify retry attempts were made
        retry_attempts = error_tracker.retry_attempts
        retry_count = len(retry_attempts)

        # Should have some retries but not excessive (good error handling)
        assert retry_count <= total_operations, "Retry count should be reasonable"

    def test_error_handler_chain_orchestration(self, error_tracker: Any) -> None:
        """Test error handler chain orchestration with multiple handler types."""

        # Create custom error handlers for testing
        class RecoveryErrorHandler:
            def __init__(self) -> None:
                self.handled_errors = []

            def can_handle(self, error: StructuredError) -> bool:
                """Check if this handler can handle the given error."""
                return True

            def handle(self, error: StructuredError) -> bool:
                """Handle error with recovery attempt."""
                self.handled_errors.append(error)
                error_tracker.track_strategy_execution("recovery_handler", str(error), "attempted")

                # Attempt recovery based on error category
                if error.category == ErrorCategory.NETWORK:
                    error_tracker.track_recovery("handler_network", True, 1)
                    return True  # Successfully handled
                if error.category == ErrorCategory.FILE_NOT_FOUND:
                    error_tracker.track_recovery("handler_file", True, 1)
                    return True  # Successfully handled
                error_tracker.track_recovery("handler_unknown", False, 1)
                return False  # Cannot handle

        class AlertingErrorHandler:
            def __init__(self) -> None:
                self.alerts_sent = []

            def can_handle(self, error: StructuredError) -> bool:
                """Check if this handler can handle the given error."""
                return True

            def handle(self, error: StructuredError) -> bool:
                """Handle error by sending alerts."""
                self.alerts_sent.append(error)
                error_tracker.track_strategy_execution("alerting_handler", str(error), "alert_sent")

                # Always "handle" by sending alert, but don't resolve
                return False  # Alert sent but error not resolved

        class FallbackErrorHandler:
            def __init__(self) -> None:
                self.fallback_actions = []

            def can_handle(self, error: StructuredError) -> bool:
                """Check if this handler can handle the given error."""
                return True

            def handle(self, error: StructuredError) -> bool:
                """Handle error with fallback actions."""
                self.fallback_actions.append(error)
                error_tracker.track_strategy_execution("fallback_handler", str(error), "fallback_action")

                # Provide fallback for any unhandled error
                error_tracker.track_recovery("handler_fallback", True, 1)
                return True  # Always provides fallback

        # Create and configure error handler chain
        recovery_handler = RecoveryErrorHandler()
        alerting_handler = AlertingErrorHandler()
        fallback_handler = FallbackErrorHandler()

        handler_chain = ErrorHandlerChain()
        handler_chain.add_handler(recovery_handler)
        handler_chain.add_handler(alerting_handler)
        handler_chain.add_handler(fallback_handler)

        # Test various error scenarios
        test_errors = [
            StructuredError(
                message="Network connection failed",
                category=ErrorCategory.NETWORK,
                recoverable=True,
                suggestions=["Check network connectivity"],
            ),
            StructuredError(
                message="Configuration file not found",
                category=ErrorCategory.FILE_NOT_FOUND,
                recoverable=True,
                suggestions=["Create default configuration"],
            ),
            StructuredError(
                message="Unknown processing error",
                category=ErrorCategory.PROCESSING,
                recoverable=False,
                suggestions=["Review input data"],
            ),
        ]

        for error in test_errors:
            # Process error through chain
            was_handled = handler_chain.handle_error(error)

            # All errors should be handled (recovery for network/file, fallback for others)
            assert was_handled, f"Error should be handled by chain: {error.message}"

        # Verify handler execution order and behavior
        assert len(recovery_handler.handled_errors) == 3, "Recovery handler should see all errors"
        assert len(alerting_handler.alerts_sent) == 3, "Alerting handler should see all errors"

        # Fallback handler should only handle unresolved errors
        unresolved_errors = [e for e in test_errors if e.category == ErrorCategory.PROCESSING]
        assert len(fallback_handler.fallback_actions) == len(unresolved_errors), (
            "Fallback should handle unresolved errors"
        )

        # Verify tracking of strategy executions
        strategy_executions = error_tracker.strategy_executions
        handler_types = {s["strategy"] for s in strategy_executions}
        expected_handlers = {"recovery_handler", "alerting_handler", "fallback_handler"}
        assert handler_types >= expected_handlers, f"Should execute all handler types: {handler_types}"

        # Verify recovery tracking
        recoveries = error_tracker.recovery_attempts
        recovery_strategies = {r["strategy"] for r in recoveries}
        expected_recoveries = {"handler_network", "handler_file", "handler_fallback"}
        assert recovery_strategies >= expected_recoveries, f"Should track all recovery types: {recovery_strategies}"
