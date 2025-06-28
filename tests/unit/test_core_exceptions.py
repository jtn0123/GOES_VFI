"""
Tests for core application exceptions.

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
    """Test base application error."""

    def test_goesvfi_error_creation(self) -> None:
        """Test creating base GOES VFI error."""
        error = GoesVfiError("Test error message")

        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_goesvfi_error_inheritance(self) -> None:
        """Test GOES VFI error inheritance."""
        error = GoesVfiError("Test error")

        assert isinstance(error, Exception)
        assert isinstance(error, GoesVfiError)

    def test_goesvfi_error_alias(self) -> None:
        """Test that GoesvfiError alias works."""
        # Both should be the same class
        assert GoesvfiError is GoesVfiError

        error1 = GoesVfiError("Test 1")
        error2 = GoesvfiError("Test 2")

        assert type(error1) is type(error2)
        assert isinstance(error1, GoesvfiError)
        assert isinstance(error2, GoesVfiError)


class TestPipelineError:
    """Test pipeline error functionality."""

    def test_pipeline_error_creation(self) -> None:
        """Test creating pipeline error."""
        error = PipelineError("Pipeline processing failed")

        assert str(error) == "Pipeline processing failed"
        assert isinstance(error, PipelineError)
        assert isinstance(error, GoesVfiError)
        assert isinstance(error, Exception)

    def test_pipeline_error_inheritance(self) -> None:
        """Test pipeline error inheritance chain."""
        error = PipelineError("Test pipeline error")

        # Should inherit from GoesVfiError
        assert isinstance(error, GoesVfiError)
        assert isinstance(error, Exception)

    def test_pipeline_error_empty_message(self) -> None:
        """Test pipeline error with empty message."""
        error = PipelineError("")
        assert str(error) == ""


class TestConfigurationError:
    """Test configuration error functionality."""

    def test_configuration_error_creation(self) -> None:
        """Test creating configuration error."""
        error = ConfigurationError("Invalid configuration setting")

        assert str(error) == "Invalid configuration setting"
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, GoesVfiError)

    def test_configuration_error_inheritance(self) -> None:
        """Test configuration error inheritance."""
        error = ConfigurationError("Config error")

        assert isinstance(error, GoesVfiError)
        assert isinstance(error, Exception)

    def test_configuration_error_with_details(self) -> None:
        """Test configuration error with detailed message."""
        error = ConfigurationError("Missing required setting 'database_url' in section 'connection'")

        assert "database_url" in str(error)
        assert "connection" in str(error)


class TestGuiError:
    """Test GUI error functionality."""

    def test_gui_error_creation(self) -> None:
        """Test creating GUI error."""
        error = GuiError("Widget initialization failed")

        assert str(error) == "Widget initialization failed"
        assert isinstance(error, GuiError)
        assert isinstance(error, GoesVfiError)

    def test_gui_error_inheritance(self) -> None:
        """Test GUI error inheritance."""
        error = GuiError("GUI error")

        assert isinstance(error, GoesVfiError)
        assert isinstance(error, Exception)

    def test_gui_error_widget_related(self) -> None:
        """Test GUI error for widget-related issues."""
        error = GuiError("Failed to update progress bar widget")

        assert "progress bar" in str(error)
        assert "widget" in str(error)


class TestExternalToolError:
    """Test external tool error functionality."""

    def test_external_tool_error_creation_minimal(self) -> None:
        """Test creating external tool error with minimal parameters."""
        error = ExternalToolError("ffmpeg", "Encoding failed")

        assert "Error executing ffmpeg: Encoding failed" in str(error)
        assert error.tool_name == "ffmpeg"
        assert error.stderr is None
        assert isinstance(error, ExternalToolError)
        assert isinstance(error, PipelineError)
        assert isinstance(error, GoesVfiError)

    def test_external_tool_error_creation_with_stderr(self) -> None:
        """Test creating external tool error with stderr output."""
        stderr_output = "Error: Invalid codec parameters"
        error = ExternalToolError("ffmpeg", "Encoding failed", stderr=stderr_output)

        assert error.tool_name == "ffmpeg"
        assert error.stderr == stderr_output
        assert "Error executing ffmpeg: Encoding failed" in str(error)

    def test_external_tool_error_inheritance(self) -> None:
        """Test external tool error inheritance chain."""
        error = ExternalToolError("rife", "Interpolation failed")

        # Should inherit from PipelineError -> GoesVfiError -> Exception
        assert isinstance(error, PipelineError)
        assert isinstance(error, GoesVfiError)
        assert isinstance(error, Exception)

    def test_external_tool_error_different_tools(self) -> None:
        """Test external tool error with different tools."""
        ffmpeg_error = ExternalToolError("ffmpeg", "Video encoding failed")
        rife_error = ExternalToolError("rife", "Frame interpolation failed")
        sanchez_error = ExternalToolError("sanchez", "Image processing failed")

        assert ffmpeg_error.tool_name == "ffmpeg"
        assert rife_error.tool_name == "rife"
        assert sanchez_error.tool_name == "sanchez"

        assert "ffmpeg" in str(ffmpeg_error)
        assert "rife" in str(rife_error)
        assert "sanchez" in str(sanchez_error)

    def test_external_tool_error_with_complex_stderr(self) -> None:
        """Test external tool error with complex stderr output."""
        stderr_output = """
        ERROR: Invalid input format
        File: /path/to/input.mp4
        Line 42: Unsupported codec
        """

        error = ExternalToolError("ffmpeg", "Processing failed", stderr=stderr_output)

        assert error.stderr == stderr_output
        assert "Invalid input format" in error.stderr
        assert "/path/to/input.mp4" in error.stderr

    def test_external_tool_error_empty_stderr(self) -> None:
        """Test external tool error with empty stderr."""
        error = ExternalToolError("tool", "Failed", stderr="")

        assert error.stderr == ""

    def test_external_tool_error_none_stderr(self) -> None:
        """Test external tool error with None stderr."""
        error = ExternalToolError("tool", "Failed", stderr=None)

        assert error.stderr is None


class TestExceptionHierarchy:
    """Test exception hierarchy and relationships."""

    def test_exception_hierarchy_structure(self) -> None:
        """Test that exception hierarchy is properly structured."""
        # Create instances of all exception types
        base_error = GoesVfiError("Base error")
        pipeline_error = PipelineError("Pipeline error")
        config_error = ConfigurationError("Config error")
        gui_error = GuiError("GUI error")
        tool_error = ExternalToolError("tool", "Tool error")

        # Test inheritance relationships
        assert isinstance(pipeline_error, GoesVfiError)
        assert isinstance(config_error, GoesVfiError)
        assert isinstance(gui_error, GoesVfiError)
        assert isinstance(tool_error, PipelineError)
        assert isinstance(tool_error, GoesVfiError)

        # All should be exceptions
        exceptions = [base_error, pipeline_error, config_error, gui_error, tool_error]
        for exc in exceptions:
            assert isinstance(exc, Exception)

    def test_exception_catching_patterns(self) -> None:
        """Test different exception catching patterns."""

        def raise_pipeline_error() -> Never:
            msg = "Pipeline failed"
            raise PipelineError(msg)

        def raise_config_error() -> Never:
            msg = "Config failed"
            raise ConfigurationError(msg)

        def raise_tool_error() -> Never:
            msg = "ffmpeg"
            raise ExternalToolError(msg, "Tool failed")

        # Catch specific exception types
        with pytest.raises(PipelineError):
            raise_pipeline_error()

        with pytest.raises(ConfigurationError):
            raise_config_error()

        with pytest.raises(ExternalToolError):
            raise_tool_error()

        # Catch base exception type
        with pytest.raises(GoesVfiError):
            raise_pipeline_error()

        with pytest.raises(GoesVfiError):
            raise_config_error()

        with pytest.raises(GoesVfiError):
            raise_tool_error()

        # ExternalToolError should also be catchable as PipelineError
        with pytest.raises(PipelineError):
            raise_tool_error()

    def test_exception_type_checking(self) -> None:
        """Test exception type checking in exception handlers."""
        errors = [
            GoesVfiError("Base error"),
            PipelineError("Pipeline error"),
            ConfigurationError("Config error"),
            GuiError("GUI error"),
            ExternalToolError("tool", "Tool error"),
        ]

        goesvfi_errors = []
        pipeline_errors = []
        tool_errors = []

        for error in errors:
            if isinstance(error, GoesVfiError):
                goesvfi_errors.append(error)
            if isinstance(error, PipelineError):
                pipeline_errors.append(error)
            if isinstance(error, ExternalToolError):
                tool_errors.append(error)

        # All errors should be GoesVfiError
        assert len(goesvfi_errors) == 5

        # Only PipelineError and ExternalToolError should be pipeline errors
        assert len(pipeline_errors) == 2

        # Only ExternalToolError should be tool errors
        assert len(tool_errors) == 1
        assert isinstance(tool_errors[0], ExternalToolError)


class TestExceptionIntegration:
    """Integration tests for exception usage."""

    def test_realistic_error_scenarios(self) -> None:
        """Test realistic error usage scenarios."""

        def simulate_config_loading() -> Never:
            """Simulate configuration loading that might fail."""
            msg = "Missing database configuration in settings.json"
            raise ConfigurationError(msg)

        def simulate_pipeline_processing() -> Never:
            """Simulate pipeline processing that might fail."""
            msg = "Failed to process frame 42 of 100"
            raise PipelineError(msg)

        def simulate_external_tool_execution() -> Never:
            """Simulate external tool execution that might fail."""
            stderr = "ffmpeg: error while loading shared libraries: libx264.so"
            msg = "ffmpeg"
            raise ExternalToolError(msg, "Failed to encode video", stderr=stderr)

        def simulate_gui_operation() -> Never:
            """Simulate GUI operation that might fail."""
            msg = "Failed to update progress dialog: widget has been destroyed"
            raise GuiError(msg)

        # Test that we can catch and handle different error types appropriately
        scenarios = [
            (simulate_config_loading, ConfigurationError),
            (simulate_pipeline_processing, PipelineError),
            (simulate_external_tool_execution, ExternalToolError),
            (simulate_gui_operation, GuiError),
        ]

        for scenario_func, expected_exception_type in scenarios:
            with pytest.raises(expected_exception_type):
                scenario_func()

            # Also test that they can be caught as base type
            with pytest.raises(GoesVfiError):
                scenario_func()

    def test_exception_chaining(self) -> None:
        """Test exception chaining and context preservation."""

        def low_level_function() -> Never:
            msg = "Invalid input format"
            raise ValueError(msg)

        def high_level_function() -> None:
            try:
                low_level_function()
            except ValueError as e:
                msg = "Processing failed"
                raise PipelineError(msg) from e

        with pytest.raises(PipelineError) as exc_info:
            high_level_function()

        # Check that original exception is preserved
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert "Invalid input format" in str(exc_info.value.__cause__)

    def test_exception_message_formatting(self) -> None:
        """Test that exception messages are properly formatted."""

        # Test that messages contain relevant information
        config_error = ConfigurationError("Database URL not found in config section 'database'")
        assert "Database URL" in str(config_error)
        assert "database" in str(config_error)

        pipeline_error = PipelineError("Frame interpolation failed at step 3 of 5")
        assert "interpolation" in str(pipeline_error)
        assert "step 3 of 5" in str(pipeline_error)

        tool_error = ExternalToolError("ffmpeg", "Codec not supported", stderr="libx264 not found")
        error_str = str(tool_error)
        assert "ffmpeg" in error_str
        assert "Codec not supported" in error_str
        # stderr is not included in the main error message, but stored separately
        assert tool_error.stderr == "libx264 not found"
