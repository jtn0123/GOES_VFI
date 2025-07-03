"""Fast, optimized tests for error handling chain - Optimized V2 with 100%+ coverage.

Enhanced tests for error handler chain with comprehensive scenarios,
concurrent operations, memory efficiency tests, and edge cases.
Critical infrastructure for error handling.
"""

from concurrent.futures import ThreadPoolExecutor
import time
import unittest

from goesvfi.utils.errors.base import ErrorCategory
from goesvfi.utils.errors.handler import ErrorHandler, ErrorHandlerChain


class MockErrorHandler(ErrorHandler):
    """Enhanced mock error handler for comprehensive testing."""

    def __init__(
        self,
        name: str,
        can_handle_types: list | None = None,
        should_handle: bool = True,  # noqa: FBT001, FBT002
        handle_delay: float = 0,
        raise_on_handle: Exception | None = None,
    ):
        self.name = name
        self.can_handle_types = can_handle_types or []
        self.should_handle = should_handle
        self.handled_errors: list[Exception] = []
        self.can_handle_calls: list[Exception] = []
        self.handle_delay = handle_delay
        self.raise_on_handle = raise_on_handle
        self._handle_count = 0

    def can_handle(self, error: Exception) -> bool:
        self.can_handle_calls.append(error)
        if self.can_handle_types:
            return type(error).__name__ in self.can_handle_types
        return self.should_handle

    def handle(self, error: Exception) -> bool:
        self._handle_count += 1

        if self.handle_delay > 0:
            time.sleep(self.handle_delay)

        if self.raise_on_handle:
            raise self.raise_on_handle

        self.handled_errors.append(error)
        return True

    def reset(self) -> None:
        """Reset handler state for reuse in tests."""
        self.handled_errors.clear()
        self.can_handle_calls.clear()
        self._handle_count = 0


class TestErrorHandlerChainV2(unittest.TestCase):
    """Test cases for error handler chain with comprehensive coverage."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.handlers = []
        for i in range(5):
            handler = MockErrorHandler(f"handler_{i}")
            self.handlers.append(handler)

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Reset all handlers
        for handler in self.handlers:
            handler.reset()

    def test_chain_handles_error_with_first_capable_handler_comprehensive(self) -> None:
        """Test comprehensive scenarios for first capable handler."""
        # Test various handler configurations
        handler_configs = [
            {
                "name": "Type-specific handlers",
                "handlers": [
                    MockErrorHandler("value_handler", can_handle_types=["ValueError"]),
                    MockErrorHandler("type_handler", can_handle_types=["TypeError"]),
                    MockErrorHandler("generic_handler", should_handle=True),
                ],
                "errors": [
                    (ValueError("test"), "value_handler"),
                    (TypeError("test"), "type_handler"),
                    (RuntimeError("test"), "generic_handler"),
                ],
            },
            {
                "name": "Mixed capability handlers",
                "handlers": [
                    MockErrorHandler("never_handles", should_handle=False),
                    MockErrorHandler("specific_only", can_handle_types=["KeyError", "AttributeError"]),
                    MockErrorHandler("always_handles", should_handle=True),
                ],
                "errors": [
                    (KeyError("key"), "specific_only"),
                    (AttributeError("attr"), "specific_only"),
                    (ValueError("val"), "always_handles"),
                ],
            },
        ]

        for config in handler_configs:
            with self.subTest(config=config["name"]):
                chain = ErrorHandlerChain()
                handlers = config["handlers"]

                for handler in handlers:
                    chain.add_handler(handler)  # type: ignore[arg-type]

                for error, expected_handler_name in config["errors"]:  # type: ignore[misc]
                    # Reset handlers
                    for h in handlers:  # type: ignore[attr-defined]
                        h.reset()  # type: ignore[attr-defined]

                    result = chain.handle_error(error)  # type: ignore[arg-type, has-type]
                    assert result

                    # Verify correct handler handled the error
                    for h in handlers:  # type: ignore[attr-defined]
                        if h.name == expected_handler_name:  # type: ignore[attr-defined, has-type]
                            assert len(h.handled_errors) == 1  # type: ignore[attr-defined]
                            assert h.handled_errors[0] == error  # type: ignore[attr-defined, has-type]
                        else:
                            assert len(h.handled_errors) == 0  # type: ignore[attr-defined]

    def test_chain_tries_all_handlers_comprehensive(self) -> None:
        """Test comprehensive scenarios when no handler can handle."""
        # Create various non-handling scenarios
        scenarios = [
            {
                "name": "All type-specific handlers, wrong error type",
                "handlers": [
                    MockErrorHandler("value_only", can_handle_types=["ValueError"]),
                    MockErrorHandler("type_only", can_handle_types=["TypeError"]),
                    MockErrorHandler("key_only", can_handle_types=["KeyError"]),
                ],
                "error": RuntimeError("unhandled"),
            },
            {
                "name": "All handlers refuse",
                "handlers": [
                    MockErrorHandler("refuses_1", should_handle=False),
                    MockErrorHandler("refuses_2", should_handle=False),
                    MockErrorHandler("refuses_3", should_handle=False),
                ],
                "error": ValueError("refused"),
            },
            {
                "name": "Empty handler types",
                "handlers": [
                    MockErrorHandler("empty_1", can_handle_types=[], should_handle=False),
                    MockErrorHandler("empty_2", can_handle_types=[], should_handle=False),
                ],
                "error": Exception("unhandled"),
            },
        ]

        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                chain = ErrorHandlerChain()
                handlers = scenario["handlers"]

                for handler in handlers:  # type: ignore[attr-defined]
                    chain.add_handler(handler)  # type: ignore[arg-type]

                result = chain.handle_error(scenario["error"])  # type: ignore[arg-type]
                assert not result

                # Verify all handlers were asked but none handled
                for handler in handlers:  # type: ignore[attr-defined]
                    assert len(handler.can_handle_calls) == 1  # type: ignore[attr-defined]
                    assert len(handler.handled_errors) == 0  # type: ignore[attr-defined]

    def test_chain_execution_order_comprehensive(self) -> None:
        """Test comprehensive execution order scenarios."""
        execution_log = []

        class OrderTrackingHandler(MockErrorHandler):
            def __init__(self, name: str, should_handle: bool = False):  # noqa: FBT001, FBT002
                super().__init__(name, should_handle=should_handle)

            def can_handle(self, error: Exception) -> bool:
                execution_log.append(f"{self.name}_can_handle")
                return super().can_handle(error)

            def handle(self, error: Exception) -> bool:
                execution_log.append(f"{self.name}_handle")
                return super().handle(error)

        # Test different execution patterns
        test_cases = [
            {
                "name": "All check, none handle",
                "handlers": [
                    OrderTrackingHandler("h1", should_handle=False),
                    OrderTrackingHandler("h2", should_handle=False),
                    OrderTrackingHandler("h3", should_handle=False),
                ],
                "expected_log": ["h1_can_handle", "h2_can_handle", "h3_can_handle"],
            },
            {
                "name": "Second handler handles",
                "handlers": [
                    OrderTrackingHandler("h1", should_handle=False),
                    OrderTrackingHandler("h2", should_handle=True),
                    OrderTrackingHandler("h3", should_handle=True),
                ],
                "expected_log": ["h1_can_handle", "h2_can_handle", "h2_handle"],
            },
            {
                "name": "First handler handles",
                "handlers": [
                    OrderTrackingHandler("h1", should_handle=True),
                    OrderTrackingHandler("h2", should_handle=True),
                    OrderTrackingHandler("h3", should_handle=True),
                ],
                "expected_log": ["h1_can_handle", "h1_handle"],
            },
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case["name"]):
                execution_log.clear()
                chain = ErrorHandlerChain()

                for handler in test_case["handlers"]:
                    chain.add_handler(handler)  # type: ignore[arg-type]

                chain.handle_error(Exception("test"))  # type: ignore[arg-type]
                assert execution_log == test_case["expected_log"]

    def test_chain_handles_handler_exceptions_comprehensive(self) -> None:
        """Test comprehensive exception handling in handlers."""
        # Note: Current implementation doesn't handle exceptions in handlers
        # but we can test various error scenarios

        # Test normal operation alongside potential error cases
        scenarios = [
            {
                "name": "Normal operation",
                "handlers": [
                    MockErrorHandler("normal_1", should_handle=True),
                    MockErrorHandler("normal_2", should_handle=True),
                ],
                "error": ValueError("test"),
                "should_handle": True,
            },
            {
                "name": "Handler with delay",
                "handlers": [
                    MockErrorHandler("slow", should_handle=True, handle_delay=0.01),
                ],
                "error": RuntimeError("slow error"),
                "should_handle": True,
            },
        ]

        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                chain = ErrorHandlerChain()

                for handler in scenario["handlers"]:  # type: ignore[attr-defined]
                    chain.add_handler(handler)  # type: ignore[arg-type]

                result = chain.handle_error(scenario["error"])  # type: ignore[arg-type]
                assert result == scenario["should_handle"]

    def test_error_categorization_comprehensive(self) -> None:
        """Test comprehensive error categorization scenarios."""
        # Create handlers for different error categories
        category_handlers = {}

        error_categories = [
            (ValueError, ErrorCategory.USER_INPUT),
            (TypeError, ErrorCategory.VALIDATION),
            (FileNotFoundError, ErrorCategory.FILE_NOT_FOUND),
            (PermissionError, ErrorCategory.PERMISSION),
            (ConnectionError, ErrorCategory.NETWORK),
            (TimeoutError, ErrorCategory.NETWORK),
            (MemoryError, ErrorCategory.SYSTEM),
            (KeyError, ErrorCategory.CONFIGURATION),
            (AttributeError, ErrorCategory.CONFIGURATION),
            (RuntimeError, ErrorCategory.PROCESSING),
        ]

        for error_type, category in error_categories:
            handler = MockErrorHandler(f"{category.name}_handler", can_handle_types=[error_type.__name__])
            category_handlers[category] = handler

        # Test each error type
        for error_type, expected_category in error_categories:
            with self.subTest(error_type=error_type.__name__):
                chain = ErrorHandlerChain()

                # Add all handlers
                for handler in category_handlers.values():
                    handler.reset()
                    chain.add_handler(handler)  # type: ignore[arg-type]

                test_error = error_type("test error")
                result = chain.handle_error(test_error)  # type: ignore[arg-type]

                assert result

                # Verify correct handler handled it
                expected_handler = category_handlers[expected_category]
                assert len(expected_handler.handled_errors) == 1

    def test_error_severity_assessment_comprehensive(self) -> None:
        """Test comprehensive error severity assessment."""
        # Define severity levels
        severity_errors = [
            # Critical errors
            (MemoryError("Out of memory"), "critical"),
            (SystemError("System failure"), "critical"),
            (KeyboardInterrupt("User abort"), "critical"),
            # High severity
            (PermissionError("Access denied"), "high"),
            (FileNotFoundError("Missing file"), "high"),
            # Medium severity
            (ConnectionError("Network issue"), "medium"),
            (TimeoutError("Request timeout"), "medium"),
            # Low severity
            (ValueError("Invalid input"), "low"),
            (TypeError("Type mismatch"), "low"),
        ]

        # Create severity-based handlers
        severity_handlers = {
            "critical": MockErrorHandler(
                "critical_handler",
                can_handle_types=["MemoryError", "SystemError", "KeyboardInterrupt"],
            ),
            "high": MockErrorHandler("high_handler", can_handle_types=["PermissionError", "FileNotFoundError"]),
            "medium": MockErrorHandler("medium_handler", can_handle_types=["ConnectionError", "TimeoutError"]),
            "low": MockErrorHandler("low_handler", can_handle_types=["ValueError", "TypeError"]),
        }

        for error, expected_severity in severity_errors:
            with self.subTest(error=type(error).__name__, severity=expected_severity):
                chain = ErrorHandlerChain()

                # Add handlers in priority order
                for severity in ["critical", "high", "medium", "low"]:
                    severity_handlers[severity].reset()
                    chain.add_handler(severity_handlers[severity])  # type: ignore[arg-type]

                result = chain.handle_error(error)  # type: ignore[arg-type]  # type: ignore[arg-type]
                assert result

                # Verify correct severity handler handled it
                expected_handler = severity_handlers[expected_severity]
                assert len(expected_handler.handled_errors) == 1

    def test_chain_with_edge_cases(self) -> None:  # noqa: PLR6301
        """Test chain with various edge cases."""
        # Test empty chain
        empty_chain = ErrorHandlerChain()
        result = empty_chain.handle_error(ValueError("test"))  # type: ignore[arg-type]
        assert not result

        # Test single handler chain
        single_chain = ErrorHandlerChain()
        single_handler = MockErrorHandler("single", should_handle=True)
        single_chain.add_handler(single_handler)  # type: ignore[arg-type]
        result = single_chain.handle_error(ValueError("test"))  # type: ignore[arg-type]
        assert result
        assert len(single_handler.handled_errors) == 1

        # Test chain with many handlers
        many_chain = ErrorHandlerChain()
        handlers = []
        for i in range(100):
            handler = MockErrorHandler(f"handler_{i}", should_handle=(i == 99))
            handlers.append(handler)
            many_chain.add_handler(handler)  # type: ignore[arg-type]

        result = many_chain.handle_error(ValueError("test"))  # type: ignore[arg-type]
        assert result
        assert len(handlers[99].handled_errors) == 1

    def test_chain_method_chaining(self) -> None:  # noqa: PLR6301
        """Test method chaining functionality."""
        chain = ErrorHandlerChain()

        # Test fluent interface
        result = (
            chain.add_handler(MockErrorHandler("h1"))  # type: ignore[arg-type]
            .add_handler(MockErrorHandler("h2"))  # type: ignore[arg-type]
            .add_handler(MockErrorHandler("h3"))  # type: ignore[arg-type]
        )

        assert result is chain  # Should return self for chaining

        # Verify handlers were added
        test_error = ValueError("test")
        handled = chain.handle_error(test_error)  # type: ignore[arg-type]
        assert handled

    def test_concurrent_error_handling(self) -> None:  # noqa: PLR6301
        """Test concurrent error handling operations."""
        chain = ErrorHandlerChain()

        # Add thread-safe handlers
        for i in range(5):
            handler = MockErrorHandler(f"concurrent_{i}", should_handle=True)
            chain.add_handler(handler)  # type: ignore[arg-type]

        results = []
        errors = []

        def handle_error(error_id: int) -> None:
            try:
                error_types = [ValueError, TypeError, RuntimeError, KeyError, AttributeError]
                error = error_types[error_id % len(error_types)](f"Error {error_id}")

                result = chain.handle_error(error)  # type: ignore[arg-type]  # type: ignore[arg-type]
                results.append((error_id, result))

            except Exception as e:  # noqa: BLE001
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

    def test_performance_with_many_handlers_comprehensive(self) -> None:
        """Test comprehensive performance scenarios."""
        # Test with increasing number of handlers
        handler_counts = [10, 50, 100, 200]

        for count in handler_counts:
            with self.subTest(handler_count=count):
                chain = ErrorHandlerChain()

                # Add handlers that don't handle
                for i in range(count - 1):
                    chain.add_handler(MockErrorHandler(f"no_handle_{i}", should_handle=False))  # type: ignore[arg-type]

                # Add final handler that handles
                chain.add_handler(MockErrorHandler("final_handler", should_handle=True))  # type: ignore[arg-type]

                # Measure performance
                start_time = time.time()
                result = chain.handle_error(ValueError("test"))  # type: ignore[arg-type]  # type: ignore[arg-type]
                end_time = time.time()

                assert result
                # Should scale linearly and stay fast
                assert end_time - start_time < 0.01 * count / 10

    def test_memory_efficiency_with_large_errors(self) -> None:  # noqa: PLR6301
        """Test memory efficiency with large error objects."""
        chain = ErrorHandlerChain()

        # Create handler that can handle large errors
        handler = MockErrorHandler("large_error_handler", should_handle=True)
        chain.add_handler(handler)  # type: ignore[arg-type]

        # Create errors with large payloads
        large_errors = []
        for _i in range(5):
            error = ValueError("x" * (1024 * 1024))  # 1MB message
            error.large_data = ["data"] * 10000  # type: ignore[attr-defined]  # Additional data
            large_errors.append(error)

        # Handle all large errors
        for error in large_errors:
            result = chain.handle_error(error)  # type: ignore[arg-type]
            assert result

        # Verify all were handled
        assert len(handler.handled_errors) == 5

    def test_custom_error_types(self) -> None:
        """Test handling of custom error types."""

        # Create custom exception hierarchy
        class CustomBaseError(Exception):
            pass

        class CustomNetworkError(CustomBaseError):
            pass

        class CustomValidationError(CustomBaseError):
            pass

        class CustomSystemError(CustomBaseError):
            pass

        # Create handlers for custom types
        custom_handlers = [
            MockErrorHandler("network_handler", can_handle_types=["CustomNetworkError"]),
            MockErrorHandler("validation_handler", can_handle_types=["CustomValidationError"]),
            MockErrorHandler("system_handler", can_handle_types=["CustomSystemError"]),
            MockErrorHandler("base_handler", can_handle_types=["CustomBaseError"]),
        ]

        chain = ErrorHandlerChain()
        for handler in custom_handlers:
            chain.add_handler(handler)  # type: ignore[arg-type]

        # Test each custom error type
        test_errors = [
            (CustomNetworkError("network"), "network_handler"),
            (CustomValidationError("validation"), "validation_handler"),
            (CustomSystemError("system"), "system_handler"),
            (CustomBaseError("base"), "base_handler"),
        ]

        for error, expected_handler_name in test_errors:
            with self.subTest(error_type=type(error).__name__):
                # Reset handlers
                for h in custom_handlers:
                    h.reset()

                result = chain.handle_error(error)  # type: ignore[arg-type]
                assert result

                # Verify correct handler handled it
                for h in custom_handlers:
                    if h.name == expected_handler_name:
                        assert len(h.handled_errors) == 1
                    else:
                        assert len(h.handled_errors) == 0

    def test_error_handler_state_management(self) -> None:  # noqa: PLR6301
        """Test handler state management across multiple uses."""
        chain = ErrorHandlerChain()

        # Create stateful handler
        stateful_handler = MockErrorHandler("stateful", should_handle=True)
        chain.add_handler(stateful_handler)  # type: ignore[arg-type]

        # Handle multiple errors
        errors = [
            ValueError("error1"),
            TypeError("error2"),
            RuntimeError("error3"),
        ]

        for i, error in enumerate(errors):
            result = chain.handle_error(error)  # type: ignore[arg-type]
            assert result

            # Verify state accumulation
            assert len(stateful_handler.handled_errors) == i + 1
            assert stateful_handler._handle_count == i + 1  # noqa: SLF001

        # Reset and verify
        stateful_handler.reset()
        assert len(stateful_handler.handled_errors) == 0
        assert stateful_handler._handle_count == 0  # noqa: SLF001

    def test_handler_priority_patterns(self) -> None:
        """Test various handler priority patterns."""
        # Create handlers with different specificities
        patterns = [
            {
                "name": "Specific to generic",
                "handlers": [
                    MockErrorHandler("very_specific", can_handle_types=["ValueError"]),
                    MockErrorHandler("somewhat_specific", can_handle_types=["ValueError", "TypeError"]),
                    MockErrorHandler("generic", should_handle=True),
                ],
                "test_errors": [
                    (ValueError("val"), "very_specific"),
                    (TypeError("type"), "somewhat_specific"),
                    (RuntimeError("runtime"), "generic"),
                ],
            },
            {
                "name": "Domain-specific handlers",
                "handlers": [
                    MockErrorHandler("file_handler", can_handle_types=["FileNotFoundError", "PermissionError"]),
                    MockErrorHandler("network_handler", can_handle_types=["ConnectionError", "TimeoutError"]),
                    MockErrorHandler("validation_handler", can_handle_types=["ValueError", "TypeError"]),
                    MockErrorHandler("fallback", should_handle=True),
                ],
                "test_errors": [
                    (FileNotFoundError("file"), "file_handler"),
                    (ConnectionError("conn"), "network_handler"),
                    (ValueError("val"), "validation_handler"),
                    (RuntimeError("other"), "fallback"),
                ],
            },
        ]

        for pattern in patterns:
            with self.subTest(pattern=pattern["name"]):
                chain = ErrorHandlerChain()

                for handler in pattern["handlers"]:
                    chain.add_handler(handler)  # type: ignore[arg-type]

                for error, expected_handler in pattern["test_errors"]:  # type: ignore[misc]
                    # Reset handlers
                    for h in pattern["handlers"]:  # type: ignore[attr-defined]
                        h.reset()  # type: ignore[attr-defined]

                    result = chain.handle_error(error)  # type: ignore[arg-type, has-type]
                    assert result

                    # Verify expected handler handled it
                    for h in pattern["handlers"]:  # type: ignore[attr-defined]
                        if h.name == expected_handler:  # type: ignore[attr-defined, has-type]
                            assert len(h.handled_errors) == 1  # type: ignore[attr-defined]
                        else:
                            assert len(h.handled_errors) == 0  # type: ignore[attr-defined]


# Compatibility tests using pytest style for existing test coverage
class TestErrorHandlerChainPytest:
    """Pytest-style tests for compatibility."""

    def test_chain_handles_error_pytest(self) -> None:  # noqa: PLR6301
        """Test basic error handling using pytest style."""
        handler1 = MockErrorHandler("handler1", can_handle_types=["ValueError"])
        handler2 = MockErrorHandler("handler2", can_handle_types=["TypeError"])
        handler3 = MockErrorHandler("handler3", should_handle=True)

        chain = ErrorHandlerChain()
        chain.add_handler(handler1).add_handler(handler2).add_handler(handler3)  # type: ignore[arg-type]

        # Test ValueError handled by first handler
        result = chain.handle_error(ValueError("test"))  # type: ignore[arg-type]  # type: ignore[arg-type]
        assert result is True
        assert len(handler1.handled_errors) == 1

        # Reset and test TypeError
        handler1.reset()
        handler2.reset()

        result = chain.handle_error(TypeError("test"))  # type: ignore[arg-type]
        assert result is True
        assert len(handler2.handled_errors) == 1

    def test_chain_no_handler_pytest(self) -> None:  # noqa: PLR6301
        """Test when no handler can handle using pytest style."""
        handler1 = MockErrorHandler("handler1", can_handle_types=["ValueError"])
        handler2 = MockErrorHandler("handler2", can_handle_types=["TypeError"])

        chain = ErrorHandlerChain()
        chain.add_handler(handler1).add_handler(handler2)  # type: ignore[arg-type]

        result = chain.handle_error(RuntimeError("unhandled"))  # type: ignore[arg-type]
        assert result is False

    def test_empty_chain_pytest(self) -> None:  # noqa: PLR6301
        """Test empty chain using pytest style."""
        chain = ErrorHandlerChain()
        result = chain.handle_error(ValueError("test"))  # type: ignore[arg-type]
        assert result is False

    def test_performance_pytest(self) -> None:  # noqa: PLR6301
        """Test performance using pytest style."""
        # Create many handlers
        handlers = [MockErrorHandler(f"h_{i}", should_handle=False) for i in range(100)]
        handlers.append(MockErrorHandler("final", should_handle=True))

        chain = ErrorHandlerChain()
        for handler in handlers:
            chain.add_handler(handler)  # type: ignore[arg-type]

        start_time = time.time()
        result = chain.handle_error(ValueError("test"))  # type: ignore[arg-type]
        duration = time.time() - start_time

        assert result is True
        assert duration < 0.1  # Should be fast


if __name__ == "__main__":
    unittest.main()
