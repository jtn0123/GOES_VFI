"""
Tests for error reporting utilities - Optimized Version.

Tests the ErrorReporter class and its ability to format and report
structured errors in both simple and verbose modes.
"""

from io import StringIO
import sys

import pytest

from goesvfi.utils.errors.base import ErrorCategory, ErrorContext, StructuredError
from goesvfi.utils.errors.reporter import ErrorReporter


class TestErrorReporter:
    """Test error reporter functionality - optimized with fixtures and parameterization."""

    @pytest.fixture()
    @staticmethod
    def output_stream() -> StringIO:
        """Create a reusable output stream.

        Returns:
            StringIO: Output stream for testing.
        """
        return StringIO()

    @pytest.fixture()
    @staticmethod
    def error_context() -> ErrorContext:
        """Create a reusable error context with test data.

        Returns:
            ErrorContext: Error context with test data.
        """
        context = ErrorContext(operation="test_operation", component="test_component")
        context.add_user_data("test_key", "test_value")
        context.add_user_data("file_path", "/test/path.txt")
        context.add_system_data("memory_used", "512MB")
        context.add_system_data("processing_time", 15.7)
        return context

    @pytest.fixture()
    def structured_error(self, error_context):
        """Create a reusable structured error."""
        return StructuredError(
            message="Technical error message",
            category=ErrorCategory.PROCESSING,
            context=error_context,
            recoverable=True,
            user_message="User-friendly error message",
            suggestions=["Check file path", "Verify permissions"],
            cause=ValueError("Original error"),
        )

    @pytest.mark.parametrize(
        "output,verbose,expected",
        [
            (None, None, (sys.stderr, False)),  # Default initialization
            (sys.stdout, True, (sys.stdout, True)),  # Custom output and verbose
            (sys.stderr, False, (sys.stderr, False)),  # Explicit stderr
        ],
    )
    def test_error_reporter_initialization(self, output, verbose, expected) -> None:
        """Test error reporter initialization with various parameters."""
        kwargs = {}
        if output is not None:
            kwargs["output"] = output
        if verbose is not None:
            kwargs["verbose"] = verbose

        reporter = ErrorReporter(**kwargs)

        assert reporter.output == expected[0]
        assert reporter.verbose == expected[1]

    @pytest.mark.parametrize(
        "has_suggestions,suggestions,expected_suggestions",
        [
            (True, ["Check file", "Verify path", "Try again"], 3),
            (True, ["Single suggestion"], 1),
            (False, [], 0),
            (False, None, 0),
        ],
    )
    def test_simple_error_reporting_variations(
        self, output_stream, has_suggestions, suggestions, expected_suggestions
    ) -> None:
        """Test simple error reporting with different suggestion configurations."""
        reporter = ErrorReporter(output=output_stream, verbose=False)

        error_kwargs = {
            "message": "Technical error",
            "user_message": "User-friendly error",
        }
        if has_suggestions and suggestions:
            error_kwargs["suggestions"] = suggestions

        error = StructuredError(**error_kwargs)
        reporter.report_error(error)

        output = output_stream.getvalue()
        assert "Error: User-friendly error" in output
        assert "Technical error" not in output  # Should not appear in simple mode

        if expected_suggestions > 0:
            assert "Suggestions:" in output
            for suggestion in suggestions:
                assert f"• {suggestion}" in output
        else:
            assert "Suggestions:" not in output

    @pytest.mark.parametrize(
        "context_data,cause,expected_sections",
        [
            # Full verbose output with all sections
            (
                {"file": "/data.txt", "size": 1024},
                ValueError("Cause"),
                ["Error in", "Message:", "Operation:", "Recoverable:", "Context:", "Suggestions:", "Caused by:"],
            ),
            # No context data
            ({}, None, ["Error in", "Message:", "Operation:", "Recoverable:"]),
            # Context but no cause
            ({"key": "value"}, None, ["Error in", "Message:", "Operation:", "Recoverable:", "Context:"]),
            # Cause but no context
            ({}, FileNotFoundError("Missing"), ["Error in", "Message:", "Operation:", "Caused by:"]),
        ],
    )
    def test_verbose_error_reporting_sections(self, output_stream, context_data, cause, expected_sections) -> None:
        """Test verbose error reporting with different section combinations."""
        reporter = ErrorReporter(output=output_stream, verbose=True)

        context = ErrorContext("operation", "component")
        for key, value in context_data.items():
            context.add_user_data(key, value)

        error = StructuredError(
            message="Test error",
            category=ErrorCategory.VALIDATION,
            context=context,
            recoverable=True,
            suggestions=["Fix it"] if "Suggestions:" in expected_sections else None,
            cause=cause,
        )

        reporter.report_error(error)
        output = output_stream.getvalue()

        for section in expected_sections:
            assert section in output

    def test_error_reporting_mode_selection(self, output_stream, structured_error) -> None:
        """Test that reporter selects correct mode based on verbose flag."""
        simple_stream = StringIO()
        verbose_stream = StringIO()

        simple_reporter = ErrorReporter(output=simple_stream, verbose=False)
        verbose_reporter = ErrorReporter(output=verbose_stream, verbose=True)

        # Report same error in both modes
        simple_reporter.report_error(structured_error)
        verbose_reporter.report_error(structured_error)

        simple_output = simple_stream.getvalue()
        verbose_output = verbose_stream.getvalue()

        # Simple output checks
        assert "Error: User-friendly error message" in simple_output
        assert "test_component" not in simple_output
        assert "PROCESSING" not in simple_output
        assert "Technical error message" not in simple_output

        # Verbose output checks
        assert "Error in test_component (PROCESSING):" in verbose_output
        assert "Message: Technical error message" in verbose_output
        assert "Operation: test_operation" in verbose_output
        assert "test_key: test_value" in verbose_output
        assert "Caused by: Original error" in verbose_output

    def test_multiple_error_reporting(self, output_stream) -> None:
        """Test reporting multiple errors to same stream."""
        reporter = ErrorReporter(output=output_stream, verbose=False)

        errors = [
            StructuredError(
                message=f"Error {i}",
                user_message=f"User message {i}",
                suggestions=[f"Suggestion {i}"],
            )
            for i in range(3)
        ]

        for error in errors:
            reporter.report_error(error)

        output = output_stream.getvalue()

        # All errors should be in output
        for i in range(3):
            assert f"Error: User message {i}" in output
            assert f"• Suggestion {i}" in output

    @pytest.mark.parametrize(
        "encoding_test",
        [
            ("测试错误", "用户消息", ["建议一", "建议二"], "中文字符"),
            ("Error with émojis 🚫", "Message with ñ", ["Café", "Résumé"], "特殊字符"),
            ("Plain ASCII", "Simple message", ["Basic suggestion"], "ASCII"),
        ],
    )
    def test_error_reporting_encoding_handling(self, output_stream, encoding_test) -> None:
        """Test error reporting with various character encodings."""
        message, user_message, suggestions, test_name = encoding_test

        reporter = ErrorReporter(output=output_stream, verbose=True)

        context = ErrorContext(f"op_{test_name}", f"comp_{test_name}")
        context.add_user_data("文件路径", f"/测试/{test_name}.txt")

        error = StructuredError(
            message=message,
            category=ErrorCategory.VALIDATION,
            context=context,
            user_message=user_message,
            suggestions=suggestions,
        )

        reporter.report_error(error)
        output = output_stream.getvalue()

        # Verify all special characters are handled properly
        assert message in output
        assert user_message in output
        for suggestion in suggestions:
            assert f"• {suggestion}" in output


class TestErrorReporterIntegration:
    """Integration tests for error reporter with realistic scenarios - optimized."""

    @pytest.fixture()
    def reporter_simple(self):
        """Create a simple mode reporter."""
        return ErrorReporter(output=StringIO(), verbose=False)

    @pytest.fixture()
    def reporter_verbose(self):
        """Create a verbose mode reporter."""
        return ErrorReporter(output=StringIO(), verbose=True)

    @pytest.mark.parametrize(
        "scenario",
        [
            {
                "name": "file_permission",
                "operation": "config_load",
                "component": "config_manager",
                "category": ErrorCategory.PERMISSION,
                "message": "Failed to read configuration file",
                "user_message": "Cannot access the configuration file",
                "user_data": {
                    "config_file": "/app/config/settings.json",
                    "expected_format": "JSON",
                },
                "system_data": {
                    "file_size": 1024,
                    "permissions": "644",
                },
                "cause": PermissionError("Permission denied"),
                "suggestions": [
                    "Check file permissions",
                    "Run with elevated privileges",
                    "Verify file ownership",
                ],
            },
            {
                "name": "network_timeout",
                "operation": "api_request",
                "component": "http_client",
                "category": ErrorCategory.NETWORK,
                "message": "Connection timeout after 30 seconds",
                "user_message": "Unable to connect to the server",
                "user_data": {
                    "url": "https://api.example.com/data",
                    "method": "GET",
                    "timeout": 30,
                },
                "system_data": {},
                "cause": None,
                "suggestions": [
                    "Check your internet connection",
                    "Verify the server is running",
                    "Try again later",
                ],
            },
            {
                "name": "processing_memory",
                "operation": "image_resize",
                "component": "image_processor",
                "category": ErrorCategory.PROCESSING,
                "message": "Image processing failed due to insufficient memory",
                "user_message": "Unable to resize the image due to memory constraints",
                "user_data": {
                    "input_file": "/images/large_photo.jpg",
                    "target_size": "1920x1080",
                    "format": "JPEG",
                },
                "system_data": {
                    "memory_used": "512MB",
                    "processing_time": 15.7,
                    "temp_files_created": 3,
                },
                "cause": None,
                "suggestions": [
                    "Try with a smaller target size",
                    "Close other applications to free memory",
                    "Use a different image format",
                ],
            },
        ],
    )
    def test_realistic_error_scenarios(self, scenario) -> None:
        """Test realistic error reporting scenarios with parameterization."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)

        # Build context
        context = ErrorContext(scenario["operation"], scenario["component"])
        for key, value in scenario["user_data"].items():
            context.add_user_data(key, value)
        for key, value in scenario["system_data"].items():
            context.add_system_data(key, value)

        # Create error
        error = StructuredError(
            message=scenario["message"],
            category=scenario["category"],
            context=context,
            cause=scenario["cause"],
            recoverable=scenario["category"] != ErrorCategory.PROCESSING,
            user_message=scenario["user_message"],
            suggestions=scenario["suggestions"],
        )

        reporter.report_error(error)
        output = output_stream.getvalue()

        # Verify output contains expected elements
        assert f"Error in {scenario['component']}" in output
        assert scenario["message"] in output
        assert f"Operation: {scenario['operation']}" in output

        # Check context data
        for key, value in scenario["user_data"].items():
            assert f"{key}: {value}" in output

        # Check suggestions
        for suggestion in scenario["suggestions"]:
            assert suggestion in output

        # Check cause if present
        if scenario["cause"]:
            assert "Caused by:" in output

    def test_error_reporting_with_minimal_data(self) -> None:
        """Test error reporting with minimal/empty data."""
        output_stream = StringIO()
        reporter = ErrorReporter(output=output_stream, verbose=True)

        # Create absolutely minimal error
        error = StructuredError("Minimal error")
        reporter.report_error(error)

        output = output_stream.getvalue()

        # Should handle minimal data gracefully
        assert "Error in unknown (UNKNOWN):" in output
        assert "Message: Minimal error" in output
        assert "Operation: unknown" in output
        assert "Recoverable: False" in output

        # Should not have optional sections
        assert "Context:" not in output
        assert "Suggestions:" not in output
        assert "Caused by:" not in output
