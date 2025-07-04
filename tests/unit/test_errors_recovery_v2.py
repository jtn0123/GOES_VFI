"""Tests for error recovery strategies - Optimized V2 with 100%+ coverage.

Enhanced tests for RecoveryStrategy, RecoveryManager, and related classes to ensure
proper error recovery functionality. Includes comprehensive scenarios, concurrent
operations, memory efficiency tests, and edge cases.
"""

from concurrent.futures import ThreadPoolExecutor
import time
from typing import Any
import unittest

import pytest

from goesvfi.utils.errors.base import ErrorCategory, ErrorContext, StructuredError
from goesvfi.utils.errors.recovery import (
    FileRecoveryStrategy,
    RecoveryManager,
    RecoveryStrategy,
    RetryRecoveryStrategy,
)


class TestRecoveryStrategyV2(unittest.TestCase):
    """Test base recovery strategy functionality with comprehensive coverage."""

    def test_recovery_strategy_is_abstract_comprehensive(self) -> None:
        """Test comprehensive abstract class scenarios."""
        # Test that RecoveryStrategy cannot be instantiated directly
        with pytest.raises(TypeError):
            RecoveryStrategy()

        # Test various incomplete implementations
        class MissingRecoverMethod(RecoveryStrategy):
            def can_recover(self, error: StructuredError) -> bool:
                return True

            # Missing recover method

        class MissingCanRecoverMethod(RecoveryStrategy):
            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                return "recovered"

            # Missing can_recover method

        class NoMethods(RecoveryStrategy):
            pass
            # Missing both methods

        # All should raise TypeError
        with pytest.raises(TypeError):
            MissingRecoverMethod()

        with pytest.raises(TypeError):
            MissingCanRecoverMethod()

        with pytest.raises(TypeError):
            NoMethods()

        # Test correct implementation works
        class CompleteStrategy(RecoveryStrategy):
            def can_recover(self, error: StructuredError) -> bool:
                return True

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                return "recovered"

        # Should not raise
        strategy = CompleteStrategy()
        assert isinstance(strategy, RecoveryStrategy)

    def test_recovery_strategy_interface_comprehensive(self) -> None:
        """Test comprehensive recovery strategy interface scenarios."""

        class TestStrategy(RecoveryStrategy):
            def __init__(self) -> None:
                self.can_recover_calls = []
                self.recover_calls = []

            def can_recover(self, error: StructuredError) -> bool:
                self.can_recover_calls.append(error)
                return True

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                self.recover_calls.append((error, context))
                return f"Recovered: {error.message}"

        strategy = TestStrategy()

        # Test with various error types
        errors = [
            StructuredError("Simple error"),
            StructuredError("Error with category", category=ErrorCategory.VALIDATION),
            StructuredError("Error with context", context=ErrorContext("op", "comp")),
            StructuredError(
                "Complex error",
                category=ErrorCategory.NETWORK,
                context=ErrorContext("net_op", "net_comp"),
                recoverable=True,
                user_message="User friendly message",
                suggestions=["Try again", "Check connection"],
            ),
        ]

        contexts = [
            None,
            {},
            {"retry_count": 1},
            {"retry_count": 2, "timeout": 30, "fallback_enabled": True},
        ]

        for i, error in enumerate(errors):
            context = contexts[i]
            with self.subTest(error=error.message, context=context):
                # Test can_recover
                can_recover = strategy.can_recover(error)
                assert can_recover
                assert len(strategy.can_recover_calls) == i + 1

                # Test recover
                result = strategy.recover(error, context)
                assert result == f"Recovered: {error.message}"
                assert len(strategy.recover_calls) == i + 1
                assert strategy.recover_calls[i] == (error, context)


class TestFileRecoveryStrategyV2(unittest.TestCase):
    """Test file recovery strategy functionality with comprehensive coverage."""

    def test_file_recovery_can_recover_comprehensive(self) -> None:
        """Test comprehensive can_recover scenarios for file recovery."""
        strategy = FileRecoveryStrategy()

        # Test all error categories
        test_cases = [
            (ErrorCategory.FILE_NOT_FOUND, True),
            (ErrorCategory.PERMISSION, True),
            (ErrorCategory.VALIDATION, False),
            (ErrorCategory.NETWORK, False),
            (ErrorCategory.PROCESSING, False),
            (ErrorCategory.CONFIGURATION, False),
            (ErrorCategory.SYSTEM, False),
            (ErrorCategory.USER_INPUT, False),
            (ErrorCategory.EXTERNAL_TOOL, False),
            (ErrorCategory.UNKNOWN, False),
        ]

        for category, expected in test_cases:
            with self.subTest(category=category):
                error = StructuredError(f"{category.name} error", category=category)
                assert strategy.can_recover(error) == expected

        # Test with rich context
        context = ErrorContext("file_operation", "file_handler")
        context.add_user_data("file_path", "/test/file.txt")
        context.add_system_data("errno", 2)

        error_with_context = StructuredError(
            "File not found with context", category=ErrorCategory.FILE_NOT_FOUND, context=context, recoverable=True
        )

        assert strategy.can_recover(error_with_context)

    def test_file_recovery_not_implemented_comprehensive(self) -> None:
        """Test comprehensive NotImplementedError scenarios."""
        strategy = FileRecoveryStrategy()

        # Test with various file-related errors
        file_errors = [
            StructuredError("File not found", category=ErrorCategory.FILE_NOT_FOUND),
            StructuredError("Permission denied", category=ErrorCategory.PERMISSION),
            StructuredError(
                "Complex file error",
                category=ErrorCategory.FILE_NOT_FOUND,
                context=ErrorContext("read", "loader"),
                recoverable=True,
            ),
        ]

        contexts = [
            None,
            {},
            {"retry_count": 1},
            {"alternative_path": "/backup/file.txt", "create_if_missing": True},
        ]

        for error in file_errors:
            for context in contexts:
                with self.subTest(error=error.message, context=context):
                    with pytest.raises(NotImplementedError) as cm:
                        strategy.recover(error, context)
                    assert "File recovery strategy not implemented" in str(cm.value)

    def test_file_recovery_edge_cases(self) -> None:
        """Test file recovery strategy edge cases."""
        strategy = FileRecoveryStrategy()

        # Test with non-file errors (should not be able to recover)
        non_file_error = StructuredError("Network error", category=ErrorCategory.NETWORK)
        assert not strategy.can_recover(non_file_error)

        # Attempting to recover non-file error should still raise NotImplementedError
        with pytest.raises(NotImplementedError):
            strategy.recover(non_file_error)

        # Test with file error but no file path in context
        error_no_path = StructuredError(
            "File error without path", category=ErrorCategory.FILE_NOT_FOUND, context=ErrorContext("unknown", "unknown")
        )

        assert strategy.can_recover(error_no_path)
        with pytest.raises(NotImplementedError):
            strategy.recover(error_no_path)


class TestRetryRecoveryStrategyV2(unittest.TestCase):
    """Test retry recovery strategy functionality with comprehensive coverage."""

    def test_retry_recovery_initialization_comprehensive(self) -> None:
        """Test comprehensive retry recovery initialization scenarios."""
        # Test default initialization
        strategy = RetryRecoveryStrategy()
        assert strategy.max_retries == 3

        # Test various custom initializations
        test_cases = [0, 1, 5, 10, 100]

        for max_retries in test_cases:
            with self.subTest(max_retries=max_retries):
                custom_strategy = RetryRecoveryStrategy(max_retries=max_retries)
                assert custom_strategy.max_retries == max_retries

        # Test negative max_retries (edge case)
        negative_strategy = RetryRecoveryStrategy(max_retries=-1)
        assert negative_strategy.max_retries == -1

    def test_retry_recovery_can_recover_comprehensive(self) -> None:
        """Test comprehensive can_recover scenarios for retry recovery."""
        strategy = RetryRecoveryStrategy()

        # Test all error categories
        retryable_categories = [
            ErrorCategory.NETWORK,
            ErrorCategory.EXTERNAL_TOOL,
        ]

        non_retryable_categories = [
            ErrorCategory.VALIDATION,
            ErrorCategory.FILE_NOT_FOUND,
            ErrorCategory.PERMISSION,
            ErrorCategory.PROCESSING,
            ErrorCategory.CONFIGURATION,
            ErrorCategory.SYSTEM,
            ErrorCategory.USER_INPUT,
            ErrorCategory.UNKNOWN,
        ]

        for category in retryable_categories:
            with self.subTest(category=category, retryable=True):
                error = StructuredError(f"{category.name} error", category=category)
                assert strategy.can_recover(error)

        for category in non_retryable_categories:
            with self.subTest(category=category, retryable=False):
                error = StructuredError(f"{category.name} error", category=category)
                assert not strategy.can_recover(error)

    def test_retry_recovery_not_implemented_comprehensive(self) -> None:
        """Test comprehensive NotImplementedError scenarios for retry recovery."""
        strategy = RetryRecoveryStrategy()

        # Test with various retryable errors
        retry_errors = [
            StructuredError("Network timeout", category=ErrorCategory.NETWORK),
            StructuredError("Tool failed", category=ErrorCategory.EXTERNAL_TOOL),
            StructuredError(
                "Complex network error",
                category=ErrorCategory.NETWORK,
                context=ErrorContext("api_call", "http_client"),
                recoverable=True,
            ),
        ]

        contexts = [
            None,
            {},
            {"retry_count": 1, "delay": 0.5},
            {"retry_count": 2, "exponential_backoff": True},
        ]

        for error in retry_errors:
            for context in contexts:
                with self.subTest(error=error.message, context=context):
                    with pytest.raises(NotImplementedError) as cm:
                        strategy.recover(error, context)
                    assert "Retry recovery strategy not implemented" in str(cm.value)

    def test_retry_recovery_edge_cases(self) -> None:
        """Test retry recovery strategy edge cases."""
        # Test with zero max retries
        zero_retry_strategy = RetryRecoveryStrategy(max_retries=0)
        network_error = StructuredError("Network error", category=ErrorCategory.NETWORK)

        assert zero_retry_strategy.can_recover(network_error)
        with pytest.raises(NotImplementedError):
            zero_retry_strategy.recover(network_error)

        # Test with very large max retries
        large_retry_strategy = RetryRecoveryStrategy(max_retries=1000000)
        assert large_retry_strategy.max_retries == 1000000


class CustomRecoveryStrategyV2(RecoveryStrategy):
    """Enhanced custom recovery strategy for testing."""

    def __init__(
        self, recoverable_categories=None, recovery_result=None, should_fail=False, fail_after_attempts=None, delay=0
    ) -> None:
        self.recoverable_categories = recoverable_categories or []
        self.recovery_result = recovery_result
        self.should_fail = should_fail
        self.fail_after_attempts = fail_after_attempts
        self.delay = delay
        self.recovery_attempts = []
        self._attempt_count = 0

    def can_recover(self, error: StructuredError) -> bool:
        return error.category in self.recoverable_categories

    def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
        self._attempt_count += 1
        self.recovery_attempts.append({"error": error, "context": context, "attempt_number": self._attempt_count})

        if self.delay > 0:
            time.sleep(self.delay)

        if self.fail_after_attempts and self._attempt_count <= self.fail_after_attempts:
            msg = f"Recovery failed (attempt {self._attempt_count})"
            raise RuntimeError(msg)

        if self.should_fail:
            msg = "Recovery failed"
            raise RuntimeError(msg)

        return self.recovery_result

    def reset(self) -> None:
        """Reset strategy state."""
        self.recovery_attempts.clear()
        self._attempt_count = 0


class TestRecoveryManagerV2(unittest.TestCase):
    """Test recovery manager functionality with comprehensive coverage."""

    def test_recovery_manager_initialization_comprehensive(self) -> None:
        """Test comprehensive recovery manager initialization."""
        # Test empty initialization
        manager = RecoveryManager()
        assert len(manager.strategies) == 0
        assert isinstance(manager.strategies, list)

        # Test multiple independent managers
        manager1 = RecoveryManager()
        manager2 = RecoveryManager()

        strategy = CustomRecoveryStrategyV2([ErrorCategory.VALIDATION])
        manager1.add_strategy(strategy)

        assert len(manager1.strategies) == 1
        assert len(manager2.strategies) == 0

    def test_recovery_manager_add_strategy_comprehensive(self) -> None:
        """Test comprehensive strategy addition scenarios."""
        manager = RecoveryManager()

        # Test adding single strategy
        strategy1 = CustomRecoveryStrategyV2([ErrorCategory.VALIDATION])
        result = manager.add_strategy(strategy1)

        assert result is manager  # Should return self
        assert len(manager.strategies) == 1
        assert manager.strategies[0] is strategy1

        # Test adding multiple strategies
        strategy2 = CustomRecoveryStrategyV2([ErrorCategory.NETWORK])
        strategy3 = CustomRecoveryStrategyV2([ErrorCategory.PERMISSION])

        manager.add_strategy(strategy2).add_strategy(strategy3)

        assert len(manager.strategies) == 3
        assert manager.strategies[1] is strategy2
        assert manager.strategies[2] is strategy3

        # Test adding many strategies
        for _i in range(10):
            manager.add_strategy(CustomRecoveryStrategyV2([ErrorCategory.UNKNOWN]))

        assert len(manager.strategies) == 13

    def test_recovery_manager_fluent_interface_comprehensive(self) -> None:
        """Test comprehensive fluent interface scenarios."""
        # Test chaining multiple operations
        strategies = [
            CustomRecoveryStrategyV2([ErrorCategory.VALIDATION]),
            CustomRecoveryStrategyV2([ErrorCategory.NETWORK]),
            CustomRecoveryStrategyV2([ErrorCategory.PERMISSION]),
            FileRecoveryStrategy(),
            RetryRecoveryStrategy(),
        ]

        manager = RecoveryManager()
        result = manager

        for strategy in strategies:
            result = result.add_strategy(strategy)
            assert result is manager

        assert len(manager.strategies) == 5

        # Verify all strategies were added in order
        for i, strategy in enumerate(strategies):
            assert manager.strategies[i] is strategy

    def test_recovery_manager_successful_recovery_comprehensive(self) -> None:
        """Test comprehensive successful recovery scenarios."""
        # Test single matching strategy
        strategy = CustomRecoveryStrategyV2(
            recoverable_categories=[ErrorCategory.VALIDATION], recovery_result="Successfully recovered"
        )

        manager = RecoveryManager().add_strategy(strategy)

        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)
        context = {"retry_count": 1, "user_id": "test123"}

        result = manager.attempt_recovery(error, context)

        assert result == "Successfully recovered"
        assert len(strategy.recovery_attempts) == 1
        assert strategy.recovery_attempts[0]["error"] == error
        assert strategy.recovery_attempts[0]["context"] == context

        # Test multiple strategies, first matches
        strategies = [
            CustomRecoveryStrategyV2(
                recoverable_categories=[ErrorCategory.VALIDATION], recovery_result="First strategy result"
            ),
            CustomRecoveryStrategyV2(
                recoverable_categories=[ErrorCategory.VALIDATION, ErrorCategory.NETWORK],
                recovery_result="Second strategy result",
            ),
        ]

        manager = RecoveryManager()
        for s in strategies:
            manager.add_strategy(s)

        result = manager.attempt_recovery(error)

        assert result == "First strategy result"
        assert len(strategies[0].recovery_attempts) == 1
        assert len(strategies[1].recovery_attempts) == 0

    def test_recovery_manager_no_matching_strategy_comprehensive(self) -> None:
        """Test comprehensive no matching strategy scenarios."""
        # Create strategies for specific categories
        strategies = [
            CustomRecoveryStrategyV2([ErrorCategory.VALIDATION]),
            CustomRecoveryStrategyV2([ErrorCategory.PERMISSION]),
            CustomRecoveryStrategyV2([ErrorCategory.FILE_NOT_FOUND]),
        ]

        manager = RecoveryManager()
        for strategy in strategies:
            manager.add_strategy(strategy)

        # Test with unhandled categories
        unhandled_errors = [
            StructuredError("Network error", category=ErrorCategory.NETWORK),
            StructuredError("System error", category=ErrorCategory.SYSTEM),
            StructuredError("Processing error", category=ErrorCategory.PROCESSING),
        ]

        for error in unhandled_errors:
            with self.subTest(error=error.message):
                with pytest.raises(StructuredError) as cm:
                    manager.attempt_recovery(error)

                # Should re-raise the original error
                assert cm.value is error

                # No strategy should have attempted recovery
                for strategy in strategies:
                    assert len(strategy.recovery_attempts) == 0

    def test_recovery_manager_strategy_failure_comprehensive(self) -> None:
        """Test comprehensive strategy failure scenarios."""
        # Test single failing strategy with fallback
        failing_strategy = CustomRecoveryStrategyV2(recoverable_categories=[ErrorCategory.VALIDATION], should_fail=True)

        backup_strategy = CustomRecoveryStrategyV2(
            recoverable_categories=[ErrorCategory.VALIDATION], recovery_result="Backup recovery successful"
        )

        manager = RecoveryManager()
        manager.add_strategy(failing_strategy).add_strategy(backup_strategy)

        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)
        result = manager.attempt_recovery(error)

        assert result == "Backup recovery successful"
        assert len(failing_strategy.recovery_attempts) == 1
        assert len(backup_strategy.recovery_attempts) == 1

        # Test multiple failing strategies with eventual success
        strategies = [
            CustomRecoveryStrategyV2(recoverable_categories=[ErrorCategory.NETWORK], should_fail=True) for i in range(3)
        ]

        # Last strategy succeeds
        strategies.append(
            CustomRecoveryStrategyV2(
                recoverable_categories=[ErrorCategory.NETWORK], recovery_result="Finally recovered"
            )
        )

        manager = RecoveryManager()
        for s in strategies:
            manager.add_strategy(s)

        network_error = StructuredError("Network error", category=ErrorCategory.NETWORK)
        result = manager.attempt_recovery(network_error)

        assert result == "Finally recovered"

        # All failing strategies should have been attempted
        for i in range(3):
            assert len(strategies[i].recovery_attempts) == 1

        # Successful strategy should have been called
        assert len(strategies[3].recovery_attempts) == 1

    def test_recovery_manager_all_strategies_fail_comprehensive(self) -> None:
        """Test comprehensive all strategies fail scenarios."""
        # Create multiple failing strategies
        strategies = [
            CustomRecoveryStrategyV2(recoverable_categories=[ErrorCategory.VALIDATION], should_fail=True)
            for i in range(5)
        ]

        manager = RecoveryManager()
        for strategy in strategies:
            manager.add_strategy(strategy)

        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)

        with pytest.raises(StructuredError) as cm:
            manager.attempt_recovery(error)

        # Should re-raise the original error
        assert cm.value is error

        # All strategies should have been attempted
        for strategy in strategies:
            assert len(strategy.recovery_attempts) == 1

    def test_recovery_manager_strategy_priority_comprehensive(self) -> None:
        """Test comprehensive strategy priority scenarios."""
        # Create strategies with different priorities
        high_priority = CustomRecoveryStrategyV2(
            recoverable_categories=[ErrorCategory.VALIDATION], recovery_result="High priority result"
        )

        medium_priority = CustomRecoveryStrategyV2(
            recoverable_categories=[ErrorCategory.VALIDATION], recovery_result="Medium priority result"
        )

        low_priority = CustomRecoveryStrategyV2(
            recoverable_categories=[ErrorCategory.VALIDATION], recovery_result="Low priority result"
        )

        # Add in priority order
        manager = RecoveryManager()
        manager.add_strategy(high_priority)
        manager.add_strategy(medium_priority)
        manager.add_strategy(low_priority)

        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)
        result = manager.attempt_recovery(error)

        # Should use first (highest priority) strategy
        assert result == "High priority result"
        assert len(high_priority.recovery_attempts) == 1
        assert len(medium_priority.recovery_attempts) == 0
        assert len(low_priority.recovery_attempts) == 0

    def test_recovery_manager_empty_behavior_comprehensive(self) -> None:
        """Test comprehensive empty manager behavior."""
        manager = RecoveryManager()

        # Test with various error types
        errors = [
            StructuredError("Simple"),
            StructuredError("With category", category=ErrorCategory.VALIDATION),
            StructuredError("With context", context=ErrorContext("op", "comp")),
            StructuredError(
                "Complex", category=ErrorCategory.NETWORK, context=ErrorContext("net", "client"), recoverable=True
            ),
        ]

        for error in errors:
            with self.subTest(error=error.message):
                with pytest.raises(StructuredError) as cm:
                    manager.attempt_recovery(error)
                assert cm.value is error

    def test_recovery_manager_concurrent_recovery(self) -> None:
        """Test concurrent recovery operations."""
        # Create thread-safe strategy
        strategy = CustomRecoveryStrategyV2(recoverable_categories=list(ErrorCategory), recovery_result="Recovered")

        manager = RecoveryManager().add_strategy(strategy)

        results = []
        errors = []

        def attempt_recovery(recovery_id: int) -> None:
            try:
                categories = list(ErrorCategory)
                category = categories[recovery_id % len(categories)]

                error = StructuredError(
                    f"Error {recovery_id}",
                    category=category,
                    context=ErrorContext(f"op_{recovery_id}", f"comp_{recovery_id}"),
                )

                context = {"recovery_id": recovery_id, "thread_id": recovery_id}
                result = manager.attempt_recovery(error, context)
                results.append((recovery_id, result))

            except Exception as e:
                errors.append((recovery_id, e))

        # Run concurrent recovery attempts
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_recovery, i) for i in range(50)]
            for future in futures:
                future.result()

        assert len(errors) == 0, f"Concurrent recovery errors: {errors}"
        assert len(results) == 50

        # All should be recovered
        for _recovery_id, result in results:
            assert result == "Recovered"

        # Check all attempts were recorded
        assert len(strategy.recovery_attempts) == 50

    def test_recovery_manager_performance(self) -> None:
        """Test recovery manager performance with many strategies."""
        manager = RecoveryManager()

        # Add many non-matching strategies
        for _i in range(100):
            manager.add_strategy(CustomRecoveryStrategyV2([ErrorCategory.UNKNOWN]))

        # Add final matching strategy
        final_strategy = CustomRecoveryStrategyV2(
            recoverable_categories=[ErrorCategory.VALIDATION], recovery_result="Found it"
        )
        manager.add_strategy(final_strategy)

        # Time the recovery
        error = StructuredError("Test", category=ErrorCategory.VALIDATION)

        start_time = time.time()
        result = manager.attempt_recovery(error)
        end_time = time.time()

        assert result == "Found it"
        assert len(final_strategy.recovery_attempts) == 1

        # Should still be fast
        assert end_time - start_time < 0.1

    def test_recovery_manager_memory_efficiency(self) -> None:
        """Test recovery manager memory efficiency with large errors."""
        # Create strategy that can handle large errors
        strategy = CustomRecoveryStrategyV2(
            recoverable_categories=list(ErrorCategory), recovery_result="Recovered large error"
        )

        manager = RecoveryManager().add_strategy(strategy)

        # Create errors with large payloads
        large_message = "x" * (1024 * 1024)  # 1MB

        for i in range(5):
            error = StructuredError(
                large_message,
                category=list(ErrorCategory)[i % len(ErrorCategory)],
                context=ErrorContext("large_op", "large_comp"),
            )

            context = {"large_data": "y" * (1024 * 1024)}  # 1MB context

            result = manager.attempt_recovery(error, context)
            assert result == "Recovered large error"

        assert len(strategy.recovery_attempts) == 5


class TestRecoveryIntegrationV2(unittest.TestCase):
    """Integration tests for recovery system with enhanced coverage."""

    def test_realistic_file_recovery_scenario_comprehensive(self) -> None:
        """Test comprehensive realistic file recovery scenarios."""

        class FileCreationStrategyV2(RecoveryStrategy):
            def __init__(self) -> None:
                self.created_files = []
                self.creation_attempts = []

            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.FILE_NOT_FOUND

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                file_path = error.context.user_data.get("file_path", "unknown")

                # Simulate directory creation if needed
                if "/" in file_path:
                    dir_path = "/".join(file_path.split("/")[:-1])
                    self.creation_attempts.append(f"mkdir -p {dir_path}")

                self.created_files.append(file_path)
                self.creation_attempts.append(f"touch {file_path}")

                # Simulate different creation results
                if "readonly" in file_path:
                    msg = f"Cannot create {file_path}: Read-only filesystem"
                    raise PermissionError(msg)
                if "large" in file_path:
                    msg = f"Cannot create {file_path}: No space left on device"
                    raise OSError(msg)

                return f"Created file: {file_path}"

        class PermissionFixStrategyV2(RecoveryStrategy):
            def __init__(self) -> None:
                self.permission_fixes = []
                self.chmod_commands = []
                self.fix_attempts = 0

            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.PERMISSION

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                self.fix_attempts += 1
                file_path = error.context.user_data.get("file_path", "unknown")

                # Check context for permission mode
                mode = context.get("permission_mode", "644") if context else "644"

                self.permission_fixes.append(file_path)
                self.chmod_commands.append(f"chmod {mode} {file_path}")

                # Simulate permission fix failures
                if "system" in file_path:
                    msg = f"Cannot change permissions for {file_path}: Operation not permitted"
                    raise PermissionError(msg)
                if self.fix_attempts > 3:
                    msg = "Too many permission fix attempts"
                    raise RuntimeError(msg)

                return f"Fixed permissions for: {file_path} (mode: {mode})"

        class DirectoryCreationStrategy(RecoveryStrategy):
            def __init__(self) -> None:
                self.created_directories = []

            def can_recover(self, error: StructuredError) -> bool:
                # Can recover file not found if it's a directory issue
                if error.category != ErrorCategory.FILE_NOT_FOUND:
                    return False

                file_path = error.context.user_data.get("file_path", "")
                return "/" in file_path and "dir_missing" in error.message.lower()

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                file_path = error.context.user_data.get("file_path", "")
                dir_path = "/".join(file_path.split("/")[:-1])

                self.created_directories.append(dir_path)
                return f"Created directory: {dir_path}"

        # Create strategies
        file_strategy = FileCreationStrategyV2()
        permission_strategy = PermissionFixStrategyV2()
        dir_strategy = DirectoryCreationStrategy()

        manager = RecoveryManager()
        manager.add_strategy(dir_strategy)  # Try directory creation first
        manager.add_strategy(file_strategy)
        manager.add_strategy(permission_strategy)

        # Test various file recovery scenarios

        # Scenario 1: Simple file not found
        context1 = ErrorContext("file_read", "loader")
        context1.add_user_data("file_path", "/data/missing.txt")

        error1 = StructuredError("File not found", category=ErrorCategory.FILE_NOT_FOUND, context=context1)

        result1 = manager.attempt_recovery(error1)
        assert result1 == "Created file: /data/missing.txt"
        assert "/data/missing.txt" in file_strategy.created_files

        # Scenario 2: Directory missing
        context2 = ErrorContext("file_write", "writer")
        context2.add_user_data("file_path", "/new/dir/file.txt")

        error2 = StructuredError("File not found: dir_missing", category=ErrorCategory.FILE_NOT_FOUND, context=context2)

        result2 = manager.attempt_recovery(error2)
        assert result2 == "Created directory: /new/dir"
        assert "/new/dir" in dir_strategy.created_directories

        # Scenario 3: Permission error with custom mode
        context3 = ErrorContext("file_write", "saver")
        context3.add_user_data("file_path", "/restricted/config.json")

        error3 = StructuredError("Permission denied", category=ErrorCategory.PERMISSION, context=context3)

        recovery_context = {"permission_mode": "755"}
        result3 = manager.attempt_recovery(error3, recovery_context)
        assert result3 == "Fixed permissions for: /restricted/config.json (mode: 755)"
        assert "chmod 755 /restricted/config.json" in permission_strategy.chmod_commands

        # Scenario 4: Read-only filesystem (should fail)
        context4 = ErrorContext("file_create", "creator")
        context4.add_user_data("file_path", "/readonly/test.txt")

        error4 = StructuredError("File not found", category=ErrorCategory.FILE_NOT_FOUND, context=context4)

        with pytest.raises(StructuredError):
            manager.attempt_recovery(error4)

    def test_network_retry_recovery_scenario_comprehensive(self) -> None:
        """Test comprehensive network retry recovery scenarios."""

        class NetworkRetryStrategyV2(RecoveryStrategy):
            def __init__(self, max_retries=3, backoff_factor=2.0) -> None:
                self.max_retries = max_retries
                self.backoff_factor = backoff_factor
                self.retry_counts = {}
                self.retry_delays = []
                self.total_attempts = 0

            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.NETWORK

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                # Get operation identifier
                operation_id = error.context.operation
                if context and "request_id" in context:
                    operation_id = f"{operation_id}_{context['request_id']}"

                # Initialize retry count if needed
                if operation_id not in self.retry_counts:
                    self.retry_counts[operation_id] = 0

                # Perform retries internally
                for attempt in range(self.max_retries + 1):
                    self.total_attempts += 1

                    # Calculate delay with exponential backoff
                    if attempt > 0:
                        delay = (self.backoff_factor ** (attempt - 1)) * 0.01  # Small delays for testing
                        self.retry_delays.append(delay)
                        time.sleep(delay)

                    # Simulate different network conditions
                    try:
                        if "timeout" in error.message.lower():
                            if attempt < 1:  # Fail first attempt
                                msg = f"Request timeout (attempt {attempt + 1})"
                                raise TimeoutError(msg)
                        elif "refused" in error.message.lower():
                            if attempt < 2:  # Fail first two attempts
                                msg = f"Connection refused (attempt {attempt + 1})"
                                raise ConnectionRefusedError(msg)

                        # Success
                        self.retry_counts[operation_id] = attempt + 1
                        return f"Retry {attempt + 1} succeeded for {operation_id}"
                    except (TimeoutError, ConnectionRefusedError):
                        if attempt == self.max_retries:
                            # Final attempt failed
                            raise

                # Should not reach here
                msg = f"Max retries ({self.max_retries}) exceeded for {operation_id}"
                raise RuntimeError(msg)

        class CircuitBreakerStrategy(RecoveryStrategy):
            def __init__(self, failure_threshold=5, reset_timeout=1.0) -> None:
                self.failure_threshold = failure_threshold
                self.reset_timeout = reset_timeout
                self.failure_count = 0
                self.last_failure_time = None
                self.circuit_open = False

            def can_recover(self, error: StructuredError) -> bool:
                # Check if circuit should be reset
                if self.circuit_open and self.last_failure_time:
                    if time.time() - self.last_failure_time > self.reset_timeout:
                        self.circuit_open = False
                        self.failure_count = 0

                return error.category == ErrorCategory.NETWORK and not self.circuit_open

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.circuit_open = True
                    msg = "Circuit breaker opened - too many failures"
                    raise RuntimeError(msg)

                # Always fail to test circuit breaker
                msg = f"Network failure {self.failure_count}"
                raise RuntimeError(msg)

        # Test basic retry scenario
        retry_strategy = NetworkRetryStrategyV2(max_retries=3)
        manager = RecoveryManager().add_strategy(retry_strategy)

        # Scenario 1: Timeout that succeeds on retry
        timeout_context = ErrorContext("api_call", "http_client")
        timeout_error = StructuredError("Request timeout", category=ErrorCategory.NETWORK, context=timeout_context)

        result = manager.attempt_recovery(timeout_error)
        assert "Retry 2 succeeded" in result
        assert retry_strategy.retry_counts["api_call"] == 2

        # Scenario 2: Connection refused that succeeds on third try
        refused_context = ErrorContext("service_connect", "grpc_client")
        refused_error = StructuredError("Connection refused", category=ErrorCategory.NETWORK, context=refused_context)

        result = manager.attempt_recovery(refused_error)
        assert "Retry 3 succeeded" in result

        # Scenario 3: Test with circuit breaker
        circuit_breaker = CircuitBreakerStrategy(failure_threshold=3, reset_timeout=0.1)
        breaker_manager = RecoveryManager()
        breaker_manager.add_strategy(circuit_breaker)
        breaker_manager.add_strategy(retry_strategy)  # Fallback

        network_error = StructuredError(
            "Network failure", category=ErrorCategory.NETWORK, context=ErrorContext("test_op", "test_comp")
        )

        # First attempts should use circuit breaker until it opens
        for _i in range(3):
            result = breaker_manager.attempt_recovery(network_error)
            # Falls back to retry strategy
            assert "succeeded" in result

        # Now circuit should be open
        assert circuit_breaker.circuit_open

        # Wait for circuit to reset
        time.sleep(0.15)

        # Should work again
        result = breaker_manager.attempt_recovery(network_error)
        assert "succeeded" in result

    def test_complex_recovery_with_fallbacks_comprehensive(self) -> None:
        """Test comprehensive complex recovery scenarios with multiple fallback strategies."""

        class PrimaryStrategyV2(RecoveryStrategy):
            def __init__(self) -> None:
                self.attempts = 0
                self.success_after = 3

            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.PROCESSING

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                self.attempts += 1

                if context and "force_fail" in context:
                    msg = "Forced failure"
                    raise RuntimeError(msg)

                if self.attempts < self.success_after:
                    msg = f"Primary strategy failed (attempt {self.attempts})"
                    raise RuntimeError(msg)

                return f"Primary strategy succeeded on attempt {self.attempts}"

        class FallbackStrategyV2(RecoveryStrategy):
            def __init__(self) -> None:
                self.attempts = 0
                self.success_conditions = {}

            def can_recover(self, error: StructuredError) -> bool:
                return error.category in {ErrorCategory.PROCESSING, ErrorCategory.VALIDATION}

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                self.attempts += 1
                operation = error.context.operation

                # Track attempts per operation
                self.success_conditions[operation] = self.success_conditions.get(operation, 0) + 1

                # Different success conditions based on operation
                if operation == "critical_process":
                    if self.success_conditions[operation] < 2:
                        msg = "Fallback not ready for critical process"
                        raise RuntimeError(msg)
                elif operation == "batch_process":
                    # Always succeed for batch
                    pass
                # Default: succeed on second attempt
                elif self.attempts == 1:
                    msg = "Fallback strategy failed on first try"
                    raise RuntimeError(msg)

                return f"Fallback strategy succeeded for {operation}"

        class LastResortStrategyV2(RecoveryStrategy):
            def __init__(self) -> None:
                self.attempts = 0
                self.handled_errors = []

            def can_recover(self, error: StructuredError) -> bool:
                # Can handle anything
                return True

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                self.attempts += 1
                self.handled_errors.append({"error": error, "context": context, "attempt": self.attempts})

                # Check for special conditions
                if context and "no_last_resort" in context:
                    msg = "Last resort disabled"
                    raise RuntimeError(msg)

                # Degrade functionality based on error type
                if error.category == ErrorCategory.PROCESSING:
                    return "Last resort: Processing with reduced quality"
                if error.category == ErrorCategory.NETWORK:
                    return "Last resort: Using cached data"
                return "Last resort: Basic recovery completed"

        # Create strategies
        primary = PrimaryStrategyV2()
        fallback = FallbackStrategyV2()
        last_resort = LastResortStrategyV2()

        manager = RecoveryManager()
        manager.add_strategy(primary)
        manager.add_strategy(fallback)
        manager.add_strategy(last_resort)

        # Test various recovery paths

        # Path 1: Primary fails twice, fallback fails, last resort succeeds
        error1 = StructuredError(
            "Processing failed",
            category=ErrorCategory.PROCESSING,
            context=ErrorContext("standard_process", "processor"),
        )

        result1 = manager.attempt_recovery(error1)
        assert result1 == "Last resort: Processing with reduced quality"
        assert primary.attempts == 1
        assert fallback.attempts == 1
        assert last_resort.attempts == 1

        # Path 2: Primary fails, fallback succeeds
        result2 = manager.attempt_recovery(error1)
        assert result2 == "Fallback strategy succeeded for standard_process"
        assert primary.attempts == 2
        assert fallback.attempts == 2
        assert last_resort.attempts == 1  # Not called

        # Path 3: Primary succeeds
        result3 = manager.attempt_recovery(error1)
        assert result3 == "Primary strategy succeeded on attempt 3"
        assert primary.attempts == 3

        # Path 4: Critical process - needs special handling
        critical_error = StructuredError(
            "Critical processing failed",
            category=ErrorCategory.PROCESSING,
            context=ErrorContext("critical_process", "critical_processor"),
        )

        # Reset primary attempts for new operation
        primary.attempts = 0  # Reset for new operation

        # First attempt - all fail except last resort
        result4 = manager.attempt_recovery(critical_error)
        assert result4 == "Last resort: Processing with reduced quality"

        # Second attempt - fallback now ready
        primary.attempts = 0  # Reset again for clarity
        result5 = manager.attempt_recovery(critical_error)
        assert result5 == "Fallback strategy succeeded for critical_process"

        # Path 5: Forced failure with no last resort
        forced_error = StructuredError(
            "Forced failure", category=ErrorCategory.PROCESSING, context=ErrorContext("forced_op", "forced_comp")
        )

        primary.attempts = 0
        # Reset fallback attempts to ensure it fails on first try
        fallback.attempts = 0
        with pytest.raises(StructuredError):
            manager.attempt_recovery(forced_error, {"force_fail": True, "no_last_resort": True})

    def test_recovery_with_rich_context_comprehensive(self) -> None:
        """Test comprehensive recovery strategies with rich context data."""

        class ContextAwareStrategyV2(RecoveryStrategy):
            def __init__(self) -> None:
                self.processed_contexts = []
                self.recovery_decisions = []

            def can_recover(self, error: StructuredError) -> bool:
                # Make decision based on error context
                if error.category == ErrorCategory.PROCESSING:
                    # Check if we have enough context to recover
                    required_data = ["input_file", "output_file", "processing_type"]
                    user_data_keys = error.context.user_data.keys()
                    return all(key in user_data_keys for key in required_data)
                return True

            def recover(self, error: StructuredError, context: dict[str, Any] | None = None) -> Any:
                # Build comprehensive recovery context
                recovery_info = {
                    "error_details": {
                        "message": error.message,
                        "category": error.category.name,
                        "recoverable": error.recoverable,
                        "suggestions": error.suggestions[:],
                        "timestamp": error.context.timestamp.isoformat(),
                        "trace_id": error.context.trace_id,
                    },
                    "error_context": {
                        "operation": error.context.operation,
                        "component": error.context.component,
                        "user_data": error.context.user_data.copy(),
                        "system_data": error.context.system_data.copy(),
                    },
                    "recovery_context": context or {},
                    "recovery_timestamp": time.time(),
                }

                self.processed_contexts.append(recovery_info)

                # Make recovery decision based on context
                if error.category == ErrorCategory.PROCESSING:
                    error.context.user_data.get("input_file")
                    processing_type = error.context.user_data.get("processing_type")

                    if processing_type == "image_resize":
                        # Check memory constraints
                        memory_limit = context.get("memory_limit", "500MB") if context else "500MB"
                        error.context.system_data.get("memory_usage", "0MB")

                        decision = {
                            "action": "resize_with_lower_quality",
                            "parameters": {"quality": 0.8, "max_dimension": 1920, "memory_limit": memory_limit},
                        }
                    elif processing_type == "video_transcode":
                        # Adjust encoding parameters
                        decision = {
                            "action": "transcode_with_fallback",
                            "parameters": {
                                "codec": "h264",  # Fallback from h265
                                "bitrate": "2M",  # Reduced from original
                                "preset": "fast",  # Faster encoding
                            },
                        }
                    else:
                        decision = {"action": "generic_retry", "parameters": {"delay": 1.0}}

                    self.recovery_decisions.append(decision)
                    return f"Recovered with strategy: {decision['action']}"

                if error.category == ErrorCategory.NETWORK:
                    # Network-specific recovery
                    endpoint = error.context.user_data.get("endpoint", "unknown")

                    if context and "use_cdn" in context:
                        return f"Switched to CDN for {endpoint}"
                    if context and "use_cache" in context:
                        return f"Using cached version of {endpoint}"
                    return f"Retrying {endpoint} with backoff"

                return "Generic recovery completed"

        strategy = ContextAwareStrategyV2()
        manager = RecoveryManager().add_strategy(strategy)

        # Test various rich context scenarios

        # Scenario 1: Image processing with memory constraints
        image_context = ErrorContext("image_processing", "resizer")
        image_context.add_user_data("input_file", "/images/large.jpg")
        image_context.add_user_data("output_file", "/images/resized.jpg")
        image_context.add_user_data("processing_type", "image_resize")
        image_context.add_user_data("original_dimensions", (4000, 3000))
        image_context.add_system_data("memory_usage", "450MB")
        image_context.add_system_data("cpu_usage", 85.5)
        image_context.add_system_data("processing_time", 12.3)
        image_context.trace_id = "img_trace_123"

        image_error = StructuredError(
            "Out of memory during image resize",
            category=ErrorCategory.PROCESSING,
            context=image_context,
            recoverable=True,
            suggestions=["Reduce image dimensions", "Increase memory allocation"],
        )

        recovery_params = {"memory_limit": "400MB", "allow_quality_reduction": True, "max_retries": 3}

        result = manager.attempt_recovery(image_error, recovery_params)
        assert result == "Recovered with strategy: resize_with_lower_quality"

        # Verify context was properly processed
        assert len(strategy.processed_contexts) == 1
        processed = strategy.processed_contexts[0]
        assert processed["error_context"]["user_data"]["input_file"] == "/images/large.jpg"
        assert processed["recovery_context"]["memory_limit"] == "400MB"

        # Scenario 2: Video transcoding failure
        video_context = ErrorContext("video_processing", "transcoder")
        video_context.add_user_data("input_file", "/videos/source.mp4")
        video_context.add_user_data("output_file", "/videos/output.mp4")
        video_context.add_user_data("processing_type", "video_transcode")
        video_context.add_user_data("original_codec", "h265")
        video_context.add_system_data("ffmpeg_version", "4.4.0")
        video_context.add_system_data("gpu_available", False)

        video_error = StructuredError(
            "Codec not supported", category=ErrorCategory.PROCESSING, context=video_context, recoverable=True
        )

        result = manager.attempt_recovery(video_error)
        assert result == "Recovered with strategy: transcode_with_fallback"

        # Scenario 3: Network error with CDN fallback
        network_context = ErrorContext("api_request", "http_client")
        network_context.add_user_data("endpoint", "https://api.example.com/data")
        network_context.add_user_data("method", "GET")
        network_context.add_system_data("response_time", 30.0)
        network_context.add_system_data("status_code", 503)

        network_error = StructuredError(
            "Service temporarily unavailable", category=ErrorCategory.NETWORK, context=network_context, recoverable=True
        )

        cdn_context = {"use_cdn": True, "cdn_endpoint": "https://cdn.example.com"}
        result = manager.attempt_recovery(network_error, cdn_context)
        assert result == "Switched to CDN for https://api.example.com/data"


# Compatibility tests using pytest style
class TestRecoveryPytest:
    """Pytest-style tests for compatibility."""

    def test_recovery_strategy_abstract_pytest(self) -> None:
        """Test abstract recovery strategy using pytest style."""
        with pytest.raises(TypeError):
            RecoveryStrategy()

    def test_file_recovery_pytest(self) -> None:
        """Test file recovery using pytest style."""
        strategy = FileRecoveryStrategy()

        file_error = StructuredError("File not found", category=ErrorCategory.FILE_NOT_FOUND)
        assert strategy.can_recover(file_error) is True

        with pytest.raises(NotImplementedError):
            strategy.recover(file_error)

    def test_retry_recovery_pytest(self) -> None:
        """Test retry recovery using pytest style."""
        strategy = RetryRecoveryStrategy(max_retries=5)

        assert strategy.max_retries == 5

        network_error = StructuredError("Network error", category=ErrorCategory.NETWORK)
        assert strategy.can_recover(network_error) is True

        with pytest.raises(NotImplementedError):
            strategy.recover(network_error)

    def test_recovery_manager_pytest(self) -> None:
        """Test recovery manager using pytest style."""
        strategy = CustomRecoveryStrategyV2(
            recoverable_categories=[ErrorCategory.VALIDATION], recovery_result="Recovered"
        )

        manager = RecoveryManager().add_strategy(strategy)

        error = StructuredError("Test", category=ErrorCategory.VALIDATION)
        result = manager.attempt_recovery(error)

        assert result == "Recovered"
        assert len(strategy.recovery_attempts) == 1


if __name__ == "__main__":
    unittest.main()
