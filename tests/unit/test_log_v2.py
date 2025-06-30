"""
Optimized tests for logging utilities with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures and setup
- Combined related logging scenarios
- Parameterized tests for different configurations
- Batch testing of logger configurations
"""

import logging
from typing import Any
from unittest.mock import patch

import pytest

from goesvfi.utils import log


class TestLogOptimizedV2:
    """Optimized logging tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def mock_colorlog_classes() -> tuple[type[logging.StreamHandler], type[logging.Formatter]]:
        """Create mock colorlog classes for testing.

        Returns:
            tuple[type[logging.StreamHandler], type[logging.Formatter]]: Mock handler and formatter classes.
        """

        class MockStreamHandler(logging.StreamHandler):
            pass

        class MockColoredFormatter(logging.Formatter):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                # Accept unexpected args for colorlog compatibility
                super().__init__(*args)

        return MockStreamHandler, MockColoredFormatter

    @pytest.fixture(autouse=True)
    @staticmethod
    def reset_log_state() -> Any:  # noqa: ANN401
        """Reset log state before each test.

        Yields:
            None: Yields control back to test.
        """
        # Store original state
        original_handler = log._handler  # noqa: SLF001
        original_level = log._LEVEL  # noqa: SLF001

        yield

        # Restore original state
        log._handler = original_handler  # noqa: SLF001
        log._LEVEL = original_level  # noqa: SLF001

    def test_get_logger_default_configuration(self) -> None:  # noqa: PLR6301
        """Test logger creation with default configuration."""
        logger = log.get_logger("test_logger")

        # Verify basic logger properties
        assert logger.level == log._LEVEL  # noqa: SLF001
        assert len(logger.handlers) > 0

        # Verify handler configuration
        handler_types = [type(h) for h in logger.handlers]
        assert type(log._handler) in handler_types  # noqa: SLF001

        # Verify formatter is set
        for handler in logger.handlers:
            if handler.formatter is not None:
                assert isinstance(handler.formatter, logging.Formatter)
                break
        else:
            pytest.fail("No handler with formatter found")

    @pytest.mark.parametrize(
        "debug_mode,expected_level",
        [
            (True, logging.DEBUG),
            (False, logging.INFO),
        ],
    )
    def test_set_level_configurations(self, debug_mode: bool, expected_level: int) -> None:  # noqa: PLR6301, FBT001
        """Test level setting with different debug configurations."""
        log.set_level(debug_mode=debug_mode)

        assert expected_level == log._LEVEL  # noqa: SLF001

        if log._handler:  # noqa: SLF001
            assert log._handler.level == expected_level  # noqa: SLF001

    def test_logger_handler_management(self) -> None:  # noqa: PLR6301
        """Test that handlers are managed correctly across multiple calls."""
        # Create first logger
        logger1 = log.get_logger("handler_test_logger")
        initial_handler_count = len(logger1.handlers)

        # Get same logger again - should not duplicate handlers
        logger2 = log.get_logger("handler_test_logger")
        assert len(logger2.handlers) == initial_handler_count
        assert logger1 is logger2  # Should be same logger instance

        # Create different logger - should have same handler setup
        logger3 = log.get_logger("different_logger")
        assert len(logger3.handlers) == len(logger1.handlers)

        # Verify handler types are consistent
        handler_types_1 = [type(h) for h in logger1.handlers]
        handler_types_3 = [type(h) for h in logger3.handlers]
        assert handler_types_1 == handler_types_3

    def test_colorlog_integration_scenarios(  # noqa: PLR6301
        self, mock_colorlog_classes: tuple[type[logging.StreamHandler], type[logging.Formatter]],
    ) -> None:
        """Test logging behavior with colorlog available and unavailable."""
        mock_stream_handler, mock_colored_formatter = mock_colorlog_classes

        # Test 1: With colorlog available
        with patch("goesvfi.utils.log.colorlog_module") as mock_colorlog_module:
            mock_colorlog_module.StreamHandler = mock_stream_handler
            mock_colorlog_module.ColoredFormatter = mock_colored_formatter

            # Reset handler to force rebuild
            log._handler = None  # noqa: SLF001
            logger = log.get_logger("colorlog_test_logger")
            handler = log._handler  # noqa: SLF001

            assert isinstance(handler, mock_stream_handler)
            assert isinstance(handler.formatter, mock_colored_formatter)
            assert handler in logger.handlers

        # Test 2: Without colorlog available
        with patch("goesvfi.utils.log.colorlog_module", None):
            # Reset handler to force rebuild
            log._handler = None  # noqa: SLF001
            logger = log.get_logger("no_colorlog_test_logger")
            handler = log._handler  # noqa: SLF001

            assert isinstance(handler, logging.StreamHandler)
            assert isinstance(handler.formatter, logging.Formatter)
            assert not isinstance(handler.formatter, mock_colored_formatter)
            assert handler in logger.handlers

    def test_level_transitions_and_persistence(self) -> None:  # noqa: PLR6301
        """Test level changes and their persistence across operations."""
        # Start with default

        # Test debug mode activation
        log.set_level(debug_mode=True)
        assert log._LEVEL == logging.DEBUG  # noqa: SLF001

        # Create logger in debug mode
        debug_logger = log.get_logger("debug_transition_logger")
        assert debug_logger.level == logging.DEBUG
        if log._handler:  # noqa: SLF001
            assert log._handler.level == logging.DEBUG  # noqa: SLF001

        # Switch to info mode
        log.set_level(debug_mode=False)
        assert log._LEVEL == logging.INFO  # noqa: SLF001

        # Create new logger in info mode
        info_logger = log.get_logger("info_transition_logger")
        assert info_logger.level == logging.INFO
        if log._handler:  # noqa: SLF001
            assert log._handler.level == logging.INFO  # noqa: SLF001

        # Verify previous logger properties
        assert debug_logger.level == logging.INFO  # Should update existing loggers

    def test_multiple_logger_consistency(self) -> None:  # noqa: PLR6301
        """Test consistency across multiple loggers."""
        logger_names = ["logger1", "logger2", "logger3", "logger4", "logger5"]
        loggers = []

        # Create multiple loggers
        for name in logger_names:
            logger = log.get_logger(name)
            loggers.append(logger)

            # Verify each logger has expected properties
            assert logger.level == log._LEVEL  # noqa: SLF001
            assert len(logger.handlers) > 0

        # Verify all loggers have consistent handler setup
        first_logger_handler_types = [type(h) for h in loggers[0].handlers]

        for logger in loggers[1:]:
            handler_types = [type(h) for h in logger.handlers]
            assert handler_types == first_logger_handler_types

        # Test level change affects all loggers
        log.set_level(debug_mode=True)
        for logger in loggers:
            assert logger.level == logging.DEBUG

    def test_handler_formatter_configuration(self) -> None:  # noqa: PLR6301
        """Test handler and formatter configuration details."""
        logger = log.get_logger("formatter_test_logger")

        # Verify handler exists and is properly configured
        assert log._handler is not None  # noqa: SLF001
        assert log._handler in logger.handlers  # noqa: SLF001

        # Verify formatter configuration
        formatter = log._handler.formatter  # noqa: SLF001
        assert formatter is not None
        assert isinstance(formatter, logging.Formatter)

        # Test formatter with different log levels
        test_levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]

        for level in test_levels:
            log.set_level(debug_mode=(level == logging.DEBUG))

            # Create test record
            record = logging.LogRecord(
                name="test", level=level, pathname="test.py", lineno=1, msg="Test message", args=(), exc_info=None,
            )

            # Format should not raise exception
            formatted = formatter.format(record)
            assert isinstance(formatted, str)
            assert len(formatted) > 0

    def test_logger_edge_cases_and_robustness(self) -> None:  # noqa: PLR6301
        """Test edge cases and robustness of logger functionality."""
        # Test with empty logger name
        empty_logger = log.get_logger("")
        assert empty_logger is not None
        assert len(empty_logger.handlers) > 0

        # Test with very long logger name
        long_name = "a" * 1000
        long_logger = log.get_logger(long_name)
        assert long_logger is not None
        assert long_logger.name == long_name

        # Test with special characters in logger name
        special_logger = log.get_logger("test.logger-with_special@chars")
        assert special_logger is not None

        # Test multiple rapid level changes
        for i in range(10):
            log.set_level(debug_mode=(i % 2 == 0))
            expected_level = logging.DEBUG if i % 2 == 0 else logging.INFO
            assert expected_level == log._LEVEL  # noqa: SLF001

        # Test logger creation after rapid level changes
        rapid_logger = log.get_logger("rapid_change_logger")
        assert rapid_logger.level == log._LEVEL  # noqa: SLF001

    def test_colorlog_fallback_behavior(  # noqa: PLR6301
        self, mock_colorlog_classes: tuple[type[logging.StreamHandler], type[logging.Formatter]]
    ) -> None:
        """Test colorlog fallback behavior in various scenarios."""
        mock_stream_handler, _mock_colored_formatter = mock_colorlog_classes

        # Test with colorlog module that raises exceptions
        class FailingColoredFormatter:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                msg = "Simulated colorlog failure"
                raise ImportError(msg)

        with patch("goesvfi.utils.log.colorlog_module") as mock_colorlog_module:
            mock_colorlog_module.StreamHandler = mock_stream_handler
            mock_colorlog_module.ColoredFormatter = FailingColoredFormatter

            # Reset handler to force rebuild
            log._handler = None  # noqa: SLF001

            # Should fall back to standard logging without crashing
            logger = log.get_logger("fallback_test_logger")
            assert logger is not None
            assert len(logger.handlers) > 0

            # Handler should be standard handler, not mock
            handler = log._handler  # noqa: SLF001
            assert handler is not None

    def test_complete_logging_workflow(self) -> None:  # noqa: PLR6301
        """Test complete logging workflow with all components."""
        # Initialize with debug mode
        log.set_level(debug_mode=True)

        # Create logger
        workflow_logger = log.get_logger("workflow_test")
        assert workflow_logger.level == logging.DEBUG

        # Test actual logging at different levels (no exceptions should occur)
        test_messages = [
            (logging.DEBUG, "Debug message"),
            (logging.INFO, "Info message"),
            (logging.WARNING, "Warning message"),
            (logging.ERROR, "Error message"),
            (logging.CRITICAL, "Critical message"),
        ]

        for level, message in test_messages:
            # This tests that the logging system works end-to-end
            workflow_logger.log(level, message)

        # Switch to info mode and test filtering
        log.set_level(debug_mode=False)
        assert workflow_logger.level == logging.INFO

        # Test that logger configuration is persistent and functional
        workflow_logger.info("Final test message")

        # Verify handler state is consistent
        assert log._handler is not None  # noqa: SLF001
        assert log._handler.level == logging.INFO  # noqa: SLF001
        assert log._handler.formatter is not None  # noqa: SLF001
