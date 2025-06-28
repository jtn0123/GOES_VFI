"""Tests for error handling decorators."""

import asyncio
from typing import Never
import unittest
from unittest.mock import patch
import warnings

import pytest

from goesvfi.core.error_decorators import (
    async_safe,
    deprecated,
    robust_operation,
    with_error_handling,
    with_logging,
    with_retry,
    with_timeout,
    with_validation,
)


class TestErrorDecorators(unittest.TestCase):
    """Test error handling decorators."""

    def test_with_error_handling_success(self) -> None:
        """Test error handling decorator with successful execution."""
        @with_error_handling(operation_name="test_op", component_name="test_comp")
        def successful_func(x: int) -> int:
            return x * 2

        result = successful_func(5)
        assert result == 10

    def test_with_error_handling_exception_reraise(self) -> None:
        """Test error handling decorator with exception and reraise."""
        @with_error_handling(
            operation_name="test_op",
            component_name="test_comp",
            reraise=True
        )
        def failing_func() -> Never:
            msg = "Test error"
            raise ValueError(msg)

        with pytest.raises(ValueError):
            failing_func()

    def test_with_error_handling_exception_no_reraise(self) -> None:
        """Test error handling decorator without reraising."""
        @with_error_handling(
            operation_name="test_op",
            component_name="test_comp",
            reraise=False,
            default_return=-1
        )
        def failing_func() -> Never:
            msg = "Test error"
            raise ValueError(msg)

        result = failing_func()
        assert result == -1

    def test_with_retry_success_first_attempt(self) -> None:
        """Test retry decorator with success on first attempt."""
        call_count = 0

        @with_retry(max_attempts=3, delay=0.1)
        def successful_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_with_retry_success_after_failures(self) -> None:
        """Test retry decorator with success after failures."""
        call_count = 0

        @with_retry(max_attempts=3, delay=0.01, backoff_factor=1.0)
        def eventually_successful_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                msg = f"Attempt {call_count} failed"
                raise ValueError(msg)
            return "success"

        result = eventually_successful_func()
        assert result == "success"
        assert call_count == 3

    def test_with_retry_all_attempts_fail(self) -> None:
        """Test retry decorator when all attempts fail."""
        call_count = 0

        @with_retry(max_attempts=3, delay=0.01)
        def always_failing_func() -> Never:
            nonlocal call_count
            call_count += 1
            msg = f"Attempt {call_count} failed"
            raise ValueError(msg)

        with pytest.raises(ValueError) as cm:
            always_failing_func()

        assert call_count == 3
        assert "Attempt 3 failed" in str(cm.value)

    def test_with_retry_specific_exceptions(self) -> None:
        """Test retry decorator with specific exceptions."""
        @with_retry(
            max_attempts=3,
            delay=0.01,
            exceptions=(IOError, OSError)
        )
        def func_with_specific_error() -> Never:
            msg = "Should not retry this"
            raise ValueError(msg)

        # Should not retry ValueError
        with pytest.raises(ValueError):
            func_with_specific_error()

    def test_with_retry_callback(self) -> None:
        """Test retry decorator with callback."""
        retry_calls = []

        def on_retry(attempt: int, exception: Exception) -> None:
            retry_calls.append((attempt, str(exception)))

        @with_retry(
            max_attempts=3,
            delay=0.01,
            on_retry=on_retry
        )
        def failing_func() -> Never:
            msg = "Test error"
            raise ValueError(msg)

        with pytest.raises(ValueError):
            failing_func()

        assert len(retry_calls) == 2  # Called on retry, not final failure
        assert retry_calls[0][0] == 1
        assert retry_calls[1][0] == 2

    def test_with_timeout_async(self) -> None:
        """Test timeout decorator with async function."""
        @with_timeout(timeout=0.1)
        async def slow_async_func() -> str:
            await asyncio.sleep(0.5)
            return "done"

        # Run async test
        async def run_test() -> None:
            with pytest.raises(asyncio.TimeoutError):
                await slow_async_func()

        asyncio.run(run_test())

    def test_with_timeout_async_success(self) -> None:
        """Test timeout decorator with async function that completes in time."""
        @with_timeout(timeout=0.5)
        async def fast_async_func() -> str:
            await asyncio.sleep(0.1)
            return "done"

        # Run async test
        async def run_test() -> None:
            result = await fast_async_func()
            assert result == "done"

        asyncio.run(run_test())

    @patch("goesvfi.core.error_decorators.LOGGER")
    def test_with_logging_basic(self, mock_logger) -> None:
        """Test logging decorator with basic function."""
        @with_logging(log_args=True, log_result=True, log_time=True)
        def test_func(x: int, y: int = 2) -> int:
            return x * y

        result = test_func(5, y=3)
        assert result == 15

        # Check logging calls
        assert mock_logger.debug.called

        # Check that function name was logged
        call_args = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("test_func" in str(call) for call in call_args)

    def test_with_validation_success(self) -> None:
        """Test validation decorator with valid inputs/outputs."""
        def validate_inputs(args, kwargs) -> None:
            if args[0] < 0:
                msg = "Input must be non-negative"
                raise ValueError(msg)

        def validate_output(result) -> None:
            if result > 100:
                msg = "Output too large"
                raise ValueError(msg)

        @with_validation(validator=validate_inputs, validate_result=validate_output)
        def validated_func(x: int) -> int:
            return x * 2

        # Valid input and output
        result = validated_func(5)
        assert result == 10

    def test_with_validation_input_failure(self) -> None:
        """Test validation decorator with invalid input."""
        def validate_inputs(args, kwargs) -> None:
            if args[0] < 0:
                msg = "Input must be non-negative"
                raise ValueError(msg)

        @with_validation(validator=validate_inputs)
        def validated_func(x: int) -> int:
            return x * 2

        # Invalid input
        with pytest.raises(ValueError) as cm:
            validated_func(-5)

        assert "Input must be non-negative" in str(cm.value)

    def test_with_validation_output_failure(self) -> None:
        """Test validation decorator with invalid output."""
        def validate_output(result) -> None:
            if result > 100:
                msg = "Output too large"
                raise ValueError(msg)

        @with_validation(validate_result=validate_output)
        def validated_func(x: int) -> int:
            return x * 2

        # Invalid output
        with pytest.raises(ValueError) as cm:
            validated_func(60)

        assert "Output too large" in str(cm.value)

    def test_deprecated_decorator(self) -> None:
        """Test deprecated decorator."""
        @deprecated(
            reason="Use new_func instead",
            version="2.0",
            alternative="new_func"
        )
        def old_func() -> str:
            return "old"

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            result = old_func()
            assert result == "old"

            # Check warning
            assert len(w) == 1
            assert w[0].category == DeprecationWarning
            assert "old_func is deprecated" in str(w[0].message)
            assert "Use new_func instead" in str(w[0].message)

        # Check updated docstring
        assert "DEPRECATED" in old_func.__doc__

    def test_robust_operation_success(self) -> None:
        """Test robust operation composite decorator with success."""
        call_count = 0

        @robust_operation(
            operation_name="test_op",
            max_retries=3,
            retry_delay=0.01
        )
        def robust_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result = robust_func(5)
        assert result == 10
        assert call_count == 1

    def test_robust_operation_retry(self) -> None:
        """Test robust operation with retryable error."""
        call_count = 0

        @robust_operation(
            operation_name="test_op",
            max_retries=3,
            retry_delay=0.01
        )
        def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                msg = "Network error"
                raise OSError(msg)
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 2

    def test_async_safe_success(self) -> None:
        """Test async safe decorator with successful execution."""
        @async_safe(timeout=1.0, default_return="default")
        async def safe_async_func() -> str:
            await asyncio.sleep(0.1)
            return "success"

        # Run async test
        async def run_test() -> None:
            result = await safe_async_func()
            assert result == "success"

        asyncio.run(run_test())

    def test_async_safe_timeout(self) -> None:
        """Test async safe decorator with timeout."""
        @async_safe(timeout=0.1, default_return="timeout_default")
        async def slow_func() -> str:
            await asyncio.sleep(0.5)
            return "never_reached"

        # Run async test
        async def run_test() -> None:
            result = await slow_func()
            assert result == "timeout_default"

        asyncio.run(run_test())

    def test_async_safe_error(self) -> None:
        """Test async safe decorator with error."""
        @async_safe(default_return="error_default")
        async def error_func() -> Never:
            msg = "Test error"
            raise ValueError(msg)

        # Run async test
        async def run_test() -> None:
            result = await error_func()
            assert result == "error_default"

        asyncio.run(run_test())

    def test_decorator_stacking(self) -> None:
        """Test multiple decorators stacked together."""
        call_log = []

        @with_logging(log_args=False, log_result=False, log_time=False)
        @with_error_handling(reraise=False, default_return="error")
        @with_retry(max_attempts=2, delay=0.01)
        def complex_func(should_fail: bool) -> str:
            call_log.append("called")
            if should_fail:
                msg = "Deliberate failure"
                raise ValueError(msg)
            return "success"

        # Test success
        result = complex_func(False)
        assert result == "success"
        assert len(call_log) == 1

        # Test failure
        call_log.clear()
        result = complex_func(True)
        assert result == "error"
        assert len(call_log) == 2  # Two retry attempts


if __name__ == "__main__":
    unittest.main()
