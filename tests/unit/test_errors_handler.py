"""
Tests for error handling chains and handlers.

Tests the ErrorHandler, ErrorHandlerChain, and related classes to ensure
proper error handling workflow functionality.
"""

import logging
from io import StringIO

import pytest

from goesvfi.utils.errors.base import ErrorCategory, ErrorContext, StructuredError
from goesvfi.utils.errors.handler import (
    CategoryErrorHandler,
    ErrorHandler,
    ErrorHandlerChain,
    LoggingErrorHandler,
)


class TestErrorHandler:
    """Test base error handler functionality."""

    def test_error_handler_is_abstract(self):
        """Test that ErrorHandler cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ErrorHandler()

    def test_error_handler_methods_are_abstract(self):
        """Test that ErrorHandler methods are abstract."""

        class IncompleteHandler(ErrorHandler):
            def can_handle(self, error: StructuredError) -> bool:
                return True

            # Missing handle method

        with pytest.raises(TypeError):
            IncompleteHandler()


class TestLoggingErrorHandler:
    """Test logging error handler functionality."""

    def test_logging_handler_initialization_default(self):
        """Test logging handler initialization with defaults."""
        handler = LoggingErrorHandler()

        assert handler.logger is not None
        assert handler.log_level == logging.ERROR

    def test_logging_handler_initialization_custom(self):
        """Test logging handler initialization with custom parameters."""
        custom_logger = logging.getLogger("test_logger")
        handler = LoggingErrorHandler(logger=custom_logger, log_level=logging.WARNING)

        assert handler.logger == custom_logger
        assert handler.log_level == logging.WARNING

    def test_logging_handler_can_handle_any_error(self):
        """Test that logging handler can handle any error."""
        handler = LoggingErrorHandler()
        error = StructuredError("Test error")

        assert handler.can_handle(error) is True

    def test_logging_handler_logs_error(self):
        """Test that logging handler properly logs errors."""
        # Create a string stream to capture log output
        log_stream = StringIO()
        log_handler = logging.StreamHandler(log_stream)

        # Create a logger with our custom handler
        test_logger = logging.getLogger("test_error_handler")
        test_logger.setLevel(logging.ERROR)
        test_logger.addHandler(log_handler)

        # Create our error handler with the test logger
        error_handler = LoggingErrorHandler(logger=test_logger)

        # Create a test error
        context = ErrorContext(operation="test_op", component="test_comp")
        error = StructuredError(message="Test error message", context=context)

        # Handle the error
        result = error_handler.handle(error)

        # Should return False to continue processing
        assert result is False

        # Check that error was logged
        log_output = log_stream.getvalue()
        assert "Error in test_comp: Test error message" in log_output

    def test_logging_handler_different_log_levels(self):
        """Test logging handler with different log levels."""
        log_stream = StringIO()
        log_handler = logging.StreamHandler(log_stream)

        test_logger = logging.getLogger("test_levels")
        test_logger.setLevel(logging.DEBUG)
        test_logger.addHandler(log_handler)

        # Test with WARNING level
        warning_handler = LoggingErrorHandler(
            logger=test_logger, log_level=logging.WARNING
        )
        error = StructuredError("Warning test", context=ErrorContext("op", "comp"))

        warning_handler.handle(error)
        log_output = log_stream.getvalue()
        assert "Warning test" in log_output


class TestCategoryErrorHandler:
    """Test category-specific error handler functionality."""

    def test_category_handler_single_category(self):
        """Test category handler with single category."""
        handler = CategoryErrorHandler(ErrorCategory.VALIDATION)

        validation_error = StructuredError(
            "Validation error", category=ErrorCategory.VALIDATION
        )
        network_error = StructuredError("Network error", category=ErrorCategory.NETWORK)

        assert handler.can_handle(validation_error) is True
        assert handler.can_handle(network_error) is False

    def test_category_handler_multiple_categories(self):
        """Test category handler with multiple categories."""
        categories = [ErrorCategory.VALIDATION, ErrorCategory.PERMISSION]
        handler = CategoryErrorHandler(categories)

        validation_error = StructuredError(
            "Validation error", category=ErrorCategory.VALIDATION
        )
        permission_error = StructuredError(
            "Permission error", category=ErrorCategory.PERMISSION
        )
        network_error = StructuredError("Network error", category=ErrorCategory.NETWORK)

        assert handler.can_handle(validation_error) is True
        assert handler.can_handle(permission_error) is True
        assert handler.can_handle(network_error) is False

    def test_category_handler_default_handle(self):
        """Test that default handle method returns False."""
        handler = CategoryErrorHandler(ErrorCategory.VALIDATION)
        error = StructuredError("Test error", category=ErrorCategory.VALIDATION)

        result = handler.handle(error)
        assert result is False


class CustomErrorHandler(ErrorHandler):
    """Custom error handler for testing."""

    def __init__(self, handled_categories=None, should_stop=False):
        self.handled_categories = handled_categories or []
        self.should_stop = should_stop
        self.handled_errors = []

    def can_handle(self, error: StructuredError) -> bool:
        return error.category in self.handled_categories

    def handle(self, error: StructuredError) -> bool:
        self.handled_errors.append(error)
        return self.should_stop


class TestErrorHandlerChain:
    """Test error handler chain functionality."""

    def test_chain_initialization(self):
        """Test error handler chain initialization."""
        chain = ErrorHandlerChain()

        assert len(chain.handlers) == 0

    def test_chain_add_handler(self):
        """Test adding handlers to chain."""
        chain = ErrorHandlerChain()
        handler1 = CustomErrorHandler([ErrorCategory.VALIDATION])
        handler2 = CustomErrorHandler([ErrorCategory.NETWORK])

        result = chain.add_handler(handler1)
        assert result == chain  # Should return self for chaining
        assert len(chain.handlers) == 1

        chain.add_handler(handler2)
        assert len(chain.handlers) == 2
        assert chain.handlers[0] == handler1
        assert chain.handlers[1] == handler2

    def test_chain_fluent_interface(self):
        """Test fluent interface for adding handlers."""
        handler1 = CustomErrorHandler([ErrorCategory.VALIDATION])
        handler2 = CustomErrorHandler([ErrorCategory.NETWORK])

        chain = ErrorHandlerChain().add_handler(handler1).add_handler(handler2)

        assert len(chain.handlers) == 2

    def test_chain_handles_error_successfully(self):
        """Test chain handling error with matching handler."""
        # Create handlers
        validation_handler = CustomErrorHandler(
            [ErrorCategory.VALIDATION], should_stop=True
        )
        network_handler = CustomErrorHandler([ErrorCategory.NETWORK])

        # Create chain
        chain = (
            ErrorHandlerChain()
            .add_handler(validation_handler)
            .add_handler(network_handler)
        )

        # Create error
        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)

        # Handle error
        result = chain.handle_error(error)

        # Should return True (handled)
        assert result is True
        assert len(validation_handler.handled_errors) == 1
        assert validation_handler.handled_errors[0] == error
        assert (
            len(network_handler.handled_errors) == 0
        )  # Should not reach second handler

    def test_chain_continues_processing(self):
        """Test chain continues processing when handlers return False."""
        # Create handlers that don't stop processing
        handler1 = CustomErrorHandler([ErrorCategory.VALIDATION], should_stop=False)
        handler2 = CustomErrorHandler([ErrorCategory.VALIDATION], should_stop=False)
        handler3 = CustomErrorHandler([ErrorCategory.VALIDATION], should_stop=True)

        # Create chain
        chain = (
            ErrorHandlerChain()
            .add_handler(handler1)
            .add_handler(handler2)
            .add_handler(handler3)
        )

        # Create error
        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)

        # Handle error
        result = chain.handle_error(error)

        # Should return True (handled by third handler)
        assert result is True
        # All handlers should have processed the error
        assert len(handler1.handled_errors) == 1
        assert len(handler2.handled_errors) == 1
        assert len(handler3.handled_errors) == 1

    def test_chain_no_matching_handler(self):
        """Test chain when no handler can handle the error."""
        # Create handlers for different categories
        validation_handler = CustomErrorHandler([ErrorCategory.VALIDATION])
        permission_handler = CustomErrorHandler([ErrorCategory.PERMISSION])

        # Create chain
        chain = (
            ErrorHandlerChain()
            .add_handler(validation_handler)
            .add_handler(permission_handler)
        )

        # Create error for unhandled category
        error = StructuredError("Network error", category=ErrorCategory.NETWORK)

        # Handle error
        result = chain.handle_error(error)

        # Should return False (not handled)
        assert result is False
        assert len(validation_handler.handled_errors) == 0
        assert len(permission_handler.handled_errors) == 0

    def test_chain_handler_order_matters(self):
        """Test that handler order affects processing."""
        # Create handlers - first one stops processing
        first_handler = CustomErrorHandler([ErrorCategory.VALIDATION], should_stop=True)
        second_handler = CustomErrorHandler(
            [ErrorCategory.VALIDATION], should_stop=False
        )

        # Create chain
        chain = (
            ErrorHandlerChain().add_handler(first_handler).add_handler(second_handler)
        )

        # Create error
        error = StructuredError("Validation error", category=ErrorCategory.VALIDATION)

        # Handle error
        result = chain.handle_error(error)

        # Should return True, but only first handler should process
        assert result is True
        assert len(first_handler.handled_errors) == 1
        assert len(second_handler.handled_errors) == 0

    def test_chain_with_logging_handler(self):
        """Test chain with actual logging handler."""
        # Create string stream for logging
        log_stream = StringIO()
        log_handler = logging.StreamHandler(log_stream)

        test_logger = logging.getLogger("test_chain")
        test_logger.setLevel(logging.ERROR)
        test_logger.addHandler(log_handler)

        # Create handlers
        logging_handler = LoggingErrorHandler(logger=test_logger)
        custom_handler = CustomErrorHandler(
            [ErrorCategory.VALIDATION], should_stop=True
        )

        # Create chain
        chain = (
            ErrorHandlerChain().add_handler(logging_handler).add_handler(custom_handler)
        )

        # Create error
        context = ErrorContext(operation="test", component="validator")
        error = StructuredError(
            "Validation failed", category=ErrorCategory.VALIDATION, context=context
        )

        # Handle error
        result = chain.handle_error(error)

        # Should be handled by custom handler
        assert result is True
        assert len(custom_handler.handled_errors) == 1

        # Should also be logged
        log_output = log_stream.getvalue()
        assert "Error in validator: Validation failed" in log_output


class TestErrorHandlerIntegration:
    """Integration tests for error handler system."""

    def test_realistic_error_handling_scenario(self):
        """Test realistic error handling scenario."""
        # Setup logging
        log_stream = StringIO()
        log_handler = logging.StreamHandler(log_stream)
        test_logger = logging.getLogger("integration_test")
        test_logger.setLevel(logging.DEBUG)
        test_logger.addHandler(log_handler)

        # Create specialized handlers
        class FileErrorHandler(CategoryErrorHandler):
            def __init__(self):
                super().__init__(
                    [ErrorCategory.FILE_NOT_FOUND, ErrorCategory.PERMISSION]
                )
                self.recovery_attempts = []

            def handle(self, error: StructuredError) -> bool:
                self.recovery_attempts.append(error)
                if error.category == ErrorCategory.FILE_NOT_FOUND:
                    # Try to create the file
                    return True  # Successfully recovered
                elif error.category == ErrorCategory.PERMISSION:
                    # Cannot recover from permission errors
                    return False  # Continue to next handler
                return False

        class NetworkErrorHandler(CategoryErrorHandler):
            def __init__(self):
                super().__init__([ErrorCategory.NETWORK])
                self.retry_count = 0

            def handle(self, error: StructuredError) -> bool:
                self.retry_count += 1
                if self.retry_count < 3:
                    return False  # Continue processing (will retry)
                else:
                    return True  # Give up after 3 retries

        # Create handlers
        file_handler = FileErrorHandler()
        network_handler = NetworkErrorHandler()
        logging_handler = LoggingErrorHandler(
            logger=test_logger, log_level=logging.INFO
        )

        # Create chain
        chain = (
            ErrorHandlerChain()
            .add_handler(logging_handler)  # Log everything
            .add_handler(file_handler)  # Handle file errors
            .add_handler(network_handler)
        )  # Handle network errors

        # Test file not found error
        file_error = StructuredError(
            "File not found",
            category=ErrorCategory.FILE_NOT_FOUND,
            context=ErrorContext("file_read", "file_loader"),
        )

        result = chain.handle_error(file_error)
        assert result is True  # Should be handled by file handler
        assert len(file_handler.recovery_attempts) == 1

        # Test network error (should retry)
        network_error = StructuredError(
            "Connection failed",
            category=ErrorCategory.NETWORK,
            context=ErrorContext("api_call", "http_client"),
        )

        # First two attempts should continue processing
        assert chain.handle_error(network_error) is False
        assert chain.handle_error(network_error) is False
        assert chain.handle_error(network_error) is True  # Third attempt stops

        assert network_handler.retry_count == 3

        # Check logging output
        log_output = log_stream.getvalue()
        assert "Error in file_loader: File not found" in log_output
        assert "Error in http_client: Connection failed" in log_output

    def test_error_handler_with_structured_error_context(self):
        """Test error handlers with rich structured error context."""

        class ContextAwareHandler(ErrorHandler):
            def __init__(self):
                self.processed_contexts = []

            def can_handle(self, error: StructuredError) -> bool:
                return True

            def handle(self, error: StructuredError) -> bool:
                self.processed_contexts.append(
                    {
                        "operation": error.context.operation,
                        "component": error.context.component,
                        "user_data": error.context.user_data.copy(),
                        "system_data": error.context.system_data.copy(),
                        "category": error.category,
                        "recoverable": error.recoverable,
                    }
                )
                return True

        handler = ContextAwareHandler()
        chain = ErrorHandlerChain().add_handler(handler)

        # Create error with rich context
        context = ErrorContext(operation="data_processing", component="image_processor")
        context.add_user_data("file_path", "/images/test.jpg")
        context.add_user_data("operation_id", "proc_123")
        context.add_system_data("memory_usage", "150MB")
        context.add_system_data("processing_time", 2.5)

        error = StructuredError(
            message="Processing failed",
            category=ErrorCategory.PROCESSING,
            context=context,
            recoverable=False,
        )

        result = chain.handle_error(error)
        assert result is True

        processed_context = handler.processed_contexts[0]
        assert processed_context["operation"] == "data_processing"
        assert processed_context["component"] == "image_processor"
        assert processed_context["user_data"]["file_path"] == "/images/test.jpg"
        assert processed_context["system_data"]["memory_usage"] == "150MB"
        assert processed_context["category"] == ErrorCategory.PROCESSING
        assert processed_context["recoverable"] is False

    def test_empty_chain_behavior(self):
        """Test behavior of empty handler chain."""
        chain = ErrorHandlerChain()
        error = StructuredError("Test error")

        result = chain.handle_error(error)
        assert result is False  # No handlers to process the error
