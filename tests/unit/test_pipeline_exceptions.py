"""
Tests for pipeline-specific exceptions.

Tests the pipeline exception hierarchy and their specific use cases.
"""

import pytest

from goesvfi.pipeline.exceptions import (
    ConfigurationError,
    FFmpegError,
    InputError,
    OutputError,
    PipelineError,
    ProcessingError,
    ResourceError,
    RIFEError,
    SanchezError,
)


class TestPipelineError:
    """Test base pipeline error."""

    def test_pipeline_error_creation(self):
        """Test creating pipeline error."""
        error = PipelineError("Pipeline processing failed")

        assert str(error) == "Pipeline processing failed"
        assert isinstance(error, PipelineError)
        assert isinstance(error, Exception)

    def test_pipeline_error_inheritance(self):
        """Test pipeline error inheritance."""
        error = PipelineError("Test error")

        assert isinstance(error, Exception)


class TestProcessingError:
    """Test processing error functionality."""

    def test_processing_error_creation(self):
        """Test creating processing error."""
        error = ProcessingError("Video processing failed")

        assert str(error) == "Video processing failed"
        assert isinstance(error, ProcessingError)
        assert isinstance(error, PipelineError)

    def test_processing_error_inheritance(self):
        """Test processing error inheritance."""
        error = ProcessingError("Processing failed")

        assert isinstance(error, PipelineError)
        assert isinstance(error, Exception)


class TestFFmpegError:
    """Test FFmpeg-specific error functionality."""

    def test_ffmpeg_error_creation_minimal(self):
        """Test creating FFmpeg error with minimal parameters."""
        error = FFmpegError("Encoding failed")

        assert str(error) == "Encoding failed"
        assert error.command == ""
        assert error.stderr == ""
        assert isinstance(error, FFmpegError)
        assert isinstance(error, ProcessingError)

    def test_ffmpeg_error_creation_with_command(self):
        """Test creating FFmpeg error with command information."""
        command = "ffmpeg -i input.mp4 -c:v libx264 output.mp4"
        error = FFmpegError("Encoding failed", command=command)

        assert str(error) == "Encoding failed"
        assert error.command == command
        assert error.stderr == ""

    def test_ffmpeg_error_creation_with_stderr(self):
        """Test creating FFmpeg error with stderr output."""
        stderr_output = "Error: Unknown encoder 'libx265'"
        error = FFmpegError("Encoding failed", stderr=stderr_output)

        assert str(error) == "Encoding failed"
        assert error.command == ""
        assert error.stderr == stderr_output

    def test_ffmpeg_error_creation_full(self):
        """Test creating FFmpeg error with all parameters."""
        command = "ffmpeg -i input.mp4 -c:v libx264 output.mp4"
        stderr_output = "Error: Input file not found"
        error = FFmpegError("Encoding failed", command=command, stderr=stderr_output)

        assert str(error) == "Encoding failed"
        assert error.command == command
        assert error.stderr == stderr_output

    def test_ffmpeg_error_inheritance(self):
        """Test FFmpeg error inheritance chain."""
        error = FFmpegError("FFmpeg failed")

        assert isinstance(error, ProcessingError)
        assert isinstance(error, PipelineError)
        assert isinstance(error, Exception)


class TestRIFEError:
    """Test RIFE-specific error functionality."""

    def test_rife_error_creation(self):
        """Test creating RIFE error."""
        error = RIFEError("Frame interpolation failed")

        assert str(error) == "Frame interpolation failed"
        assert isinstance(error, RIFEError)
        assert isinstance(error, ProcessingError)

    def test_rife_error_inheritance(self):
        """Test RIFE error inheritance."""
        error = RIFEError("RIFE processing failed")

        assert isinstance(error, ProcessingError)
        assert isinstance(error, PipelineError)

    def test_rife_error_specific_scenarios(self):
        """Test RIFE error for specific scenarios."""
        scenarios = [
            "RIFE model not found",
            "Insufficient memory for RIFE processing",
            "RIFE executable not found",
            "Input images have incompatible dimensions",
        ]

        for scenario in scenarios:
            error = RIFEError(scenario)
            assert scenario in str(error)


class TestSanchezError:
    """Test Sanchez-specific error functionality."""

    def test_sanchez_error_creation(self):
        """Test creating Sanchez error."""
        error = SanchezError("Image processing failed")

        assert str(error) == "Image processing failed"
        assert isinstance(error, SanchezError)
        assert isinstance(error, ProcessingError)

    def test_sanchez_error_inheritance(self):
        """Test Sanchez error inheritance."""
        error = SanchezError("Sanchez processing failed")

        assert isinstance(error, ProcessingError)
        assert isinstance(error, PipelineError)

    def test_sanchez_error_specific_scenarios(self):
        """Test Sanchez error for specific scenarios."""
        scenarios = [
            "Sanchez executable not found",
            "Invalid satellite data format",
            "Unsupported image resolution",
            "Failed to apply false color enhancement",
        ]

        for scenario in scenarios:
            error = SanchezError(scenario)
            assert scenario in str(error)


class TestInputError:
    """Test input validation error functionality."""

    def test_input_error_creation(self):
        """Test creating input error."""
        error = InputError("Invalid input file format")

        assert str(error) == "Invalid input file format"
        assert isinstance(error, InputError)
        assert isinstance(error, PipelineError)

    def test_input_error_inheritance(self):
        """Test input error inheritance."""
        error = InputError("Input validation failed")

        assert isinstance(error, PipelineError)
        assert isinstance(error, Exception)

    def test_input_error_validation_scenarios(self):
        """Test input error for various validation scenarios."""
        scenarios = [
            "No PNG files found in input directory",
            "Image dimensions are too small",
            "Unsupported file format",
            "Input path does not exist",
        ]

        for scenario in scenarios:
            error = InputError(scenario)
            assert scenario in str(error)


class TestOutputError:
    """Test output operation error functionality."""

    def test_output_error_creation(self):
        """Test creating output error."""
        error = OutputError("Failed to write output file")

        assert str(error) == "Failed to write output file"
        assert isinstance(error, OutputError)
        assert isinstance(error, PipelineError)

    def test_output_error_inheritance(self):
        """Test output error inheritance."""
        error = OutputError("Output operation failed")

        assert isinstance(error, PipelineError)
        assert isinstance(error, Exception)

    def test_output_error_scenarios(self):
        """Test output error for various scenarios."""
        scenarios = [
            "Insufficient disk space",
            "Permission denied writing to output directory",
            "Output file already exists and cannot be overwritten",
            "Invalid output path",
        ]

        for scenario in scenarios:
            error = OutputError(scenario)
            assert scenario in str(error)


class TestResourceError:
    """Test resource constraint error functionality."""

    def test_resource_error_creation_minimal(self):
        """Test creating resource error with minimal parameters."""
        error = ResourceError("Insufficient resources")

        assert str(error) == "Insufficient resources"
        assert error.resource_type == ""
        assert isinstance(error, ResourceError)
        assert isinstance(error, PipelineError)

    def test_resource_error_creation_with_type(self):
        """Test creating resource error with resource type."""
        error = ResourceError("Insufficient memory", resource_type="memory")

        assert str(error) == "Insufficient memory"
        assert error.resource_type == "memory"

    def test_resource_error_inheritance(self):
        """Test resource error inheritance."""
        error = ResourceError("Resource constraint")

        assert isinstance(error, PipelineError)
        assert isinstance(error, Exception)

    def test_resource_error_different_types(self):
        """Test resource error for different resource types."""
        resource_scenarios = [
            ("Insufficient memory", "memory"),
            ("Disk space full", "disk"),
            ("CPU overloaded", "cpu"),
            ("Too many open files", "file_handles"),
            ("Network bandwidth exceeded", "network"),
        ]

        for message, resource_type in resource_scenarios:
            error = ResourceError(message, resource_type=resource_type)
            assert message in str(error)
            assert error.resource_type == resource_type


class TestConfigurationError:
    """Test pipeline configuration error functionality."""

    def test_configuration_error_creation(self):
        """Test creating configuration error."""
        error = ConfigurationError("Invalid pipeline configuration")

        assert str(error) == "Invalid pipeline configuration"
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, PipelineError)

    def test_configuration_error_inheritance(self):
        """Test configuration error inheritance."""
        error = ConfigurationError("Config error")

        assert isinstance(error, PipelineError)
        assert isinstance(error, Exception)

    def test_configuration_error_scenarios(self):
        """Test configuration error for various scenarios."""
        scenarios = [
            "Missing required configuration parameter 'fps'",
            "Invalid encoder settings",
            "Conflicting pipeline options",
            "Unsupported processing mode",
        ]

        for scenario in scenarios:
            error = ConfigurationError(scenario)
            assert scenario in str(error)


class TestPipelineExceptionHierarchy:
    """Test pipeline exception hierarchy and relationships."""

    def test_exception_hierarchy_structure(self):
        """Test that pipeline exception hierarchy is properly structured."""
        # Create instances of all exception types
        pipeline_error = PipelineError("Base pipeline error")
        processing_error = ProcessingError("Processing error")
        ffmpeg_error = FFmpegError("FFmpeg error")
        rife_error = RIFEError("RIFE error")
        sanchez_error = SanchezError("Sanchez error")
        input_error = InputError("Input error")
        output_error = OutputError("Output error")
        resource_error = ResourceError("Resource error")
        config_error = ConfigurationError("Config error")

        # Test inheritance relationships
        processing_exceptions = [
            processing_error,
            ffmpeg_error,
            rife_error,
            sanchez_error,
        ]
        for exc in processing_exceptions:
            assert isinstance(exc, ProcessingError)
            assert isinstance(exc, PipelineError)

        # Test tool-specific exceptions inherit from ProcessingError
        assert isinstance(ffmpeg_error, ProcessingError)
        assert isinstance(rife_error, ProcessingError)
        assert isinstance(sanchez_error, ProcessingError)

        # Test other pipeline exceptions inherit directly from PipelineError
        direct_pipeline_exceptions = [
            input_error,
            output_error,
            resource_error,
            config_error,
        ]
        for exc in direct_pipeline_exceptions:
            assert isinstance(exc, PipelineError)
            assert not isinstance(
                exc, ProcessingError
            )  # Should not inherit from ProcessingError

        # All should be exceptions
        all_exceptions = (
            [pipeline_error] + processing_exceptions + direct_pipeline_exceptions
        )
        for exc in all_exceptions:
            assert isinstance(exc, Exception)

    def test_exception_catching_patterns(self):
        """Test different exception catching patterns."""

        def raise_ffmpeg_error():
            raise FFmpegError(
                "FFmpeg failed", command="ffmpeg -i test.mp4", stderr="Codec error"
            )

        def raise_rife_error():
            raise RIFEError("RIFE interpolation failed")

        def raise_resource_error():
            raise ResourceError("Out of memory", resource_type="memory")

        # Catch specific exception types
        with pytest.raises(FFmpegError):
            raise_ffmpeg_error()

        with pytest.raises(RIFEError):
            raise_rife_error()

        with pytest.raises(ResourceError):
            raise_resource_error()

        # Catch as processing errors (for tool-specific errors)
        with pytest.raises(ProcessingError):
            raise_ffmpeg_error()

        with pytest.raises(ProcessingError):
            raise_rife_error()

        # Resource error should not be catchable as ProcessingError
        with pytest.raises(ResourceError):
            raise_resource_error()

        # All should be catchable as PipelineError
        with pytest.raises(PipelineError):
            raise_ffmpeg_error()

        with pytest.raises(PipelineError):
            raise_rife_error()

        with pytest.raises(PipelineError):
            raise_resource_error()

    def test_exception_error_context_preservation(self):
        """Test that exception context is properly preserved."""

        # FFmpeg error with context
        command = "ffmpeg -i input.mp4 -c:v libx264 output.mp4"
        stderr = "Error: Codec 'libx264' not found"
        ffmpeg_error = FFmpegError("Encoding failed", command=command, stderr=stderr)

        assert ffmpeg_error.command == command
        assert ffmpeg_error.stderr == stderr

        # Resource error with context
        resource_error = ResourceError("Memory exhausted", resource_type="memory")

        assert resource_error.resource_type == "memory"


class TestPipelineExceptionIntegration:
    """Integration tests for pipeline exception usage."""

    def test_realistic_pipeline_error_scenarios(self):
        """Test realistic pipeline error scenarios."""

        def simulate_ffmpeg_encoding():
            """Simulate FFmpeg encoding failure."""
            command = "ffmpeg -i satellite_data.mp4 -c:v libx265 -crf 23 output.mp4"
            stderr = "Unknown encoder 'libx265'"
            raise FFmpegError("Video encoding failed", command=command, stderr=stderr)

        def simulate_rife_interpolation():
            """Simulate RIFE interpolation failure."""
            raise RIFEError("Failed to interpolate frames: model file corrupted")

        def simulate_resource_constraint():
            """Simulate resource constraint."""
            raise ResourceError(
                "Insufficient memory for 4K processing", resource_type="memory"
            )

        def simulate_input_validation():
            """Simulate input validation failure."""
            raise InputError("No valid PNG files found in input directory")

        # Test error handling patterns
        scenarios = [
            (simulate_ffmpeg_encoding, FFmpegError, ProcessingError),
            (simulate_rife_interpolation, RIFEError, ProcessingError),
            (simulate_resource_constraint, ResourceError, PipelineError),
            (simulate_input_validation, InputError, PipelineError),
        ]

        for scenario_func, specific_type, parent_type in scenarios:
            # Should be catchable as specific type
            with pytest.raises(specific_type):
                scenario_func()

            # Should be catchable as parent type
            with pytest.raises(parent_type):
                scenario_func()

            # Should be catchable as base pipeline error
            with pytest.raises(PipelineError):
                scenario_func()

    def test_exception_chaining_in_pipeline(self):
        """Test exception chaining in pipeline context."""

        def low_level_operation():
            raise OSError("File not found")

        def pipeline_operation():
            try:
                low_level_operation()
            except OSError as e:
                raise InputError("Failed to read input file") from e

        def high_level_pipeline():
            try:
                pipeline_operation()
            except InputError as e:
                raise PipelineError("Pipeline initialization failed") from e

        with pytest.raises(PipelineError) as exc_info:
            high_level_pipeline()

        # Check exception chain
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, InputError)
        assert exc_info.value.__cause__.__cause__ is not None
        assert isinstance(exc_info.value.__cause__.__cause__, OSError)

    def test_error_message_context_integration(self):
        """Test that error messages provide good context in pipeline scenarios."""

        # FFmpeg error with full context
        ffmpeg_error = FFmpegError(
            "Failed to encode video with HEVC codec",
            command="ffmpeg -i input.mp4 -c:v libx265 -preset slow output.mp4",
            stderr="x265 [error]: cpu-independent minimium VBV buffer size",
        )

        assert "HEVC codec" in str(ffmpeg_error)
        assert (
            ffmpeg_error.command
            == "ffmpeg -i input.mp4 -c:v libx265 -preset slow output.mp4"
        )
        assert "VBV buffer" in ffmpeg_error.stderr

        # Resource error with specific resource type
        resource_error = ResourceError(
            "Processing failed due to memory constraints during 4K frame interpolation",
            resource_type="memory",
        )

        assert "4K frame interpolation" in str(resource_error)
        assert resource_error.resource_type == "memory"

        # Input error with validation details
        input_error = InputError(
            "Input validation failed: expected at least 2 PNG files, found 0 in '/data/frames/'"
        )

        assert "at least 2 PNG files" in str(input_error)
        assert "/data/frames/" in str(input_error)
