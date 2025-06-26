"""
Tests for error recovery strategies.

Tests the RecoveryStrategy, RecoveryManager, and related classes to ensure
proper error recovery functionality.
"""

from typing import Any, Dict, Optional

import pytest

from goesvfi.utils.errors.base import ErrorCategory, ErrorContext, StructuredError
from goesvfi.utils.errors.recovery import (
    FileRecoveryStrategy,
    RecoveryManager,
    RecoveryStrategy,
    RetryRecoveryStrategy,
)


class TestRecoveryStrategy:
    """Test base recovery strategy functionality."""

    def test_recovery_strategy_is_abstract(self):
        """Test that RecoveryStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            RecoveryStrategy()

    def test_recovery_strategy_methods_are_abstract(self):
        """Test that RecoveryStrategy methods are abstract."""

        class IncompleteStrategy(RecoveryStrategy):
            def can_recover(self, error: StructuredError) -> bool:
                return True

            # Missing recover method

        with pytest.raises(TypeError):
            IncompleteStrategy()


class TestFileRecoveryStrategy:
    """Test file recovery strategy functionality."""

    def test_file_recovery_can_recover_file_errors(self):
        """Test that file recovery strategy can handle file-related errors."""
        strategy = FileRecoveryStrategy()

        file_not_found_error = StructuredError("File not found", category=ErrorCategory.FILE_NOT_FOUND)
        permission_error = StructuredError("Permission denied", category=ErrorCategory.PERMISSION)
        network_error = StructuredError("Network error", category=ErrorCategory.NETWORK)

        assert strategy.can_recover(file_not_found_error) is True
        assert strategy.can_recover(permission_error) is True
        assert strategy.can_recover(network_error) is False

    def test_file_recovery_not_implemented(self):
        """Test that file recovery strategy raises NotImplementedError."""
        strategy = FileRecoveryStrategy()
        error = StructuredError("File not found", category=ErrorCategory.FILE_NOT_FOUND)

        with pytest.raises(NotImplementedError, match="File recovery strategy not implemented"):
            strategy.recover(error)

    def test_file_recovery_with_context(self):
        """Test file recovery strategy with context data."""
        strategy = FileRecoveryStrategy()
        error = StructuredError("File not found", category=ErrorCategory.FILE_NOT_FOUND)
        context = {"retry_count": 1, "alternative_path": "/backup/file.txt"}

        with pytest.raises(NotImplementedError):
            strategy.recover(error, context)


class TestRetryRecoveryStrategy:
    """Test retry recovery strategy functionality."""

    def test_retry_recovery_initialization(self):
        """Test retry recovery strategy initialization."""
        # Default initialization
        strategy = RetryRecoveryStrategy()
        assert strategy.max_retries == 3

        # Custom initialization
        custom_strategy = RetryRecoveryStrategy(max_retries=5)
        assert custom_strategy.max_retries == 5

    def test_retry_recovery_can_recover_retryable_errors(self):
        """Test that retry strategy can handle retryable errors."""
        strategy = RetryRecoveryStrategy()

        network_error = StructuredError("Network error", category=ErrorCategory.NETWORK)
        external_tool_error = StructuredError("Tool failed", category=ErrorCategory.EXTERNAL_TOOL)
        validation_error = StructuredError("Invalid input", category=ErrorCategory.VALIDATION)

        assert strategy.can_recover(network_error) is True
        assert strategy.can_recover(external_tool_error) is True
        assert strategy.can_recover(validation_error) is False

    def test_retry_recovery_not_implemented(self):
        """Test that retry recovery strategy raises NotImplementedError."""
        strategy = RetryRecoveryStrategy()
        error = StructuredError("Network error", category=ErrorCategory.NETWORK)

        with pytest.raises(NotImplementedError, match="Retry recovery strategy not implemented"):
            strategy.recover(error)


class CustomRecoveryStrategy(RecoveryStrategy):
    """Custom recovery strategy for testing."""

    def __init__(self, recoverable_categories=None, recovery_result=None, should_fail=False):
        self.recoverable_categories = recoverable_categories or []
        self.recovery_result = recovery_result
        self.should_fail = should_fail
        self.recovery_attempts = []

    def can_recover(self, error: StructuredError) -> bool:
        return error.category in self.recoverable_categories

    def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
        self.recovery_attempts.append({"error": error, "context": context})

        if self.should_fail:
            raise RuntimeError("Recovery failed")

        return self.recovery_result


class TestRecoveryManager:
    """Test recovery manager functionality."""

    def test_recovery_manager_initialization(self):
        """Test recovery manager initialization."""
        manager = RecoveryManager()

        assert len(manager.strategies) == 0

    def test_recovery_manager_add_strategy(self):
        """Test adding strategies to recovery manager."""
        manager = RecoveryManager()
        strategy1 = CustomRecoveryStrategy([ErrorCategory.VALIDATION])
        strategy2 = CustomRecoveryStrategy([ErrorCategory.NETWORK])

        result = manager.add_strategy(strategy1)
        assert result == manager  # Should return self for chaining
        assert len(manager.strategies) == 1

        manager.add_strategy(strategy2)
        assert len(manager.strategies) == 2
        assert manager.strategies[0] == strategy1
        assert manager.strategies[1] == strategy2

    def test_recovery_manager_fluent_interface(self):
        """Test fluent interface for adding strategies."""
        strategy1 = CustomRecoveryStrategy([ErrorCategory.VALIDATION])
        strategy2 = CustomRecoveryStrategy([ErrorCategory.NETWORK])

        manager = RecoveryManager().add_strategy(strategy1).add_strategy(strategy2)

        assert len(manager.strategies) == 2

    def test_recovery_manager_successful_recovery(self):
        """Test successful error recovery."""
        strategy = CustomRecoveryStrategy(
            recoverable_categories=[ErrorCategory.VALIDATION],
            recovery_result="Successfully recovered",
        )

        manager = RecoveryManager().add_strategy(strategy)

        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)
        context = {"retry_count": 1}

        result = manager.attempt_recovery(error, context)

        assert result == "Successfully recovered"
        assert len(strategy.recovery_attempts) == 1
        assert strategy.recovery_attempts[0]["error"] == error
        assert strategy.recovery_attempts[0]["context"] == context

    def test_recovery_manager_no_matching_strategy(self):
        """Test recovery when no strategy can handle the error."""
        strategy = CustomRecoveryStrategy([ErrorCategory.VALIDATION])
        manager = RecoveryManager().add_strategy(strategy)

        # Error that can't be handled
        error = StructuredError("Network error", category=ErrorCategory.NETWORK)

        with pytest.raises(StructuredError) as exc_info:
            manager.attempt_recovery(error)

        # Should re-raise the original error
        assert exc_info.value == error
        assert len(strategy.recovery_attempts) == 0

    def test_recovery_manager_strategy_failure(self):
        """Test recovery when strategy fails."""
        failing_strategy = CustomRecoveryStrategy(recoverable_categories=[ErrorCategory.VALIDATION], should_fail=True)

        backup_strategy = CustomRecoveryStrategy(
            recoverable_categories=[ErrorCategory.VALIDATION],
            recovery_result="Backup recovery successful",
        )

        manager = RecoveryManager().add_strategy(failing_strategy).add_strategy(backup_strategy)

        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)

        result = manager.attempt_recovery(error)

        # Should succeed with backup strategy
        assert result == "Backup recovery successful"
        assert len(failing_strategy.recovery_attempts) == 1
        assert len(backup_strategy.recovery_attempts) == 1

    def test_recovery_manager_all_strategies_fail(self):
        """Test recovery when all strategies fail."""
        strategy1 = CustomRecoveryStrategy(recoverable_categories=[ErrorCategory.VALIDATION], should_fail=True)

        strategy2 = CustomRecoveryStrategy(recoverable_categories=[ErrorCategory.VALIDATION], should_fail=True)

        manager = RecoveryManager().add_strategy(strategy1).add_strategy(strategy2)

        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)

        with pytest.raises(StructuredError) as exc_info:
            manager.attempt_recovery(error)

        # Should re-raise the original error
        assert exc_info.value == error
        # Both strategies should have been attempted
        assert len(strategy1.recovery_attempts) == 1
        assert len(strategy2.recovery_attempts) == 1

    def test_recovery_manager_strategy_priority(self):
        """Test that strategies are tried in order."""
        first_strategy = CustomRecoveryStrategy(
            recoverable_categories=[ErrorCategory.VALIDATION],
            recovery_result="First strategy result",
        )

        second_strategy = CustomRecoveryStrategy(
            recoverable_categories=[ErrorCategory.VALIDATION],
            recovery_result="Second strategy result",
        )

        manager = RecoveryManager().add_strategy(first_strategy).add_strategy(second_strategy)

        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)

        result = manager.attempt_recovery(error)

        # Should use first strategy
        assert result == "First strategy result"
        assert len(first_strategy.recovery_attempts) == 1
        assert len(second_strategy.recovery_attempts) == 0


class TestRecoveryIntegration:
    """Integration tests for recovery system."""

    def test_realistic_file_recovery_scenario(self):
        """Test realistic file recovery scenario."""

        class FileCreationStrategy(RecoveryStrategy):
            def __init__(self):
                self.created_files = []

            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.FILE_NOT_FOUND

            def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
                file_path = error.context.user_data.get("file_path", "unknown")
                self.created_files.append(file_path)
                return f"Created file: {file_path}"

        class PermissionFixStrategy(RecoveryStrategy):
            def __init__(self):
                self.permission_fixes = []

            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.PERMISSION

            def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
                file_path = error.context.user_data.get("file_path", "unknown")
                self.permission_fixes.append(file_path)
                return f"Fixed permissions for: {file_path}"

        file_strategy = FileCreationStrategy()
        permission_strategy = PermissionFixStrategy()

        manager = RecoveryManager().add_strategy(file_strategy).add_strategy(permission_strategy)

        # Test file not found recovery
        file_context = ErrorContext(operation="file_read", component="loader")
        file_context.add_user_data("file_path", "/data/missing.txt")

        file_error = StructuredError(
            "File not found",
            category=ErrorCategory.FILE_NOT_FOUND,
            context=file_context,
        )

        result = manager.attempt_recovery(file_error)
        assert result == "Created file: /data/missing.txt"
        assert "/data/missing.txt" in file_strategy.created_files

        # Test permission error recovery
        perm_context = ErrorContext(operation="file_write", component="saver")
        perm_context.add_user_data("file_path", "/restricted/config.json")

        perm_error = StructuredError("Permission denied", category=ErrorCategory.PERMISSION, context=perm_context)

        result = manager.attempt_recovery(perm_error)
        assert result == "Fixed permissions for: /restricted/config.json"
        assert "/restricted/config.json" in permission_strategy.permission_fixes

    def test_network_retry_recovery_scenario(self):
        """Test network retry recovery scenario."""

        class NetworkRetryStrategy(RecoveryStrategy):
            def __init__(self, max_retries=3):
                self.max_retries = max_retries
                self.retry_counts = {}

            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.NETWORK

            def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
                operation_id = error.context.operation
                current_count = self.retry_counts.get(operation_id, 0)

                if current_count >= self.max_retries:
                    raise RuntimeError(f"Max retries ({self.max_retries}) exceeded for {operation_id}")

                self.retry_counts[operation_id] = current_count + 1
                return f"Retry {current_count + 1} for {operation_id}"

        strategy = NetworkRetryStrategy(max_retries=2)
        manager = RecoveryManager().add_strategy(strategy)

        network_context = ErrorContext(operation="api_call_123", component="http_client")
        network_error = StructuredError("Connection failed", category=ErrorCategory.NETWORK, context=network_context)

        # First retry should succeed
        result1 = manager.attempt_recovery(network_error)
        assert result1 == "Retry 1 for api_call_123"

        # Second retry should succeed
        result2 = manager.attempt_recovery(network_error)
        assert result2 == "Retry 2 for api_call_123"

        # Third retry should fail (exceeds max)
        with pytest.raises(StructuredError) as exc_info:
            manager.attempt_recovery(network_error)

        assert exc_info.value == network_error

    def test_complex_recovery_with_fallbacks(self):
        """Test complex recovery scenario with multiple fallback strategies."""

        class PrimaryStrategy(RecoveryStrategy):
            def __init__(self, success_rate=0.5):
                self.success_rate = success_rate
                self.attempts = 0

            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.PROCESSING

            def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
                self.attempts += 1
                if self.attempts <= 2:  # Fail first 2 attempts
                    raise RuntimeError("Primary strategy failed")
                return "Primary strategy succeeded"

        class FallbackStrategy(RecoveryStrategy):
            def __init__(self):
                self.attempts = 0

            def can_recover(self, error: StructuredError) -> bool:
                return error.category == ErrorCategory.PROCESSING

            def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("Fallback strategy failed on first try")
                return "Fallback strategy succeeded"

        class LastResortStrategy(RecoveryStrategy):
            def __init__(self):
                self.attempts = 0

            def can_recover(self, error: StructuredError) -> bool:
                return True  # Can handle any error

            def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
                self.attempts += 1
                return "Last resort strategy succeeded"

        primary = PrimaryStrategy()
        fallback = FallbackStrategy()
        last_resort = LastResortStrategy()

        manager = RecoveryManager().add_strategy(primary).add_strategy(fallback).add_strategy(last_resort)

        processing_error = StructuredError("Processing failed", category=ErrorCategory.PROCESSING)

        # First attempt - primary fails, fallback fails, last resort succeeds
        result1 = manager.attempt_recovery(processing_error)
        assert result1 == "Last resort strategy succeeded"
        assert primary.attempts == 1
        assert fallback.attempts == 1
        assert last_resort.attempts == 1

        # Second attempt - primary fails, fallback succeeds
        result2 = manager.attempt_recovery(processing_error)
        assert result2 == "Fallback strategy succeeded"
        assert primary.attempts == 2
        assert fallback.attempts == 2
        assert last_resort.attempts == 1  # Shouldn't be called

        # Third attempt - primary succeeds
        result3 = manager.attempt_recovery(processing_error)
        assert result3 == "Primary strategy succeeded"
        assert primary.attempts == 3
        assert fallback.attempts == 2  # Shouldn't be called
        assert last_resort.attempts == 1  # Shouldn't be called

    def test_recovery_with_rich_context(self):
        """Test recovery strategies with rich context data."""

        class ContextAwareStrategy(RecoveryStrategy):
            def __init__(self):
                self.processed_contexts = []

            def can_recover(self, error: StructuredError) -> bool:
                return True

            def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
                recovery_context = {
                    "error_context": {
                        "operation": error.context.operation,
                        "component": error.context.component,
                        "user_data": error.context.user_data.copy(),
                        "system_data": error.context.system_data.copy(),
                    },
                    "recovery_context": context or {},
                    "error_category": error.category,
                    "recoverable": error.recoverable,
                }
                self.processed_contexts.append(recovery_context)
                return f"Recovered with context: {len(self.processed_contexts)} attempts"

        strategy = ContextAwareStrategy()
        manager = RecoveryManager().add_strategy(strategy)

        # Create error with rich context
        error_context = ErrorContext(operation="image_processing", component="resizer")
        error_context.add_user_data("image_path", "/images/large.jpg")
        error_context.add_user_data("target_size", (1920, 1080))
        error_context.add_system_data("memory_usage", "250MB")
        error_context.add_system_data("processing_time", 5.2)

        error = StructuredError(
            "Memory exceeded during resize",
            category=ErrorCategory.PROCESSING,
            context=error_context,
            recoverable=True,
        )

        recovery_context = {
            "retry_with_smaller_size": True,
            "max_memory_limit": "200MB",
            "fallback_quality": 0.8,
        }

        result = manager.attempt_recovery(error, recovery_context)
        assert result == "Recovered with context: 1 attempts"

        processed = strategy.processed_contexts[0]
        assert processed["error_context"]["operation"] == "image_processing"
        assert processed["error_context"]["user_data"]["image_path"] == "/images/large.jpg"
        assert processed["error_context"]["system_data"]["memory_usage"] == "250MB"
        assert processed["recovery_context"]["retry_with_smaller_size"] is True
        assert processed["error_category"] == ErrorCategory.PROCESSING
        assert processed["recoverable"] is True
