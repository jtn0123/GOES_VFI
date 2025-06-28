"""
Tests for core application exceptions - Optimized Version.

Tests the core exception hierarchy and their usage patterns.
"""

from typing import Never

import pytest

from goesvfi.exceptions import (
    ConfigurationError,
    ExternalToolError,
    GoesVfiError,
    GoesvfiError,
    GuiError,
    PipelineError,
)


class TestGoesVfiError:
    """Test base application error - optimized with parameterization."""

    @pytest.mark.parametrize("error_class,message", [
        (GoesVfiError, "Test error message"),
        (GoesvfiError, "Test with alias"),
        (GoesVfiError, ""),  # Empty message
        (GoesvfiError, "Very long " * 100),  # Long message
    ])
    def test_goesvfi_error_creation(self, error_class, message) -> None:
        """Test creating base GOES VFI error with various messages."""
        error = error_class(message)

        assert str(error) == message
        assert isinstance(error, Exception)
        assert isinstance(error, GoesVfiError)

    def test_goesvfi_error_alias(self) -> None:
        """Test that GoesvfiError alias works correctly."""
        # Both should be the same class
        assert GoesvfiError is GoesVfiError

        error1 = GoesVfiError("Test 1")
        error2 = GoesvfiError("Test 2")

        assert type(error1) is type(error2)
        assert isinstance(error1, GoesvfiError)
        assert isinstance(error2, GoesVfiError)


class TestExceptionHierarchy:
    """Test exception hierarchy and relationships - optimized."""

    @pytest.fixture()
    def all_exceptions(self):
        """Create instances of all exception types."""
        return {
            "base": GoesVfiError("Base error"),
            "pipeline": PipelineError("Pipeline error"),
            "config": ConfigurationError("Config error"),
            "gui": GuiError("GUI error"),
            "tool": ExternalToolError("tool", "Tool error"),
        }

    @pytest.mark.parametrize("error_type,parent_types", [
        ("pipeline", [PipelineError, GoesVfiError, Exception]),
        ("config", [ConfigurationError, GoesVfiError, Exception]),
        ("gui", [GuiError, GoesVfiError, Exception]),
        ("tool", [ExternalToolError, PipelineError, GoesVfiError, Exception]),
        ("base", [GoesVfiError, Exception]),
    ])
    def test_exception_inheritance(self, all_exceptions, error_type, parent_types) -> None:
        """Test exception inheritance chains."""
        error = all_exceptions[error_type]

        for parent_type in parent_types:
            assert isinstance(error, parent_type)

    @pytest.mark.parametrize("exception_class,message,expected_str", [
        (PipelineError, "Pipeline processing failed", "Pipeline processing failed"),
        (ConfigurationError, "Invalid configuration setting", "Invalid configuration setting"),
        (GuiError, "Widget initialization failed", "Widget initialization failed"),
        (PipelineError, "", ""),
    ])
    def test_exception_string_representation(self, exception_class, message, expected_str) -> None:
        """Test exception string representations."""
        error = exception_class(message)
        assert str(error) == expected_str


class TestExternalToolError:
    """Test external tool error functionality - optimized."""

    @pytest.mark.parametrize("tool_name,message,stderr,expected_str", [
        ("ffmpeg", "Encoding failed", None, "Error executing ffmpeg: Encoding failed"),
        ("rife", "Interpolation failed", "GPU error", "Error executing rife: Interpolation failed"),
        ("sanchez", "Processing failed", "", "Error executing sanchez: Processing failed"),
        ("tool", "Failed", "Multi\nline\nerror", "Error executing tool: Failed"),
    ])
    def test_external_tool_error_creation(self, tool_name, message, stderr, expected_str) -> None:
        """Test creating external tool errors with various parameters."""
        error = ExternalToolError(tool_name, message, stderr=stderr)

        assert error.tool_name == tool_name
        assert error.stderr == stderr
        assert expected_str in str(error)
        assert isinstance(error, PipelineError)
        assert isinstance(error, GoesVfiError)

    def test_external_tool_error_complex_stderr(self) -> None:
        """Test external tool error with complex stderr output."""
        stderr_output = """
        ERROR: Invalid input format
        File: /path/to/input.mp4
        Line 42: Unsupported codec
        Stack trace:
          at process_video()
          at main()
        """

        error = ExternalToolError("ffmpeg", "Processing failed", stderr=stderr_output)

        assert error.stderr == stderr_output
        assert "Invalid input format" in error.stderr
        assert "/path/to/input.mp4" in error.stderr
        assert "Line 42" in error.stderr


class TestExceptionUsagePatterns:
    """Test common exception usage patterns - optimized."""

    @pytest.mark.parametrize("exception_info", [
        {
            "class": ConfigurationError,
            "message": "Missing required setting 'database_url' in section 'connection'",
            "expected_content": ["database_url", "connection"],
        },
        {
            "class": PipelineError,
            "message": "Frame interpolation failed at step 3 of 5",
            "expected_content": ["interpolation", "step 3 of 5"],
        },
        {
            "class": GuiError,
            "message": "Failed to update progress bar widget",
            "expected_content": ["progress bar", "widget"],
        },
    ])
    def test_exception_message_content(self, exception_info) -> None:
        """Test that exception messages contain expected information."""
        error = exception_info["class"](exception_info["message"])
        error_str = str(error)

        for content in exception_info["expected_content"]:
            assert content in error_str

    @pytest.mark.parametrize("raise_func,catch_types", [
        (lambda: PipelineError("Pipeline failed"), [PipelineError, GoesVfiError, Exception]),
        (lambda: ConfigurationError("Config failed"), [ConfigurationError, GoesVfiError, Exception]),
        (lambda: ExternalToolError("ffmpeg", "Tool failed"), [ExternalToolError, PipelineError, GoesVfiError, Exception]),
        (lambda: GuiError("GUI failed"), [GuiError, GoesVfiError, Exception]),
    ])
    def test_exception_catching_hierarchy(self, raise_func, catch_types) -> None:
        """Test exception catching at different hierarchy levels."""
        for catch_type in catch_types:
            with pytest.raises(catch_type):
                raise_func()

    def test_exception_chaining(self) -> None:
        """Test exception chaining and context preservation."""
        original_error = ValueError("Invalid input format")

        def raise_chained() -> None:
            try:
                raise original_error
            except ValueError as e:
                msg = "Processing failed"
                raise PipelineError(msg) from e

        with pytest.raises(PipelineError) as exc_info:
            raise_chained()

        # Check that original exception is preserved
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert "Invalid input format" in str(exc_info.value.__cause__)

    def test_exception_type_filtering(self) -> None:
        """Test filtering exceptions by type in handlers."""
        exceptions = [
            GoesVfiError("Base error"),
            PipelineError("Pipeline error"),
            ConfigurationError("Config error"),
            GuiError("GUI error"),
            ExternalToolError("tool", "Tool error"),
        ]

        # Filter by type
        type_counts = {
            GoesVfiError: 0,
            PipelineError: 0,
            ExternalToolError: 0,
        }

        for error in exceptions:
            for exc_type in type_counts:
                if isinstance(error, exc_type):
                    type_counts[exc_type] += 1

        assert type_counts[GoesVfiError] == 5  # All are GoesVfiError
        assert type_counts[PipelineError] == 2  # PipelineError and ExternalToolError
        assert type_counts[ExternalToolError] == 1  # Only ExternalToolError


class TestExceptionIntegration:
    """Integration tests for exception usage - optimized."""

    @pytest.mark.parametrize("scenario", [
        {
            "name": "config_loading",
            "function": lambda: ConfigurationError("Missing database configuration in settings.json"),
            "expected_type": ConfigurationError,
            "expected_content": ["database", "settings.json"],
        },
        {
            "name": "pipeline_processing",
            "function": lambda: PipelineError("Failed to process frame 42 of 100"),
            "expected_type": PipelineError,
            "expected_content": ["frame 42", "100"],
        },
        {
            "name": "external_tool",
            "function": lambda: ExternalToolError(
                "ffmpeg",
                "Failed to encode video",
                stderr="ffmpeg: error while loading shared libraries: libx264.so"
            ),
            "expected_type": ExternalToolError,
            "expected_content": ["ffmpeg", "encode video"],
        },
        {
            "name": "gui_operation",
            "function": lambda: GuiError("Failed to update progress dialog: widget has been destroyed"),
            "expected_type": GuiError,
            "expected_content": ["progress dialog", "widget", "destroyed"],
        },
    ])
    def test_realistic_error_scenarios(self, scenario) -> None:
        """Test realistic error usage scenarios."""
        error = scenario["function"]()

        # Verify type
        assert isinstance(error, scenario["expected_type"])
        assert isinstance(error, GoesVfiError)

        # Verify content
        error_str = str(error)
        for content in scenario["expected_content"]:
            assert content in error_str

        # Special handling for ExternalToolError
        if isinstance(error, ExternalToolError):
            assert error.tool_name is not None
            if error.stderr:
                assert "libx264.so" in error.stderr

    def test_exception_context_managers(self) -> None:
        """Test using exceptions with context managers."""
        class MockResource:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is ConfigurationError:
                    # Handle configuration errors specially
                    return False
                return False

            def process(self) -> Never:
                msg = "Resource configuration invalid"
                raise ConfigurationError(msg)

        with pytest.raises(ConfigurationError), MockResource() as resource:
            resource.process()

    def test_exception_aggregation(self) -> None:
        """Test aggregating multiple exceptions."""
        errors: list[GoesVfiError] = []

        # Simulate collecting errors from multiple operations
        operations = [
            ("config", lambda: ConfigurationError("Config error")),
            ("pipeline", lambda: PipelineError("Pipeline error")),
            ("tool", lambda: ExternalToolError("ffmpeg", "Tool error")),
        ]

        for _op_name, op_func in operations:
            try:
                raise op_func()
            except GoesVfiError as e:
                errors.append(e)

        # Verify all errors were collected
        assert len(errors) == 3
        assert isinstance(errors[0], ConfigurationError)
        assert isinstance(errors[1], PipelineError)
        assert isinstance(errors[2], ExternalToolError)
