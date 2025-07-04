"""Error handling utilities.

Provides structured error handling chains to reduce complexity in error management.
"""

from abc import ABC, abstractmethod
import logging

from .base import ErrorCategory, StructuredError


class ErrorHandler(ABC):
    """Base class for error handlers."""

    @abstractmethod
    def can_handle(self, error: StructuredError) -> bool:
        """Check if this handler can handle the given error."""

    @abstractmethod
    def handle(self, error: StructuredError) -> bool:
        """Handle the error.

        Returns:
            True if error was handled and processing should stop,
            False if processing should continue to next handler
        """


class LoggingErrorHandler(ErrorHandler):
    """Error handler that logs errors."""

    def __init__(self, logger: logging.Logger | None = None, log_level: int = logging.ERROR) -> None:
        self.logger = logger or logging.getLogger("goesvfi.error_handler")
        self.log_level = log_level

    def can_handle(self, _error: StructuredError) -> bool:
        """Can handle any error for logging."""
        return True

    def handle(self, error: StructuredError) -> bool:
        """Log the error and continue processing."""
        self.logger.log(self.log_level, "Error in %s: %s", error.context.component, error.message)
        return False  # Continue to next handler


class CategoryErrorHandler(ErrorHandler):
    """Error handler for specific error categories."""

    def __init__(self, categories: ErrorCategory | list[ErrorCategory]) -> None:
        if isinstance(categories, ErrorCategory):
            self.categories = [categories]
        else:
            self.categories = categories

    def can_handle(self, error: StructuredError) -> bool:
        """Check if error category matches."""
        return error.category in self.categories

    def handle(self, _error: StructuredError) -> bool:
        """Handle category-specific error."""
        # Override in subclasses
        return False


class ErrorHandlerChain:
    """Chain of error handlers for processing errors."""

    def __init__(self) -> None:
        self.handlers: list[ErrorHandler] = []

    def add_handler(self, handler: ErrorHandler) -> "ErrorHandlerChain":
        """Add a handler to the chain."""
        self.handlers.append(handler)
        return self

    def handle_error(self, error: StructuredError | Exception) -> bool:
        """Process error through the handler chain.

        Args:
            error: Either a StructuredError or regular Exception

        Returns:
            True if error was handled, False otherwise
        """
        if isinstance(error, Exception) and not isinstance(error, StructuredError):
            # Convert regular exception to StructuredError
            from .classifier import default_classifier
            structured_error = default_classifier.create_structured_error(error)
        else:
            structured_error = error

        return any(handler.can_handle(structured_error) and handler.handle(structured_error) for handler in self.handlers)
