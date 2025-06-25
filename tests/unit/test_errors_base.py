"""
Tests for error handling base classes and utilities.

Tests the StructuredError, ErrorContext, ErrorBuilder, and ErrorCategory
classes to ensure proper error handling framework functionality.
"""

import pytest
from datetime import datetime
from goesvfi.utils.errors.base import (
    ErrorCategory,
    ErrorContext,
    StructuredError,
    ErrorBuilder,
)


class TestErrorCategory:
    """Test error category enumeration."""

    def test_error_categories_exist(self):
        """Test that all expected error categories are defined."""
        expected_categories = [
            'VALIDATION', 'PERMISSION', 'FILE_NOT_FOUND', 'NETWORK',
            'PROCESSING', 'CONFIGURATION', 'SYSTEM', 'USER_INPUT',
            'EXTERNAL_TOOL', 'UNKNOWN'
        ]
        
        for category_name in expected_categories:
            assert hasattr(ErrorCategory, category_name)
            assert isinstance(getattr(ErrorCategory, category_name), ErrorCategory)

    def test_category_uniqueness(self):
        """Test that each category has a unique value."""
        categories = list(ErrorCategory)
        values = [cat.value for cat in categories]
        assert len(values) == len(set(values))  # All values should be unique


class TestErrorContext:
    """Test error context data structure."""

    def test_context_creation_minimal(self):
        """Test creating context with minimal parameters."""
        context = ErrorContext(operation="test_op", component="test_comp")
        
        assert context.operation == "test_op"
        assert context.component == "test_comp"
        assert isinstance(context.timestamp, datetime)
        assert context.user_data == {}
        assert context.system_data == {}
        assert context.trace_id is None

    def test_context_creation_full(self):
        """Test creating context with all parameters."""
        timestamp = datetime.now()
        user_data = {"key1": "value1"}
        system_data = {"key2": "value2"}
        trace_id = "trace123"
        
        context = ErrorContext(
            operation="test_op",
            component="test_comp",
            timestamp=timestamp,
            user_data=user_data,
            system_data=system_data,
            trace_id=trace_id
        )
        
        assert context.operation == "test_op"
        assert context.component == "test_comp"
        assert context.timestamp == timestamp
        assert context.user_data == user_data
        assert context.system_data == system_data
        assert context.trace_id == trace_id

    def test_add_user_data(self):
        """Test adding user data to context."""
        context = ErrorContext(operation="test", component="test")
        
        context.add_user_data("key1", "value1")
        context.add_user_data("key2", 42)
        
        assert context.user_data["key1"] == "value1"
        assert context.user_data["key2"] == 42

    def test_add_system_data(self):
        """Test adding system data to context."""
        context = ErrorContext(operation="test", component="test")
        
        context.add_system_data("debug_info", "test_debug")
        context.add_system_data("error_code", 123)
        
        assert context.system_data["debug_info"] == "test_debug"
        assert context.system_data["error_code"] == 123


class TestStructuredError:
    """Test structured error class."""

    def test_minimal_error_creation(self):
        """Test creating error with minimal parameters."""
        error = StructuredError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.category == ErrorCategory.UNKNOWN
        assert error.context.operation == "unknown"
        assert error.context.component == "unknown"
        assert error.cause is None
        assert error.recoverable is False
        assert error.user_message == "Test error message"
        assert error.suggestions == []

    def test_full_error_creation(self):
        """Test creating error with all parameters."""
        context = ErrorContext(operation="test_op", component="test_comp")
        cause = ValueError("Original error")
        suggestions = ["Try this", "Try that"]
        
        error = StructuredError(
            message="Test error",
            category=ErrorCategory.VALIDATION,
            context=context,
            cause=cause,
            recoverable=True,
            user_message="User-friendly message",
            suggestions=suggestions
        )
        
        assert error.message == "Test error"
        assert error.category == ErrorCategory.VALIDATION
        assert error.context == context
        assert error.cause == cause
        assert error.recoverable is True
        assert error.user_message == "User-friendly message"
        assert error.suggestions == suggestions

    def test_validation_error_classmethod(self):
        """Test validation error factory method."""
        error = StructuredError.validation_error(
            message="Invalid input",
            field="username",
            value="test@",
            suggestions=["Use alphanumeric characters"]
        )
        
        assert error.category == ErrorCategory.VALIDATION
        assert error.recoverable is True
        assert error.context.operation == "validation"
        assert error.context.component == "input"
        assert error.context.user_data["field"] == "username"
        assert error.context.user_data["value"] == "test@"
        assert "Use alphanumeric characters" in error.suggestions

    def test_file_error_classmethod(self):
        """Test file error factory method."""
        cause = FileNotFoundError("File not found")
        error = StructuredError.file_error(
            message="File not found: test.txt",
            file_path="/path/to/test.txt",
            operation="read_file",
            cause=cause
        )
        
        assert error.category == ErrorCategory.FILE_NOT_FOUND
        assert error.recoverable is True
        assert error.context.operation == "read_file"
        assert error.context.component == "filesystem"
        assert error.context.user_data["file_path"] == "/path/to/test.txt"
        assert error.cause == cause

    def test_file_error_permission_detection(self):
        """Test file error detects permission issues."""
        error = StructuredError.file_error(
            message="Permission denied accessing file",
            file_path="/restricted/file.txt"
        )
        
        assert error.category == ErrorCategory.PERMISSION

    def test_network_error_classmethod(self):
        """Test network error factory method."""
        error = StructuredError.network_error(
            message="Connection failed",
            url="https://example.com",
            status_code=404
        )
        
        assert error.category == ErrorCategory.NETWORK
        assert error.recoverable is True
        assert error.context.operation == "network_request"
        assert error.context.component == "network"
        assert error.context.user_data["url"] == "https://example.com"
        assert error.context.user_data["status_code"] == 404
        assert "Check network connection" in error.suggestions

    def test_processing_error_classmethod(self):
        """Test processing error factory method."""
        error = StructuredError.processing_error(
            message="Processing failed",
            stage="image_resize",
            input_data="input.jpg"
        )
        
        assert error.category == ErrorCategory.PROCESSING
        assert error.recoverable is False
        assert error.context.operation == "data_processing"
        assert error.context.component == "processor"
        assert error.context.user_data["processing_stage"] == "image_resize"
        assert error.context.system_data["input_data"] == "input.jpg"

    def test_configuration_error_classmethod(self):
        """Test configuration error factory method."""
        error = StructuredError.configuration_error(
            message="Invalid config value",
            config_key="max_threads",
            config_value=-1,
            suggestions=["Use positive integer"]
        )
        
        assert error.category == ErrorCategory.CONFIGURATION
        assert error.recoverable is True
        assert error.context.operation == "configuration"
        assert error.context.component == "config"
        assert error.context.user_data["config_key"] == "max_threads"
        assert error.context.user_data["config_value"] == "-1"
        assert "Use positive integer" in error.suggestions

    def test_external_tool_error_classmethod(self):
        """Test external tool error factory method."""
        error = StructuredError.external_tool_error(
            message="Tool execution failed",
            tool_name="ffmpeg",
            command="ffmpeg -i input.mp4 output.mp4",
            exit_code=1
        )
        
        assert error.category == ErrorCategory.EXTERNAL_TOOL
        assert error.recoverable is True
        assert error.context.operation == "external_tool"
        assert error.context.component == "ffmpeg"
        assert error.context.user_data["tool_name"] == "ffmpeg"
        assert error.context.system_data["command"] == "ffmpeg -i input.mp4 output.mp4"
        assert error.context.system_data["exit_code"] == 1
        assert "Check that ffmpeg is installed" in error.suggestions

    def test_add_suggestion(self):
        """Test adding suggestions to error."""
        error = StructuredError("Test error")
        
        error.add_suggestion("First suggestion")
        error.add_suggestion("Second suggestion")
        
        assert len(error.suggestions) == 2
        assert "First suggestion" in error.suggestions
        assert "Second suggestion" in error.suggestions

    def test_to_dict(self):
        """Test converting error to dictionary."""
        context = ErrorContext(operation="test", component="test")
        context.add_user_data("key", "value")
        
        error = StructuredError(
            message="Test error",
            category=ErrorCategory.VALIDATION,
            context=context,
            recoverable=True,
            user_message="User message",
            suggestions=["Suggestion 1"]
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["message"] == "Test error"
        assert error_dict["category"] == "VALIDATION"
        assert error_dict["user_message"] == "User message"
        assert error_dict["recoverable"] is True
        assert error_dict["suggestions"] == ["Suggestion 1"]
        assert error_dict["context"]["operation"] == "test"
        assert error_dict["context"]["component"] == "test"
        assert error_dict["context"]["user_data"]["key"] == "value"

    def test_get_user_friendly_message(self):
        """Test getting user-friendly message."""
        error = StructuredError(
            "Technical error",
            user_message="User-friendly error",
            suggestions=["Try this", "Try that"]
        )
        
        friendly_message = error.get_user_friendly_message()
        
        assert "User-friendly error" in friendly_message
        assert "• Try this" in friendly_message
        assert "• Try that" in friendly_message

    def test_get_user_friendly_message_no_suggestions(self):
        """Test user-friendly message without suggestions."""
        error = StructuredError("Test error", user_message="User message")
        
        friendly_message = error.get_user_friendly_message()
        
        assert friendly_message == "User message"


class TestErrorBuilder:
    """Test error builder class."""

    def test_builder_minimal(self):
        """Test builder with minimal configuration."""
        error = ErrorBuilder("Test message").build()
        
        assert error.message == "Test message"
        assert error.category == ErrorCategory.UNKNOWN
        assert error.recoverable is False

    def test_builder_fluent_interface(self):
        """Test builder fluent interface."""
        error = (ErrorBuilder("Test message")
                .with_category(ErrorCategory.VALIDATION)
                .with_operation("test_op")
                .with_component("test_comp")
                .as_recoverable(True)
                .with_user_message("User message")
                .add_suggestion("Try this")
                .add_user_data("key", "value")
                .add_system_data("debug", "info")
                .build())
        
        assert error.message == "Test message"
        assert error.category == ErrorCategory.VALIDATION
        assert error.context.operation == "test_op"
        assert error.context.component == "test_comp"
        assert error.recoverable is True
        assert error.user_message == "User message"
        assert "Try this" in error.suggestions
        assert error.context.user_data["key"] == "value"
        assert error.context.system_data["debug"] == "info"

    def test_builder_with_cause(self):
        """Test builder with underlying cause."""
        cause = ValueError("Original error")
        error = ErrorBuilder("Test message").with_cause(cause).build()
        
        assert error.cause == cause

    def test_builder_multiple_suggestions(self):
        """Test builder with multiple suggestions."""
        error = (ErrorBuilder("Test message")
                .add_suggestion("First")
                .add_suggestion("Second")
                .add_suggestion("Third")
                .build())
        
        assert len(error.suggestions) == 3
        assert "First" in error.suggestions
        assert "Second" in error.suggestions
        assert "Third" in error.suggestions

    def test_builder_context_data(self):
        """Test builder with context data."""
        error = (ErrorBuilder("Test message")
                .add_user_data("user_key", "user_value")
                .add_system_data("system_key", "system_value")
                .build())
        
        assert error.context.user_data["user_key"] == "user_value"
        assert error.context.system_data["system_key"] == "system_value"


class TestErrorIntegration:
    """Integration tests for error handling components."""

    def test_error_with_traceback(self):
        """Test error creation with traceback from exception."""
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            error = StructuredError("Wrapped error", cause=e)
            assert error.cause == e
            assert error.traceback_str is not None

    def test_error_without_traceback(self):
        """Test error creation without traceback."""
        error = StructuredError("Simple error")
        assert error.traceback_str is None

    def test_complex_error_scenario(self):
        """Test complex error creation scenario."""
        # Simulate a realistic error scenario
        context = ErrorContext(operation="file_processing", component="image_loader")
        context.add_user_data("file_path", "/images/test.jpg")
        context.add_system_data("file_size", 1024)
        
        try:
            raise FileNotFoundError("File not found")
        except FileNotFoundError as e:
            error = StructuredError(
                message="Failed to load image file",
                category=ErrorCategory.FILE_NOT_FOUND,
                context=context,
                cause=e,
                recoverable=True,
                user_message="The image file could not be found",
                suggestions=[
                    "Check that the file path is correct",
                    "Verify the file exists",
                    "Ensure you have read permissions"
                ]
            )
        
        # Verify all aspects of the complex error
        assert error.message == "Failed to load image file"
        assert error.category == ErrorCategory.FILE_NOT_FOUND
        assert error.recoverable is True
        assert error.context.user_data["file_path"] == "/images/test.jpg"
        assert len(error.suggestions) == 3
        assert isinstance(error.cause, FileNotFoundError)
        
        # Test dictionary conversion
        error_dict = error.to_dict()
        assert error_dict["category"] == "FILE_NOT_FOUND"
        assert error_dict["recoverable"] is True
        
        # Test user-friendly message
        friendly_msg = error.get_user_friendly_message()
        assert "image file could not be found" in friendly_msg
        assert "Check that the file path is correct" in friendly_msg