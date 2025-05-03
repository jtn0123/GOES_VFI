import logging
import sys
import types
from unittest.mock import patch

import pytest

import goesvfi.utils.log as log


def test_get_logger_default_level_and_handler():
    logger = log.get_logger("test_logger")
    assert logger.level == log._LEVEL
    # The handler should be added to the logger
    handler_types = [type(h) for h in logger.handlers]
    assert type(log._handler) in handler_types
    # The handler's formatter should be set
    assert logger.handlers[0].formatter is not None


def test_set_level_changes_level_and_handler_level():
    log.set_level(debug_mode=True)
    assert log._LEVEL == logging.DEBUG
    if log._handler:
        assert log._handler.level == logging.DEBUG

    log.set_level(debug_mode=False)
    assert log._LEVEL == logging.INFO
    if log._handler:
        assert log._handler.level == logging.INFO


def test_get_logger_adds_handler_once():
    logger = log.get_logger("unique_logger")
    initial_handler_count = len(logger.handlers)
    # Calling get_logger again should not add another handler of the same type
    logger2 = log.get_logger("unique_logger")
    assert len(logger2.handlers) == initial_handler_count


@patch("goesvfi.utils.log.colorlog_module", create=True)
def test_handler_type_and_formatter_with_colorlog(mock_colorlog_module):
    # Create a mock colorlog module with StreamHandler and ColoredFormatter
    class MockStreamHandler(logging.StreamHandler):
        pass

    class MockColoredFormatter(logging.Formatter):
        # Add **kwargs to initializer to accept unexpected args
        def __init__(self, *args, **kwargs):
            super().__init__(*args)

    mock_colorlog_module.StreamHandler = MockStreamHandler
    mock_colorlog_module.ColoredFormatter = MockColoredFormatter

    # Reset handler to None to force rebuild
    log._handler = None
    logger = log.get_logger("colorlog_logger")
    handler = log._handler
    assert isinstance(handler, MockStreamHandler)
    assert isinstance(handler.formatter, MockColoredFormatter)
    assert handler in logger.handlers


@patch("goesvfi.utils.log.colorlog_module", None)
def test_handler_type_and_formatter_without_colorlog():
    # Reset handler to None to force rebuild
    log._handler = None
    logger = log.get_logger("no_colorlog_logger")
    handler = log._handler
    assert isinstance(handler, logging.StreamHandler)
    # Formatter should be logging.Formatter (not colorlog.ColoredFormatter)
    assert isinstance(handler.formatter, logging.Formatter)
    assert handler in logger.handlers
