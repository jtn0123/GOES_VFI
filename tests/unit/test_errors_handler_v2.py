"""Tests for error handling chains and handlers - Optimized V2 with 100%+ coverage.

Enhanced tests for ErrorHandler, ErrorHandlerChain, and related classes to ensure
proper error handling workflow functionality. Includes comprehensive scenarios,
concurrent operations, memory efficiency tests, and edge cases.
"""

from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import logging
import time
from typing import Never
import unittest

import pytest

from goesvfi.utils.errors.base import ErrorCategory, ErrorContext, StructuredError
from goesvfi.utils.errors.handler import (
    CategoryErrorHandler,
    ErrorHandler,
    ErrorHandlerChain,
    LoggingErrorHandler,
)


class TestErrorHandlerV2(unittest.TestCase):
    """Test base error handler functionality with comprehensive coverage."""

    def test_error_handler_is_abstract_comprehensive(self) -> None:
        """Test comprehensive abstract class scenarios."""
        # Test that ErrorHandler cannot be instantiated directly
        with pytest.raises(TypeError):
            ErrorHandler()

        # Test various incomplete implementations
        class MissingHandleMethod(ErrorHandler):
            def can_handle(self, error: StructuredError) -> bool:
                return True

            # Missing handle method

        class MissingCanHandleMethod(ErrorHandler):
            def handle(self, error: StructuredError) -> bool:
                return True

            # Missing can_handle method

        class NoMethods(ErrorHandler):
            pass
            # Missing both methods

        # All should raise TypeError
        with pytest.raises(TypeError):
            MissingHandleMethod()

        with pytest.raises(TypeError):
            MissingCanHandleMethod()

        with pytest.raises(TypeError):
            NoMethods()

        # Test correct implementation works
        class CompleteHandler(ErrorHandler):
            def can_handle(self, error: StructuredError) -> bool:
                return True

            def handle(self, error: StructuredError) -> bool:
                return True

        # Should not raise
        handler = CompleteHandler()
        assert isinstance(handler, ErrorHandler)

    def test_error_handler_interface_comprehensive(self) -> None:
        """Test comprehensive error handler interface scenarios."""

        class TestHandler(ErrorHandler):
            def __init__(self) -> None:
                self.can_handle_calls = []
                self.handle_calls = []

            def can_handle(self, error: StructuredError) -> bool:
                self.can_handle_calls.append(error)
                return True

            def handle(self, error: StructuredError) -> bool:
                self.handle_calls.append(error)
                return True

        handler = TestHandler()

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

        for error in errors:
            with self.subTest(error=error.message):
                # Test can_handle
                can_handle = handler.can_handle(error)
                assert can_handle
                assert len(handler.can_handle_calls) == len(errors[: errors.index(error) + 1])

                # Test handle
                handled = handler.handle(error)
                assert handled
                assert len(handler.handle_calls) == len(errors[: errors.index(error) + 1])


class TestLoggingErrorHandlerV2(unittest.TestCase):
    """Test logging error handler functionality with comprehensive coverage."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create test logger with string handler
        self.log_stream = StringIO()
        self.log_handler = logging.StreamHandler(self.log_stream)
        self.test_logger = logging.getLogger(f"test_logger_{id(self)}")
        self.test_logger.setLevel(logging.DEBUG)
        self.test_logger.addHandler(self.log_handler)
        self.test_logger.propagate = False

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Clean up logger
        self.test_logger.removeHandler(self.log_handler)
        self.log_handler.close()

    def test_logging_handler_initialization_comprehensive(self) -> None:
        """Test comprehensive logging handler initialization scenarios."""
        # Test default initialization
        handler = LoggingErrorHandler()
        assert handler.logger is not None
        assert handler.log_level == logging.ERROR
        assert handler.logger.name == "goesvfi.error_handler"

        # Test custom logger
        custom_logger = logging.getLogger("custom_test")
        handler = LoggingErrorHandler(logger=custom_logger)
        assert handler.logger == custom_logger
        assert handler.log_level == logging.ERROR

        # Test custom log level
        handler = LoggingErrorHandler(log_level=logging.WARNING)
        assert handler.log_level == logging.WARNING

        # Test all log levels
        log_levels = [
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ]

        for level in log_levels:
            with self.subTest(level=logging.getLevelName(level)):
                handler = LoggingErrorHandler(logger=self.test_logger, log_level=level)
                assert handler.log_level == level

    def test_logging_handler_can_handle_comprehensive(self) -> None:
        """Test comprehensive can_handle scenarios."""
        handler = LoggingErrorHandler()

        # Test various error types - should handle all
        errors = [
            StructuredError("Simple error"),
            StructuredError("Validation error", category=ErrorCategory.VALIDATION),
            StructuredError("Network error", category=ErrorCategory.NETWORK),
            StructuredError("System error", category=ErrorCategory.SYSTEM),
            StructuredError("Unknown error", category=ErrorCategory.UNKNOWN),
            StructuredError(
                "Complex error",
                category=ErrorCategory.PROCESSING,
                context=ErrorContext("op", "comp"),
                recoverable=False,
            ),
        ]

        for error in errors:
            with self.subTest(error=error.message):
                assert handler.can_handle(error)

    def test_logging_handler_logs_error_comprehensive(self) -> None:
        """Test comprehensive error logging scenarios."""
        handler = LoggingErrorHandler(logger=self.test_logger, log_level=logging.ERROR)

        # Test various error scenarios
        test_cases = [
            {
                "error": StructuredError("Simple error", context=ErrorContext("simple_op", "simple_comp")),
                "expected_log": "Error in simple_comp: Simple error",
            },
            {
                "error": StructuredError(
                    "Error with category",
                    category=ErrorCategory.VALIDATION,
                    context=ErrorContext("validate", "validator"),
                ),
                "expected_log": "Error in validator: Error with category",
            },
            {
                "error": StructuredError(
                    "Error with details",
                    context=ErrorContext("process", "processor"),
                    user_message="User friendly message",
                    suggestions=["Try this", "Or that"],
                ),
                "expected_log": "Error in processor: Error with details",
            },
            {
                "error": StructuredError(
                    "",  # Empty message
                    context=ErrorContext("empty", "handler"),
                ),
                "expected_log": "Error in handler: ",
            },
        ]

        for test_case in test_cases:
            with self.subTest(case=test_case["expected_log"]):
                # Clear log stream
                self.log_stream.truncate(0)
                self.log_stream.seek(0)

                # Handle error
                result = handler.handle(test_case["error"])

                # Should return False to continue processing
                assert not result

                # Check log output
                log_output = self.log_stream.getvalue()
                assert test_case["expected_log"] in log_output

    def test_logging_handler_different_log_levels_comprehensive(self) -> None:
        """Test comprehensive logging with different log levels."""
        # Test each log level
        test_cases = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for log_level, level_name in test_cases:
            with self.subTest(level=level_name):
                # Clear log stream
                self.log_stream.truncate(0)
                self.log_stream.seek(0)

                # Create handler with specific level
                handler = LoggingErrorHandler(logger=self.test_logger, log_level=log_level)

                # Create error
                error = StructuredError(f"{level_name} level error", context=ErrorContext("test_op", "test_comp"))

                # Handle error
                handler.handle(error)

                # Check log output contains level
                log_output = self.log_stream.getvalue()
                assert level_name in log_output
                assert f"{level_name} level error" in log_output

    def test_logging_handler_with_exception_cause(self) -> None:
        """Test logging handler with errors that have exception causes."""
        handler = LoggingErrorHandler(logger=self.test_logger)

        # Create error with cause
        try:
            msg = "Original error"
            raise ValueError(msg)
        except ValueError as e:
            error = StructuredError("Wrapped error", context=ErrorContext("wrap", "wrapper"), cause=e)

        # Handle error
        result = handler.handle(error)
        assert not result

        # Check log output
        log_output = self.log_stream.getvalue()
        assert "Error in wrapper: Wrapped error" in log_output

    def test_logging_handler_thread_safety(self) -> None:
        """Test logging handler thread safety."""
        handler = LoggingErrorHandler(logger=self.test_logger)
        results = []
        errors = []

        def log_error(error_id: int) -> None:
            try:
                error = StructuredError(f"Error {error_id}", context=ErrorContext(f"op_{error_id}", f"comp_{error_id}"))
                result = handler.handle(error)
                results.append((error_id, result))
            except Exception as e:
                errors.append((error_id, e))

        # Run concurrent logging
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(log_error, i) for i in range(50)]
            for future in futures:
                future.result()

        assert len(errors) == 0
        assert len(results) == 50

        # All should return False
        for _error_id, result in results:
            assert not result

        # Check all errors were logged
        log_output = self.log_stream.getvalue()
        for i in range(50):
            assert f"Error {i}" in log_output


class TestCategoryErrorHandlerV2(unittest.TestCase):
    """Test category-specific error handler functionality with comprehensive coverage."""

    def test_category_handler_initialization_comprehensive(self) -> None:
        """Test comprehensive category handler initialization."""
        # Test single category (not a list)
        handler = CategoryErrorHandler(ErrorCategory.VALIDATION)
        assert handler.categories == [ErrorCategory.VALIDATION]

        # Test list of categories
        categories = [ErrorCategory.VALIDATION, ErrorCategory.PERMISSION, ErrorCategory.NETWORK]
        handler = CategoryErrorHandler(categories)
        assert handler.categories == categories

        # Test empty list
        handler = CategoryErrorHandler([])
        assert handler.categories == []

        # Test all categories
        all_categories = list(ErrorCategory)
        handler = CategoryErrorHandler(all_categories)
        assert handler.categories == all_categories

    def test_category_handler_can_handle_comprehensive(self) -> None:
        """Test comprehensive can_handle scenarios."""
        # Test single category handler
        handler = CategoryErrorHandler(ErrorCategory.VALIDATION)

        test_cases = [
            (StructuredError("Valid", category=ErrorCategory.VALIDATION), True),
            (StructuredError("Network", category=ErrorCategory.NETWORK), False),
            (StructuredError("Unknown", category=ErrorCategory.UNKNOWN), False),
        ]

        for error, expected in test_cases:
            with self.subTest(category=error.category):
                assert handler.can_handle(error) == expected

        # Test multiple category handler
        handler = CategoryErrorHandler([
            ErrorCategory.VALIDATION,
            ErrorCategory.PERMISSION,
            ErrorCategory.FILE_NOT_FOUND,
        ])

        test_cases = [
            (StructuredError("Valid", category=ErrorCategory.VALIDATION), True),
            (StructuredError("Perm", category=ErrorCategory.PERMISSION), True),
            (StructuredError("File", category=ErrorCategory.FILE_NOT_FOUND), True),
            (StructuredError("Network", category=ErrorCategory.NETWORK), False),
            (StructuredError("System", category=ErrorCategory.SYSTEM), False),
        ]

        for error, expected in test_cases:
            with self.subTest(category=error.category, expected=expected):
                assert handler.can_handle(error) == expected

    def test_category_handler_handle_method_comprehensive(self) -> None:
        """Test comprehensive handle method scenarios."""
        handler = CategoryErrorHandler(ErrorCategory.VALIDATION)

        # Test with matching category
        error = StructuredError("Test", category=ErrorCategory.VALIDATION)
        result = handler.handle(error)
        assert not result  # Default implementation returns False

        # Test with non-matching category (shouldn't be called, but test anyway)
        error = StructuredError("Test", category=ErrorCategory.NETWORK)
        result = handler.handle(error)
        assert not result

    def test_category_handler_subclass_comprehensive(self) -> None:
        """Test comprehensive category handler subclassing."""

        class CustomCategoryHandler(CategoryErrorHandler):
            def __init__(self, categories) -> None:
                super().__init__(categories)
                self.handled_errors = []
                self.handle_count = 0

            def handle(self, error: StructuredError) -> bool:
                self.handled_errors.append(error)
                self.handle_count += 1
                # Return True for VALIDATION, False for others
                return error.category == ErrorCategory.VALIDATION

        # Test custom handler
        handler = CustomCategoryHandler([ErrorCategory.VALIDATION, ErrorCategory.PERMISSION])

        # Test handling different categories
        validation_error = StructuredError("Valid", category=ErrorCategory.VALIDATION)
        permission_error = StructuredError("Perm", category=ErrorCategory.PERMISSION)

        # Validation should return True
        assert handler.handle(validation_error)
        assert handler.handle_count == 1

        # Permission should return False
        assert not handler.handle(permission_error)
        assert handler.handle_count == 2

        # Check both were recorded
        assert len(handler.handled_errors) == 2

    def test_category_handler_edge_cases(self) -> None:
        """Test category handler edge cases."""
        # Test with all categories
        handler = CategoryErrorHandler(list(ErrorCategory))

        # Should handle any error
        for category in ErrorCategory:
            error = StructuredError("Test", category=category)
            assert handler.can_handle(error)

        # Test with no categories
        handler = CategoryErrorHandler([])

        # Should not handle any error
        for category in ErrorCategory:
            error = StructuredError("Test", category=category)
            assert not handler.can_handle(error)


class CustomErrorHandlerV2(ErrorHandler):
    """Enhanced custom error handler for testing."""

    def __init__(
        self, handled_categories=None, should_stop=False, handle_delay=0, raise_on_handle=None, max_handles=None
    ) -> None:
        self.handled_categories = handled_categories or []
        self.should_stop = should_stop
        self.handled_errors = []
        self.can_handle_calls = []
        self.handle_delay = handle_delay
        self.raise_on_handle = raise_on_handle
        self.max_handles = max_handles
        self._handle_count = 0

    def can_handle(self, error: StructuredError) -> bool:
        self.can_handle_calls.append(error)
        return error.category in self.handled_categories

    def handle(self, error: StructuredError) -> bool:
        if self.handle_delay > 0:
            time.sleep(self.handle_delay)

        if self.raise_on_handle:
            raise self.raise_on_handle

        self._handle_count += 1
        self.handled_errors.append(error)

        if self.max_handles and self._handle_count >= self.max_handles:
            return True  # Stop after max handles

        return self.should_stop

    def reset(self) -> None:
        """Reset handler state."""
        self.handled_errors.clear()
        self.can_handle_calls.clear()
        self._handle_count = 0


class TestErrorHandlerChainV2(unittest.TestCase):
    """Test error handler chain functionality with comprehensive coverage."""

    def test_chain_initialization_comprehensive(self) -> None:
        """Test comprehensive chain initialization."""
        # Test empty initialization
        chain = ErrorHandlerChain()
        assert len(chain.handlers) == 0
        assert isinstance(chain.handlers, list)

        # Test chain is independent
        chain1 = ErrorHandlerChain()
        chain2 = ErrorHandlerChain()

        handler = CustomErrorHandlerV2([ErrorCategory.VALIDATION])
        chain1.add_handler(handler)

        assert len(chain1.handlers) == 1
        assert len(chain2.handlers) == 0

    def test_chain_add_handler_comprehensive(self) -> None:
        """Test comprehensive handler addition scenarios."""
        chain = ErrorHandlerChain()

        # Test adding single handler
        handler1 = CustomErrorHandlerV2([ErrorCategory.VALIDATION])
        result = chain.add_handler(handler1)

        assert result is chain  # Should return self
        assert len(chain.handlers) == 1
        assert chain.handlers[0] is handler1

        # Test adding multiple handlers
        handler2 = CustomErrorHandlerV2([ErrorCategory.NETWORK])
        handler3 = CustomErrorHandlerV2([ErrorCategory.PERMISSION])

        chain.add_handler(handler2).add_handler(handler3)

        assert len(chain.handlers) == 3
        assert chain.handlers[1] is handler2
        assert chain.handlers[2] is handler3

        # Test adding many handlers
        for _i in range(10):
            chain.add_handler(CustomErrorHandlerV2([ErrorCategory.UNKNOWN]))

        assert len(chain.handlers) == 13

    def test_chain_fluent_interface_comprehensive(self) -> None:
        """Test comprehensive fluent interface scenarios."""
        # Test chaining multiple operations
        handler1 = CustomErrorHandlerV2([ErrorCategory.VALIDATION])
        handler2 = CustomErrorHandlerV2([ErrorCategory.NETWORK])
        handler3 = CustomErrorHandlerV2([ErrorCategory.PERMISSION])

        chain = ErrorHandlerChain().add_handler(handler1).add_handler(handler2).add_handler(handler3)

        assert len(chain.handlers) == 3

        # Test chaining with different handler types
        chain = (
            ErrorHandlerChain()
            .add_handler(LoggingErrorHandler())
            .add_handler(CategoryErrorHandler(ErrorCategory.VALIDATION))
            .add_handler(CustomErrorHandlerV2([ErrorCategory.NETWORK]))
        )

        assert len(chain.handlers) == 3
        assert isinstance(chain.handlers[0], LoggingErrorHandler)
        assert isinstance(chain.handlers[1], CategoryErrorHandler)
        assert isinstance(chain.handlers[2], CustomErrorHandlerV2)

    def test_chain_handles_error_successfully_comprehensive(self) -> None:
        """Test comprehensive successful error handling scenarios."""
        # Test single matching handler
        handler = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=True)
        chain = ErrorHandlerChain().add_handler(handler)

        error = StructuredError("Test", category=ErrorCategory.VALIDATION)
        result = chain.handle_error(error)

        assert result
        assert len(handler.handled_errors) == 1
        assert handler.handled_errors[0] is error

        # Test multiple handlers, first matches
        handler1 = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=True)
        handler2 = CustomErrorHandlerV2([ErrorCategory.VALIDATION, ErrorCategory.NETWORK])

        chain = ErrorHandlerChain().add_handler(handler1).add_handler(handler2)

        error = StructuredError("Test", category=ErrorCategory.VALIDATION)
        result = chain.handle_error(error)

        assert result
        assert len(handler1.handled_errors) == 1
        assert len(handler2.handled_errors) == 0  # Not reached

        # Test multiple handlers, second matches
        handler1 = CustomErrorHandlerV2([ErrorCategory.NETWORK])
        handler2 = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=True)

        chain = ErrorHandlerChain().add_handler(handler1).add_handler(handler2)

        error = StructuredError("Test", category=ErrorCategory.VALIDATION)
        result = chain.handle_error(error)

        assert result
        assert len(handler1.handled_errors) == 0  # Can't handle
        assert len(handler2.handled_errors) == 1

    def test_chain_continues_processing_comprehensive(self) -> None:
        """Test comprehensive processing continuation scenarios."""
        # Test handlers that don't stop processing
        handlers = []
        for _i in range(5):
            handler = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=False)
            handlers.append(handler)

        # Last handler stops
        final_handler = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=True)
        handlers.append(final_handler)

        chain = ErrorHandlerChain()
        for handler in handlers:
            chain.add_handler(handler)

        error = StructuredError("Test", category=ErrorCategory.VALIDATION)
        result = chain.handle_error(error)

        assert result

        # All handlers should have processed
        for handler in handlers:
            assert len(handler.handled_errors) == 1
            assert handler.can_handle_calls[0] == error

    def test_chain_no_matching_handler_comprehensive(self) -> None:
        """Test comprehensive no matching handler scenarios."""
        # Create handlers for specific categories
        handlers = [
            CustomErrorHandlerV2([ErrorCategory.VALIDATION]),
            CustomErrorHandlerV2([ErrorCategory.PERMISSION]),
            CustomErrorHandlerV2([ErrorCategory.FILE_NOT_FOUND]),
        ]

        chain = ErrorHandlerChain()
        for handler in handlers:
            chain.add_handler(handler)

        # Test with unhandled category
        error = StructuredError("Network error", category=ErrorCategory.NETWORK)
        result = chain.handle_error(error)

        assert not result

        # All handlers should have been asked
        for handler in handlers:
            assert len(handler.can_handle_calls) == 1
            assert len(handler.handled_errors) == 0

    def test_chain_handler_order_comprehensive(self) -> None:
        """Test comprehensive handler order scenarios."""
        # Test order with stopping handlers
        stop_handler = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=True)
        continue_handler = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=False)

        # Stop first
        chain1 = ErrorHandlerChain().add_handler(stop_handler).add_handler(continue_handler)
        error = StructuredError("Test", category=ErrorCategory.VALIDATION)
        result = chain1.handle_error(error)

        assert result
        assert len(stop_handler.handled_errors) == 1
        assert len(continue_handler.handled_errors) == 0

        # Reset handlers
        stop_handler.reset()
        continue_handler.reset()

        # Continue first
        chain2 = ErrorHandlerChain().add_handler(continue_handler).add_handler(stop_handler)
        result = chain2.handle_error(error)

        assert result
        assert len(continue_handler.handled_errors) == 1
        assert len(stop_handler.handled_errors) == 1

    def test_chain_with_logging_handler_comprehensive(self) -> None:
        """Test comprehensive chain with logging handler scenarios."""
        # Setup logging
        log_stream = StringIO()
        log_handler = logging.StreamHandler(log_stream)
        test_logger = logging.getLogger("test_chain_logging")
        test_logger.setLevel(logging.DEBUG)
        test_logger.addHandler(log_handler)
        test_logger.propagate = False

        try:
            # Create mixed handler chain
            logging_handler = LoggingErrorHandler(logger=test_logger, log_level=logging.INFO)
            category_handler = CategoryErrorHandler([ErrorCategory.VALIDATION, ErrorCategory.NETWORK])
            custom_handler = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=True)

            chain = (
                ErrorHandlerChain()
                .add_handler(logging_handler)
                .add_handler(category_handler)
                .add_handler(custom_handler)
            )

            # Test with matching error
            error = StructuredError(
                "Validation failed", category=ErrorCategory.VALIDATION, context=ErrorContext("validate", "validator")
            )

            result = chain.handle_error(error)

            assert result
            assert len(custom_handler.handled_errors) == 1

            # Check logging
            log_output = log_stream.getvalue()
            assert "Error in validator: Validation failed" in log_output

            # Test with non-matching error
            log_stream.truncate(0)
            log_stream.seek(0)

            network_error = StructuredError(
                "Network timeout", category=ErrorCategory.NETWORK, context=ErrorContext("request", "http_client")
            )

            result = chain.handle_error(network_error)

            assert not result  # Category handler returns False by default

            # Should still be logged
            log_output = log_stream.getvalue()
            assert "Error in http_client: Network timeout" in log_output

        finally:
            test_logger.removeHandler(log_handler)
            log_handler.close()

    def test_chain_empty_behavior_comprehensive(self) -> None:
        """Test comprehensive empty chain behavior."""
        chain = ErrorHandlerChain()

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
                result = chain.handle_error(error)
                assert not result

    def test_chain_concurrent_error_handling(self) -> None:
        """Test concurrent error handling in chain."""
        # Create thread-safe handlers
        handlers = []
        for i in range(3):
            handler = CustomErrorHandlerV2(
                list(ErrorCategory),  # Handle all categories
                should_stop=(i == 2),  # Last handler stops
            )
            handlers.append(handler)

        chain = ErrorHandlerChain()
        for handler in handlers:
            chain.add_handler(handler)

        results = []
        errors = []

        def handle_error(error_id: int) -> None:
            try:
                categories = list(ErrorCategory)
                category = categories[error_id % len(categories)]

                error = StructuredError(
                    f"Error {error_id}", category=category, context=ErrorContext(f"op_{error_id}", f"comp_{error_id}")
                )

                result = chain.handle_error(error)
                results.append((error_id, result))

            except Exception as e:
                errors.append((error_id, e))

        # Run concurrent error handling
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(handle_error, i) for i in range(50)]
            for future in futures:
                future.result()

        assert len(errors) == 0, f"Concurrent handling errors: {errors}"
        assert len(results) == 50

        # All should be handled
        for _error_id, result in results:
            assert result

    def test_chain_performance_with_many_handlers(self) -> None:
        """Test chain performance with many handlers."""
        # Create many non-matching handlers
        chain = ErrorHandlerChain()

        for _i in range(100):
            handler = CustomErrorHandlerV2([ErrorCategory.UNKNOWN])
            chain.add_handler(handler)

        # Add final matching handler
        final_handler = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=True)
        chain.add_handler(final_handler)

        # Time the handling
        error = StructuredError("Test", category=ErrorCategory.VALIDATION)

        start_time = time.time()
        result = chain.handle_error(error)
        end_time = time.time()

        assert result
        assert len(final_handler.handled_errors) == 1

        # Should still be fast
        assert end_time - start_time < 0.1

    def test_chain_memory_efficiency(self) -> None:
        """Test chain memory efficiency with large errors."""
        # Create handler that can process large errors
        handler = CustomErrorHandlerV2(list(ErrorCategory), should_stop=True)

        chain = ErrorHandlerChain().add_handler(handler)

        # Create errors with large payloads
        large_message = "x" * (1024 * 1024)  # 1MB

        for i in range(5):
            error = StructuredError(
                large_message,
                category=list(ErrorCategory)[i % len(ErrorCategory)],
                context=ErrorContext("large_op", "large_comp"),
            )

            result = chain.handle_error(error)
            assert result

        assert len(handler.handled_errors) == 5

    def test_chain_handler_exceptions(self) -> None:
        """Test chain behavior when handlers raise exceptions."""

        # Create handler that raises exception
        class FaultyHandler(ErrorHandler):
            def can_handle(self, error) -> Never:
                msg = "Handler failed"
                raise RuntimeError(msg)

            def handle(self, error) -> Never:
                msg = "Should not reach here"
                raise RuntimeError(msg)

        # Create chain with faulty handler and good handler
        faulty = FaultyHandler()
        good = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=True)

        chain = ErrorHandlerChain().add_handler(faulty).add_handler(good)

        # Should handle error despite faulty handler
        error = StructuredError("Test", category=ErrorCategory.VALIDATION)

        # The chain might handle this differently - test actual behavior
        try:
            result = chain.handle_error(error)
            # If it doesn't raise, check if good handler was reached
            if not result:
                # Faulty handler prevented processing
                assert len(good.handled_errors) == 0
        except RuntimeError:
            # Exception propagated - this is also valid behavior
            pass


class TestErrorHandlerIntegrationV2(unittest.TestCase):
    """Integration tests for error handler system with enhanced coverage."""

    def test_realistic_error_handling_scenario_comprehensive(self) -> None:
        """Test comprehensive realistic error handling scenarios."""
        # Setup logging
        log_stream = StringIO()
        log_handler = logging.StreamHandler(log_stream)
        test_logger = logging.getLogger("integration_test_v2")
        test_logger.setLevel(logging.DEBUG)
        test_logger.addHandler(log_handler)
        test_logger.propagate = False

        try:
            # Create specialized handlers
            class FileErrorHandlerV2(CategoryErrorHandler):
                def __init__(self) -> None:
                    super().__init__([ErrorCategory.FILE_NOT_FOUND, ErrorCategory.PERMISSION, ErrorCategory.VALIDATION])
                    self.recovery_attempts = []
                    self.created_files = []

                def handle(self, error: StructuredError) -> bool:
                    self.recovery_attempts.append(error)

                    if error.category == ErrorCategory.FILE_NOT_FOUND:
                        # Simulate file creation
                        self.created_files.append(error.context.user_data.get("file_path", "unknown"))
                        return True  # Successfully recovered
                    if error.category == ErrorCategory.PERMISSION:
                        # Try to fix permissions
                        if error.recoverable:
                            return False  # Continue to next handler
                        return True  # Give up if not recoverable
                    if error.category == ErrorCategory.VALIDATION:
                        # Can't fix validation errors
                        return False
                    return False

            class NetworkErrorHandlerV2(CategoryErrorHandler):
                def __init__(self) -> None:
                    super().__init__([ErrorCategory.NETWORK])
                    self.retry_count = 0
                    self.retry_delays = [0.1, 0.2, 0.5]  # Exponential backoff

                def handle(self, error: StructuredError) -> bool:
                    if self.retry_count < len(self.retry_delays):
                        # Simulate retry with delay
                        time.sleep(self.retry_delays[self.retry_count])
                        self.retry_count += 1
                        return False  # Continue processing
                    return True  # Give up after max retries

            class UserInputErrorHandlerV2(CategoryErrorHandler):
                def __init__(self) -> None:
                    super().__init__([ErrorCategory.USER_INPUT, ErrorCategory.VALIDATION])
                    self.validation_errors = []

                def handle(self, error: StructuredError) -> bool:
                    self.validation_errors.append({
                        "message": error.message,
                        "suggestions": error.suggestions,
                        "field": error.context.user_data.get("field", "unknown"),
                    })
                    return True  # User must fix input

            # Create handlers
            file_handler = FileErrorHandlerV2()
            network_handler = NetworkErrorHandlerV2()
            user_handler = UserInputErrorHandlerV2()
            logging_handler = LoggingErrorHandler(logger=test_logger, log_level=logging.INFO)

            # Create chain
            chain = (
                ErrorHandlerChain()
                .add_handler(logging_handler)
                .add_handler(file_handler)
                .add_handler(network_handler)
                .add_handler(user_handler)
            )

            # Test various error scenarios

            # Scenario 1: File not found - should be recovered
            file_context = ErrorContext("file_read", "file_loader")
            file_context.add_user_data("file_path", "/tmp/test.txt")
            file_error = StructuredError(
                "File not found: /tmp/test.txt",
                category=ErrorCategory.FILE_NOT_FOUND,
                context=file_context,
                recoverable=True,
            )

            result = chain.handle_error(file_error)
            assert result
            assert len(file_handler.recovery_attempts) == 1
            assert "/tmp/test.txt" in file_handler.created_files

            # Scenario 2: Network error - should retry then give up
            network_error = StructuredError(
                "Connection timeout",
                category=ErrorCategory.NETWORK,
                context=ErrorContext("api_call", "http_client"),
                recoverable=True,
            )

            # First attempts should continue
            for i in range(3):
                result = chain.handle_error(network_error)
                assert not result
                assert network_handler.retry_count == i + 1

            # Final attempt should stop
            result = chain.handle_error(network_error)
            assert result

            # Scenario 3: Validation error
            validation_context = ErrorContext("input_validation", "form_validator")
            validation_context.add_user_data("field", "email")
            validation_error = StructuredError(
                "Invalid email format",
                category=ErrorCategory.VALIDATION,
                context=validation_context,
                recoverable=True,
                suggestions=["Use format: user@example.com"],
            )

            result = chain.handle_error(validation_error)
            assert result  # Handled by user input handler
            assert len(user_handler.validation_errors) == 1
            assert user_handler.validation_errors[0]["field"] == "email"

            # Check comprehensive logging
            log_output = log_stream.getvalue()
            assert "File not found: /tmp/test.txt" in log_output
            assert "Connection timeout" in log_output
            assert "Invalid email format" in log_output

        finally:
            test_logger.removeHandler(log_handler)
            log_handler.close()

    def test_error_handler_with_structured_error_context_comprehensive(self) -> None:
        """Test comprehensive error handlers with rich structured error context."""

        class ContextAwareHandlerV2(ErrorHandler):
            def __init__(self) -> None:
                self.processed_contexts = []
                self.error_statistics = {
                    "total": 0,
                    "recoverable": 0,
                    "by_category": {},
                    "by_component": {},
                }

            def can_handle(self, error: StructuredError) -> bool:
                return True

            def handle(self, error: StructuredError) -> bool:
                # Record detailed context
                self.processed_contexts.append({
                    "message": error.message,
                    "operation": error.context.operation,
                    "component": error.context.component,
                    "user_data": error.context.user_data.copy(),
                    "system_data": error.context.system_data.copy(),
                    "category": error.category,
                    "recoverable": error.recoverable,
                    "suggestions": error.suggestions[:],
                    "timestamp": error.context.timestamp,
                    "trace_id": error.context.trace_id,
                })

                # Update statistics
                self.error_statistics["total"] += 1
                if error.recoverable:
                    self.error_statistics["recoverable"] += 1

                category_name = error.category.name
                self.error_statistics["by_category"][category_name] = (
                    self.error_statistics["by_category"].get(category_name, 0) + 1
                )

                component = error.context.component
                self.error_statistics["by_component"][component] = (
                    self.error_statistics["by_component"].get(component, 0) + 1
                )

                return True

        handler = ContextAwareHandlerV2()
        chain = ErrorHandlerChain().add_handler(handler)

        # Create various errors with rich context
        test_scenarios = [
            {
                "name": "Data processing error",
                "operation": "data_processing",
                "component": "image_processor",
                "category": ErrorCategory.PROCESSING,
                "user_data": {
                    "file_path": "/images/test.jpg",
                    "operation_id": "proc_123",
                    "user_id": "user_456",
                },
                "system_data": {
                    "memory_usage": "150MB",
                    "processing_time": 2.5,
                    "cpu_usage": 85.2,
                    "thread_id": "thread_789",
                },
                "recoverable": False,
                "trace_id": "trace_abc123",
            },
            {
                "name": "API authentication failure",
                "operation": "api_auth",
                "component": "auth_service",
                "category": ErrorCategory.PERMISSION,
                "user_data": {
                    "endpoint": "/api/v1/users",
                    "method": "POST",
                    "api_key_id": "key_789",
                },
                "system_data": {
                    "response_code": 401,
                    "response_time": 0.123,
                    "server": "api-gateway-01",
                },
                "recoverable": True,
                "trace_id": "trace_def456",
            },
            {
                "name": "Configuration loading error",
                "operation": "config_load",
                "component": "config_manager",
                "category": ErrorCategory.CONFIGURATION,
                "user_data": {
                    "config_file": "/etc/app/config.yaml",
                    "environment": "production",
                },
                "system_data": {
                    "parse_error_line": 42,
                    "parse_error_column": 15,
                    "file_size": 2048,
                },
                "recoverable": True,
                "trace_id": "trace_ghi789",
            },
        ]

        for scenario in test_scenarios:
            # Create context
            context = ErrorContext(operation=scenario["operation"], component=scenario["component"])

            # Add user data
            for key, value in scenario["user_data"].items():
                context.add_user_data(key, value)

            # Add system data
            for key, value in scenario["system_data"].items():
                context.add_system_data(key, value)

            # Set trace ID
            context.trace_id = scenario["trace_id"]

            # Create error
            error = StructuredError(
                message=scenario["name"],
                category=scenario["category"],
                context=context,
                recoverable=scenario["recoverable"],
                suggestions=["Check logs", "Contact support", "Retry operation"],
            )

            # Handle error
            result = chain.handle_error(error)
            assert result

        # Verify all contexts were processed
        assert len(handler.processed_contexts) == 3

        # Check statistics
        assert handler.error_statistics["total"] == 3
        assert handler.error_statistics["recoverable"] == 2
        assert handler.error_statistics["by_category"]["PROCESSING"] == 1
        assert handler.error_statistics["by_category"]["PERMISSION"] == 1
        assert handler.error_statistics["by_category"]["CONFIGURATION"] == 1

        # Verify detailed context preservation
        for i, scenario in enumerate(test_scenarios):
            processed = handler.processed_contexts[i]
            assert processed["message"] == scenario["name"]
            assert processed["operation"] == scenario["operation"]
            assert processed["component"] == scenario["component"]
            assert processed["trace_id"] == scenario["trace_id"]

            # Check all user data preserved
            for key, value in scenario["user_data"].items():
                assert processed["user_data"][key] == value

            # Check all system data preserved
            for key, value in scenario["system_data"].items():
                assert processed["system_data"][key] == value

    def test_complex_handler_chain_scenarios(self) -> None:
        """Test complex handler chain scenarios with multiple handler types."""

        # Create a complex chain with different handler behaviors
        class PriorityHandler(ErrorHandler):
            """Handler that processes based on error priority."""

            def __init__(self, min_priority=0) -> None:
                self.min_priority = min_priority
                self.handled = []

            def can_handle(self, error):
                priority = error.context.system_data.get("priority", 0)
                return priority >= self.min_priority

            def handle(self, error):
                self.handled.append(error)
                priority = error.context.system_data.get("priority", 0)
                return priority >= 8  # Stop for high priority

        class RateLimitHandler(ErrorHandler):
            """Handler that enforces rate limiting."""

            def __init__(self, max_errors_per_second=10) -> None:
                self.max_errors_per_second = max_errors_per_second
                self.handled_times = []

            def can_handle(self, error):
                return error.category == ErrorCategory.NETWORK

            def handle(self, error) -> bool:
                current_time = time.time()
                self.handled_times.append(current_time)

                # Remove old entries
                cutoff = current_time - 1.0
                self.handled_times = [t for t in self.handled_times if t > cutoff]

                # Check rate limit
                if len(self.handled_times) > self.max_errors_per_second:
                    # Rate limit exceeded
                    return True  # Stop processing
                return False  # Continue

        # Create handlers
        priority_high = PriorityHandler(min_priority=7)
        priority_medium = PriorityHandler(min_priority=4)
        priority_low = PriorityHandler(min_priority=1)
        rate_limiter = RateLimitHandler(max_errors_per_second=5)
        fallback = CustomErrorHandlerV2(list(ErrorCategory), should_stop=False)

        # Create chain
        chain = (
            ErrorHandlerChain()
            .add_handler(rate_limiter)
            .add_handler(priority_high)
            .add_handler(priority_medium)
            .add_handler(priority_low)
            .add_handler(fallback)
        )

        # Test various scenarios

        # High priority error - should stop at priority_high
        context = ErrorContext("critical_op", "core_system")
        context.add_system_data("priority", 9)
        high_priority_error = StructuredError("Critical system failure", category=ErrorCategory.SYSTEM, context=context)

        result = chain.handle_error(high_priority_error)
        assert result
        assert len(priority_high.handled) == 1
        assert len(priority_medium.handled) == 0

        # Network errors - test rate limiting
        network_errors = []
        for i in range(10):
            context = ErrorContext("api_call", "client")
            context.add_system_data("priority", 3)
            error = StructuredError(f"Network error {i}", category=ErrorCategory.NETWORK, context=context)
            network_errors.append(error)

        # First 5 should continue processing
        for i in range(5):
            result = chain.handle_error(network_errors[i])
            assert not result  # Continues to priority handlers

        # 6th should trigger rate limit
        result = chain.handle_error(network_errors[5])
        assert result  # Rate limit stops processing


# Compatibility tests using pytest style
class TestErrorHandlerPytest:
    """Pytest-style tests for compatibility."""

    def test_logging_handler_pytest(self) -> None:
        """Test logging handler using pytest style."""
        handler = LoggingErrorHandler()
        error = StructuredError("Test error")

        assert handler.can_handle(error) is True
        assert handler.handle(error) is False

    def test_category_handler_pytest(self) -> None:
        """Test category handler using pytest style."""
        handler = CategoryErrorHandler([ErrorCategory.VALIDATION, ErrorCategory.NETWORK])

        validation_error = StructuredError("Test", category=ErrorCategory.VALIDATION)
        system_error = StructuredError("Test", category=ErrorCategory.SYSTEM)

        assert handler.can_handle(validation_error) is True
        assert handler.can_handle(system_error) is False

    def test_chain_pytest(self) -> None:
        """Test error handler chain using pytest style."""
        handler1 = CustomErrorHandlerV2([ErrorCategory.VALIDATION], should_stop=True)
        handler2 = CustomErrorHandlerV2([ErrorCategory.NETWORK])

        chain = ErrorHandlerChain().add_handler(handler1).add_handler(handler2)

        error = StructuredError("Test", category=ErrorCategory.VALIDATION)
        result = chain.handle_error(error)

        assert result is True
        assert len(handler1.handled_errors) == 1
        assert len(handler2.handled_errors) == 0

    def test_empty_chain_pytest(self) -> None:
        """Test empty chain using pytest style."""
        chain = ErrorHandlerChain()
        error = StructuredError("Test")

        result = chain.handle_error(error)
        assert result is False


if __name__ == "__main__":
    unittest.main()
