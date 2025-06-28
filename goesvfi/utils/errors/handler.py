"""
Error handling utilities.

Provides structured error handling chains to reduce complexity in error management.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Union

from .base import ErrorCategory, StructuredError


class ErrorHandler(ABC):
    """Base class for error handlers."""

    @abstractmethod
    def can_handle(self, error: StructuredError) -> bool:
        """Check if this handler can handle the given error."""
        pass

    @abstractmethod
    def handle(self, error: StructuredError) -> bool:
        """
        Handle the error.

        Returns:
            True if error was handled and processing should stop,
            False if processing should continue to next handler
        """
        pass


class LoggingErrorHandler(ErrorHandler):
    """Error handler that logs errors."""

    def __init__(self, logger: Optional[logging.Logger] = None, log_level: int = logging.ERROR) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.log_level = log_level

    def can_handle(self, error: StructuredError) -> bool:
        """Can handle any error for logging."""
        return True

    def handle(self, error: StructuredError) -> bool:
        """Log the error and continue processing."""
        self.logger.log(self.log_level, "Error in %s: %s", error.context.component, error.message)
        return False  # Continue to next handler


class CategoryErrorHandler(ErrorHandler):
    """Error handler for specific error categories."""

    def __init__(self, categories: Union[ErrorCategory, List[ErrorCategory]]) -> None:
        if isinstance(categories, ErrorCategory):
            self.categories = [categories]
        else:
            self.categories = categories

    def can_handle(self, error: StructuredError) -> bool:
        """Check if error category matches."""
        return error.category in self.categories

    def handle(self, error: StructuredError) -> bool:
        """Handle category-specific error."""
        # Override in subclasses
        return False


class ErrorHandlerChain:
    """Chain of error handlers for processing errors."""

    def __init__(self) -> None:
        self.handlers: List[ErrorHandler] = []

    def add_handler(self, handler: ErrorHandler) -> "ErrorHandlerChain":
        """Add a handler to the chain."""
        self.handlers.append(handler)
        return self

    def handle_error(self, error: StructuredError) -> bool:
        """
        Process error through the handler chain.

        Returns:
            True if error was handled, False otherwise
        """
        for handler in self.handlers:
            if handler.can_handle(error):
                if handler.handle(error):
                    return True
        return False
