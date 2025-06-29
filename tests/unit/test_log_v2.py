"""Optimized logging tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for logger setup and teardown
- Parameterized test scenarios for comprehensive logging validation
- Enhanced error handling and edge case coverage
- Mock-based testing to avoid actual log output during tests
- Comprehensive handler and formatter testing scenarios
"""

import logging
from unittest.mock import MagicMock, patch, call
import pytest
from io import StringIO

from goesvfi.utils import log


class TestLoggingV2:
    """Optimized test class for logging functionality."""

    @pytest.fixture(scope="class")
    def logging_scenarios(self):
        """Define various logging scenarios for testing."""
        return {
            "debug_enabled": {"debug_mode": True, "expected_level": logging.DEBUG},
            "debug_disabled": {"debug_mode": False, "expected_level": logging.INFO},
            "warning_level": {"debug_mode": False, "expected_level": logging.WARNING},
            "error_level": {"debug_mode": False, "expected_level": logging.ERROR},
        }

    @pytest.fixture
    def logger_cleanup(self):
        """Ensure clean logger state for each test."""
        # Store original state
        original_handler = log._handler
        original_level = log._LEVEL
        
        yield
        
        # Restore original state
        log._handler = original_handler
        log._LEVEL = original_level

    @pytest.fixture
    def mock_colorlog_module(self):
        """Create mock colorlog module for testing."""
        mock_module = MagicMock()
        
        class MockStreamHandler(logging.StreamHandler):
            pass
        
        class MockColoredFormatter(logging.Formatter):
            def __init__(self, *args, **kwargs):
                # Extract only valid arguments for base Formatter
                valid_args = []
                if args:
                    valid_args.append(args[0])  # format string
                super().__init__(*valid_args)
        
        mock_module.StreamHandler = MockStreamHandler
        mock_module.ColoredFormatter = MockColoredFormatter
        return mock_module

    def test_get_logger_default_configuration(self, logger_cleanup):
        """Test logger creation with default configuration."""
        logger_name = "test_default_logger"
        logger = log.get_logger(logger_name)
        
        # Verify logger properties
        assert logger.name == logger_name
        assert logger.level == log._LEVEL
        assert len(logger.handlers) > 0
        
        # Verify handler configuration
        handler = logger.handlers[0]
        assert handler.formatter is not None
        assert handler.level <= log._LEVEL

    @pytest.mark.parametrize("scenario_name", [
        "debug_enabled",
        "debug_disabled"
    ])
    def test_set_level_scenarios(self, logger_cleanup, logging_scenarios, scenario_name):
        """Test logging level changes with various scenarios."""
        scenario = logging_scenarios[scenario_name]
        
        # Set the logging level
        log.set_level(debug_mode=scenario["debug_mode"])
        
        # Verify level changes
        assert log._LEVEL == scenario["expected_level"]
        
        if log._handler:
            assert log._handler.level == scenario["expected_level"]
        
        # Create logger after level change
        logger = log.get_logger(f"test_logger_{scenario_name}")
        assert logger.level == scenario["expected_level"]

    def test_logger_handler_reuse(self, logger_cleanup):
        """Test that handlers are properly reused and not duplicated."""
        logger_name = "reuse_test_logger"
        
        # Get logger multiple times
        logger1 = log.get_logger(logger_name)
        initial_handler_count = len(logger1.handlers)
        
        logger2 = log.get_logger(logger_name)
        logger3 = log.get_logger(logger_name)
        
        # Should be the same logger instance
        assert logger1 is logger2 is logger3
        
        # Handler count should not increase
        assert len(logger2.handlers) == initial_handler_count
        assert len(logger3.handlers) == initial_handler_count

    def test_colorlog_integration(self, logger_cleanup, mock_colorlog_module):
        """Test integration with colorlog module when available."""
        with patch("goesvfi.utils.log.colorlog_module", mock_colorlog_module):
            # Reset handler to force rebuild
            log._handler = None
            
            logger = log.get_logger("colorlog_test_logger")
            handler = log._handler
            
            # Verify colorlog components are used
            assert isinstance(handler, mock_colorlog_module.StreamHandler)
            assert isinstance(handler.formatter, mock_colorlog_module.ColoredFormatter)
            assert handler in logger.handlers

    def test_logging_without_colorlog(self, logger_cleanup):
        """Test logging functionality when colorlog is not available."""
        with patch("goesvfi.utils.log.colorlog_module", None):
            # Reset handler to force rebuild
            log._handler = None
            
            logger = log.get_logger("no_colorlog_test_logger")
            handler = log._handler
            
            # Verify standard logging components are used
            assert isinstance(handler, logging.StreamHandler)
            assert isinstance(handler.formatter, logging.Formatter)
            assert not hasattr(handler.formatter, 'log_colors')  # Not a ColoredFormatter

    @pytest.mark.parametrize("logger_name,expected_name", [
        ("simple_name", "simple_name"),
        ("module.submodule", "module.submodule"),
        ("", ""),  # Empty name
        ("name_with_123_numbers", "name_with_123_numbers"),
        ("name-with-dashes", "name-with-dashes"),
        ("name.with.many.dots.test", "name.with.many.dots.test")
    ])
    def test_logger_naming_scenarios(self, logger_cleanup, logger_name, expected_name):
        """Test logger creation with various naming scenarios."""
        logger = log.get_logger(logger_name)
        assert logger.name == expected_name

    def test_multiple_logger_independence(self, logger_cleanup):
        """Test that multiple loggers maintain independence."""
        logger_names = ["logger_a", "logger_b", "logger_c"]
        loggers = {}
        
        for name in logger_names:
            loggers[name] = log.get_logger(name)
        
        # Verify all loggers are different instances
        logger_instances = list(loggers.values())
        for i, logger1 in enumerate(logger_instances):
            for j, logger2 in enumerate(logger_instances):
                if i != j:
                    assert logger1 is not logger2
        
        # Verify they all share the same handler type
        for logger in logger_instances:
            assert len(logger.handlers) > 0
            assert isinstance(logger.handlers[0], type(log._handler))

    def test_logging_level_transitions(self, logger_cleanup):
        """Test various logging level transitions."""
        test_logger = log.get_logger("transition_test")
        
        # Test multiple level changes
        level_sequences = [
            (True, logging.DEBUG),
            (False, logging.INFO),
            (True, logging.DEBUG),
            (False, logging.INFO)
        ]
        
        for debug_mode, expected_level in level_sequences:
            log.set_level(debug_mode=debug_mode)
            assert log._LEVEL == expected_level
            
            # Create new logger to verify level inheritance
            new_logger = log.get_logger(f"level_test_{expected_level}")
            assert new_logger.level == expected_level

    def test_handler_formatter_configuration(self, logger_cleanup):
        """Test handler and formatter configuration details."""
        logger = log.get_logger("formatter_test")
        handler = logger.handlers[0]
        formatter = handler.formatter
        
        # Verify formatter is properly configured
        assert formatter is not None
        assert hasattr(formatter, '_fmt') or hasattr(formatter, '_style')
        
        # Test that formatter can format log records
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Test message", args=(), exc_info=None
        )
        
        formatted_message = formatter.format(record)
        assert isinstance(formatted_message, str)
        assert len(formatted_message) > 0

    def test_logging_output_capture(self, logger_cleanup):
        """Test actual logging output with captured streams."""
        # Create a string buffer to capture log output
        log_stream = StringIO()
        
        # Create logger with custom handler
        test_logger = logging.getLogger("output_test")
        test_logger.setLevel(logging.DEBUG)
        
        # Remove any existing handlers
        test_logger.handlers.clear()
        
        # Add stream handler with our buffer
        stream_handler = logging.StreamHandler(log_stream)
        stream_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        stream_handler.setFormatter(formatter)
        test_logger.addHandler(stream_handler)
        
        # Test different log levels
        test_messages = [
            (logging.DEBUG, "Debug message"),
            (logging.INFO, "Info message"),
            (logging.WARNING, "Warning message"),
            (logging.ERROR, "Error message")
        ]
        
        for level, message in test_messages:
            test_logger.log(level, message)
        
        # Verify output
        log_output = log_stream.getvalue()
        for level, message in test_messages:
            assert message in log_output
            assert logging.getLevelName(level) in log_output

    def test_handler_level_synchronization(self, logger_cleanup):
        """Test that handler levels stay synchronized with global level."""
        # Set initial level
        log.set_level(debug_mode=False)
        initial_level = log._LEVEL
        
        # Create logger
        logger = log.get_logger("sync_test")
        
        # Change level and verify synchronization
        log.set_level(debug_mode=True)
        new_level = log._LEVEL
        
        assert new_level != initial_level
        assert log._handler.level == new_level
        
        # New loggers should inherit the new level
        new_logger = log.get_logger("sync_test_2")
        assert new_logger.level == new_level

    def test_logging_edge_cases(self, logger_cleanup):
        """Test logging behavior with edge cases."""
        edge_cases = [
            None,  # None as logger name
            123,   # Number as logger name
            [],    # List as logger name
            {},    # Dict as logger name
        ]
        
        for edge_case in edge_cases:
            try:
                # Some edge cases might raise exceptions
                logger = log.get_logger(edge_case)
                assert logger is not None
            except (TypeError, ValueError):
                # Expected for invalid inputs
                pass

    def test_concurrent_logger_access_simulation(self, logger_cleanup):
        """Simulate concurrent access to logger functionality."""
        import threading
        import time
        
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                # Simulate concurrent logger creation and level changes
                logger = log.get_logger(f"worker_{worker_id}")
                log.set_level(debug_mode=worker_id % 2 == 0)
                results.append(f"worker_{worker_id}_success")
                time.sleep(0.01)  # Small delay
            except Exception as e:
                errors.append(f"worker_{worker_id}_error: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 10
        assert len(errors) == 0

    def test_log_module_state_isolation(self, logger_cleanup):
        """Test that log module state is properly isolated between tests."""
        # Change state
        original_level = log._LEVEL
        log.set_level(debug_mode=True)
        
        # Create logger
        logger = log.get_logger("isolation_test")
        
        # Verify state change
        assert log._LEVEL != original_level
        assert logger.level == log._LEVEL
        
        # The cleanup fixture should restore state after test