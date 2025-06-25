"""
Tests for error reporting utilities.

Tests the ErrorReporter class and its ability to format and report
structured errors in both simple and verbose modes.
"""

import sys
from io import StringIO

import pytest

from goesvfi.utils.errors.base import ErrorCategory, ErrorContext, StructuredError
from goesvfi.utils.errors.reporter import ErrorReporter


class TestErrorReporter:
    """Test error reporter functionality."""

    def test_error_reporter_initialization_default(self):
        """Test error reporter initialization with defaults."""
        reporter = ErrorReporter()
        
        assert reporter.output == sys.stderr
        assert reporter.verbose is False

    def test_error_reporter_initialization_custom(self):
        """Test error reporter initialization with custom parameters."""
        custom_output = StringIO()
        reporter = ErrorReporter(output=custom_output, verbose=True)
        
        assert reporter.output == custom_output
        assert reporter.verbose is True

    def test_simple_error_reporting(self):
        """Test simple error reporting mode."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=False)
        
        error = StructuredError(
            message="Technical error message",
            user_message="User-friendly error message"
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        assert "Error: User-friendly error message" in output
        # Should not contain technical details in simple mode
        assert "Technical error message" not in output

    def test_simple_error_reporting_with_suggestions(self):
        """Test simple error reporting with suggestions."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=False)
        
        error = StructuredError(
            message="File not found",
            user_message="The requested file could not be found",
            suggestions=[
                "Check that the file path is correct",
                "Verify the file exists",
                "Ensure you have read permissions"
            ]
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        assert "Error: The requested file could not be found" in output
        assert "Suggestions:" in output
        assert "• Check that the file path is correct" in output
        assert "• Verify the file exists" in output
        assert "• Ensure you have read permissions" in output

    def test_simple_error_reporting_no_suggestions(self):
        """Test simple error reporting without suggestions."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=False)
        
        error = StructuredError(
            message="Simple error",
            user_message="Simple user message"
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        assert "Error: Simple user message" in output
        assert "Suggestions:" not in output

    def test_verbose_error_reporting(self):
        """Test verbose error reporting mode."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)
        
        context = ErrorContext(operation="file_read", component="file_loader")
        context.add_user_data("file_path", "/data/test.txt")
        context.add_user_data("operation_id", "read_123")
        
        error = StructuredError(
            message="Technical file not found error",
            category=ErrorCategory.FILE_NOT_FOUND,
            context=context,
            recoverable=True,
            user_message="User-friendly file not found message",
            suggestions=["Check file path", "Verify permissions"]
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        
        # Should contain all verbose information
        assert "Error in file_loader (FILE_NOT_FOUND):" in output
        assert "Message: Technical file not found error" in output
        assert "Operation: file_read" in output
        assert "Recoverable: True" in output
        assert "Context:" in output
        assert "file_path: /data/test.txt" in output
        assert "operation_id: read_123" in output
        assert "Suggestions:" in output
        assert "• Check file path" in output
        assert "• Verify permissions" in output

    def test_verbose_error_reporting_with_cause(self):
        """Test verbose error reporting with underlying cause."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)
        
        # Create original exception
        original_exception = FileNotFoundError("/data/missing.txt")
        
        error = StructuredError(
            message="Wrapper error",
            category=ErrorCategory.FILE_NOT_FOUND,
            context=ErrorContext("test_op", "test_comp"),
            cause=original_exception
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        assert "Caused by: /data/missing.txt" in output

    def test_verbose_error_reporting_no_context_data(self):
        """Test verbose error reporting without context data."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)
        
        error = StructuredError(
            message="Simple error",
            category=ErrorCategory.UNKNOWN,
            context=ErrorContext("operation", "component"),
            recoverable=False
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        
        assert "Error in component (UNKNOWN):" in output
        assert "Message: Simple error" in output
        assert "Operation: operation" in output
        assert "Recoverable: False" in output
        # Should not have Context section if no user data
        assert "Context:" not in output

    def test_verbose_error_reporting_no_suggestions(self):
        """Test verbose error reporting without suggestions."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)
        
        error = StructuredError(
            message="Error without suggestions",
            category=ErrorCategory.SYSTEM,
            context=ErrorContext("operation", "component")
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        
        assert "Error in component (SYSTEM):" in output
        assert "Message: Error without suggestions" in output
        # Should not have Suggestions section
        assert "Suggestions:" not in output

    def test_verbose_error_reporting_no_cause(self):
        """Test verbose error reporting without underlying cause."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)
        
        error = StructuredError(
            message="Error without cause",
            category=ErrorCategory.VALIDATION,
            context=ErrorContext("operation", "component")
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        
        assert "Error in component (VALIDATION):" in output
        assert "Message: Error without cause" in output
        # Should not have Caused by section
        assert "Caused by:" not in output

    def test_error_reporting_mode_selection(self):
        """Test that reporter selects correct mode based on verbose flag."""
        simple_stream = StringIO()
        verbose_stream = StringIO()
        
        simple_reporter = ErrorReporter(output=simple_stream, verbose=False)
        verbose_reporter = ErrorReporter(output=verbose_stream, verbose=True)
        
        context = ErrorContext("test_operation", "test_component")
        context.add_user_data("test_key", "test_value")
        
        error = StructuredError(
            message="Technical message",
            category=ErrorCategory.NETWORK,
            context=context,
            user_message="User message",
            suggestions=["Fix network"]
        )
        
        simple_reporter.report_error(error)
        verbose_reporter.report_error(error)
        
        simple_output = simple_stream.getvalue()
        verbose_output = verbose_stream.getvalue()
        
        # Simple output should be concise
        assert "Error: User message" in simple_output
        assert "test_component" not in simple_output
        assert "NETWORK" not in simple_output
        
        # Verbose output should have all details
        assert "Error in test_component (NETWORK):" in verbose_output
        assert "Message: Technical message" in verbose_output
        assert "Operation: test_operation" in verbose_output
        assert "test_key: test_value" in verbose_output


class TestErrorReporterIntegration:
    """Integration tests for error reporter with realistic scenarios."""

    def test_file_error_reporting_scenario(self):
        """Test error reporting for file operation scenarios."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)
        
        # Simulate file operation error
        context = ErrorContext(operation="config_load", component="config_manager")
        context.add_user_data("config_file", "/app/config/settings.json")
        context.add_user_data("expected_format", "JSON")
        context.add_system_data("file_size", 1024)
        context.add_system_data("permissions", "644")
        
        original_error = PermissionError("Permission denied")
        
        error = StructuredError(
            message="Failed to read configuration file",
            category=ErrorCategory.PERMISSION,
            context=context,
            cause=original_error,
            recoverable=True,
            user_message="Cannot access the configuration file",
            suggestions=[
                "Check file permissions",
                "Run with elevated privileges",
                "Verify file ownership"
            ]
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        
        # Verify comprehensive error reporting
        assert "Error in config_manager (PERMISSION):" in output
        assert "Message: Failed to read configuration file" in output
        assert "Operation: config_load" in output
        assert "Recoverable: True" in output
        assert "config_file: /app/config/settings.json" in output
        assert "expected_format: JSON" in output
        assert "Check file permissions" in output
        assert "Caused by: Permission denied" in output

    def test_network_error_reporting_scenario(self):
        """Test error reporting for network operation scenarios."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=False)  # Simple mode
        
        context = ErrorContext(operation="api_request", component="http_client")
        context.add_user_data("url", "https://api.example.com/data")
        context.add_user_data("method", "GET")
        context.add_user_data("timeout", 30)
        
        error = StructuredError(
            message="Connection timeout after 30 seconds",
            category=ErrorCategory.NETWORK,
            context=context,
            recoverable=True,
            user_message="Unable to connect to the server",
            suggestions=[
                "Check your internet connection",
                "Verify the server is running",
                "Try again later"
            ]
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        
        # Simple mode should be user-friendly
        assert "Error: Unable to connect to the server" in output
        assert "Suggestions:" in output
        assert "• Check your internet connection" in output
        assert "• Verify the server is running" in output
        assert "• Try again later" in output
        
        # Should not contain technical details in simple mode
        assert "http_client" not in output
        assert "api_request" not in output
        assert "NETWORK" not in output

    def test_processing_error_reporting_scenario(self):
        """Test error reporting for processing operation scenarios."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)
        
        context = ErrorContext(operation="image_resize", component="image_processor")
        context.add_user_data("input_file", "/images/large_photo.jpg")
        context.add_user_data("target_size", "1920x1080")
        context.add_user_data("format", "JPEG")
        context.add_system_data("memory_used", "512MB")
        context.add_system_data("processing_time", 15.7)
        context.add_system_data("temp_files_created", 3)
        
        error = StructuredError(
            message="Image processing failed due to insufficient memory",
            category=ErrorCategory.PROCESSING,
            context=context,
            recoverable=False,
            user_message="Unable to resize the image due to memory constraints",
            suggestions=[
                "Try with a smaller target size",
                "Close other applications to free memory",
                "Use a different image format"
            ]
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        
        # Verify all processing context is captured
        assert "Error in image_processor (PROCESSING):" in output
        assert "Operation: image_resize" in output
        assert "Recoverable: False" in output
        assert "input_file: /images/large_photo.jpg" in output
        assert "target_size: 1920x1080" in output
        assert "format: JPEG" in output
        assert "memory_used: 512MB" in output
        assert "processing_time: 15.7" in output
        assert "Try with a smaller target size" in output

    def test_multiple_error_reporting(self):
        """Test reporting multiple errors to same stream."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=False)
        
        error1 = StructuredError(
            message="First error",
            user_message="First user message",
            suggestions=["First suggestion"]
        )
        
        error2 = StructuredError(
            message="Second error",
            user_message="Second user message",
            suggestions=["Second suggestion"]
        )
        
        reporter.report_error(error1)
        reporter.report_error(error2)
        
        output = output_stream.getvalue()
        
        # Both errors should be in output
        assert "Error: First user message" in output
        assert "Error: Second user message" in output
        assert "• First suggestion" in output
        assert "• Second suggestion" in output

    def test_error_reporting_with_empty_data(self):
        """Test error reporting with minimal/empty data."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)
        
        # Minimal error with just message
        error = StructuredError("Minimal error")
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        
        # Should handle minimal data gracefully
        assert "Error in unknown (UNKNOWN):" in output
        assert "Message: Minimal error" in output
        assert "Operation: unknown" in output
        assert "Recoverable: False" in output

    def test_error_reporting_encoding_handling(self):
        """Test error reporting with special characters."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)
        
        context = ErrorContext("测试操作", "测试组件")
        context.add_user_data("文件路径", "/测试/文件.txt")
        
        error = StructuredError(
            message="Error with 特殊字符 and émojis 🚫",
            category=ErrorCategory.VALIDATION,
            context=context,
            user_message="用户友好的错误信息",
            suggestions=["建议一", "建议二"]
        )
        
        reporter.report_error(error)
        
        output = output_stream.getvalue()
        
        # Should handle Unicode characters properly
        assert "Error in 测试组件 (VALIDATION):" in output
        assert "Message: Error with 特殊字符 and émojis 🚫" in output
        assert "Operation: 测试操作" in output
        assert "文件路径: /测试/文件.txt" in output
        assert "• 建议一" in output
        assert "• 建议二" in output