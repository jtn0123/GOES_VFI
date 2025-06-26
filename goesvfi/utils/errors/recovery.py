"""
Error recovery utilities.

Provides recovery strategies to reduce complexity in error recovery logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .base import ErrorCategory, StructuredError


class RecoveryStrategy(ABC):
    """Base class for error recovery strategies."""

    @abstractmethod
    def can_recover(self, error: StructuredError) -> bool:
        """Check if this strategy can recover from the error."""
        pass

    @abstractmethod
    def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Attempt to recover from the error.

        Returns:
            Recovery result or raises exception if recovery fails
        """
        pass


class FileRecoveryStrategy(RecoveryStrategy):
    """Recovery strategy for file-related errors."""

    def can_recover(self, error: StructuredError) -> bool:
        """Can recover from file-related errors."""
        return error.category in [
            ErrorCategory.FILE_NOT_FOUND,
            ErrorCategory.PERMISSION,
        ]

    def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
        """Attempt file recovery."""
        # This is a placeholder - specific recovery logic would go here
        raise NotImplementedError("File recovery strategy not implemented")


class RetryRecoveryStrategy(RecoveryStrategy):
    """Recovery strategy that retries the operation."""

    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries

    def can_recover(self, error: StructuredError) -> bool:
        """Can retry network and external tool errors."""
        return error.category in [ErrorCategory.NETWORK, ErrorCategory.EXTERNAL_TOOL]

    def recover(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
        """Attempt retry recovery."""
        # This is a placeholder - specific retry logic would go here
        raise NotImplementedError("Retry recovery strategy not implemented")


class RecoveryManager:
    """Manages error recovery strategies."""

    def __init__(self) -> None:
        self.strategies: list[RecoveryStrategy] = []

    def add_strategy(self, strategy: RecoveryStrategy) -> "RecoveryManager":
        """Add a recovery strategy."""
        self.strategies.append(strategy)
        return self

    def attempt_recovery(self, error: StructuredError, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Attempt to recover from an error using available strategies.

        Returns:
            Recovery result if successful

        Raises:
            StructuredError: If no recovery strategy could handle the error
        """
        for strategy in self.strategies:
            if strategy.can_recover(error):
                try:
                    return strategy.recover(error, context)
                except Exception:
                    # Log recovery failure but continue to next strategy
                    continue

        # No recovery possible
        raise error
