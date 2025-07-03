"""
Optimized unit tests for pipeline exceptions with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for exception creation and validation
- Batch testing of exception hierarchy relationships
- Combined error scenario testing with parameterization
- Enhanced coverage for exception chaining and context preservation
"""

from typing import Any, Never

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


class TestPipelineExceptionsOptimizedV2:
    """Optimized pipeline exception tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def exception_test_components() -> dict[str, Any]:  # noqa: C901
        """Create shared components for exception testing.

        Returns:
            dict[str, Any]: Dictionary containing test manager instance.
        """

        # Enhanced Exception Test Manager
        class ExceptionTestManager:
            """Manage pipeline exception testing scenarios."""

            def __init__(self) -> None:
                self.exception_configs = {
                    "pipeline_error": {
                        "class": PipelineError,
                        "parent_classes": [Exception],
                        "test_messages": [
                            "Pipeline processing failed",
                            "General pipeline error",
                            "Processing workflow interrupted",
                        ],
                        "has_attributes": [],
                        "scenarios": ["basic", "inheritance"],
                    },
                    "processing_error": {
                        "class": ProcessingError,
                        "parent_classes": [PipelineError, Exception],
                        "test_messages": [
                            "Video processing failed",
                            "Processing step error",
                            "Unable to process input",
                        ],
                        "has_attributes": [],
                        "scenarios": ["basic", "inheritance", "processing_specific"],
                    },
                    "ffmpeg_error": {
                        "class": FFmpegError,
                        "parent_classes": [ProcessingError, PipelineError, Exception],
                        "test_messages": ["Encoding failed", "FFmpeg execution error", "Video codec error"],
                        "has_attributes": ["command", "stderr"],
                        "scenarios": ["minimal", "with_command", "with_stderr", "full"],
                    },
                    "rife_error": {
                        "class": RIFEError,
                        "parent_classes": [ProcessingError, PipelineError, Exception],
                        "test_messages": [
                            "Frame interpolation failed",
                            "RIFE model error",
                            "Insufficient memory for RIFE processing",
                        ],
                        "has_attributes": [],
                        "scenarios": ["basic", "model_scenarios"],
                    },
                    "sanchez_error": {
                        "class": SanchezError,
                        "parent_classes": [ProcessingError, PipelineError, Exception],
                        "test_messages": [
                            "Image processing failed",
                            "Sanchez executable error",
                            "False color enhancement failed",
                        ],
                        "has_attributes": [],
                        "scenarios": ["basic", "image_scenarios"],
                    },
                    "input_error": {
                        "class": InputError,
                        "parent_classes": [PipelineError, Exception],
                        "test_messages": ["Invalid input file format", "No PNG files found", "Input validation failed"],
                        "has_attributes": [],
                        "scenarios": ["basic", "validation_scenarios"],
                    },
                    "output_error": {
                        "class": OutputError,
                        "parent_classes": [PipelineError, Exception],
                        "test_messages": [
                            "Failed to write output file",
                            "Insufficient disk space",
                            "Permission denied",
                        ],
                        "has_attributes": [],
                        "scenarios": ["basic", "output_scenarios"],
                    },
                    "resource_error": {
                        "class": ResourceError,
                        "parent_classes": [PipelineError, Exception],
                        "test_messages": ["Insufficient resources", "Memory exhausted", "CPU overloaded"],
                        "has_attributes": ["resource_type"],
                        "scenarios": ["minimal", "with_type", "different_types"],
                    },
                    "configuration_error": {
                        "class": ConfigurationError,
                        "parent_classes": [PipelineError, Exception],
                        "test_messages": [
                            "Invalid pipeline configuration",
                            "Missing required parameter",
                            "Conflicting options",
                        ],
                        "has_attributes": [],
                        "scenarios": ["basic", "config_scenarios"],
                    },
                }

                self.test_scenarios = {
                    "creation_validation": self._test_creation_validation,
                    "inheritance_validation": self._test_inheritance_validation,
                    "attribute_validation": self._test_attribute_validation,
                    "scenario_validation": self._test_scenario_validation,
                    "hierarchy_integration": self._test_hierarchy_integration,
                    "catching_patterns": self._test_catching_patterns,
                    "context_preservation": self._test_context_preservation,
                    "realistic_scenarios": self._test_realistic_scenarios,
                    "exception_chaining": self._test_exception_chaining,
                    "message_context": self._test_message_context,
                }

            def _test_creation_validation(self, exception_name: str, config: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR6301
                """Test exception creation and basic validation.

                Returns:
                    dict[str, Any]: Dictionary with error instance and message.
                """
                exception_class = config["class"]
                test_message = config["test_messages"][0]

                # Create basic exception
                if exception_name == "ffmpeg_error":
                    # Test minimal creation
                    error = exception_class(test_message)
                    assert str(error) == test_message
                    assert not error.command
                    assert not error.stderr
                elif exception_name == "resource_error":
                    # Test minimal creation
                    error = exception_class(test_message)
                    assert str(error) == test_message
                    assert not error.resource_type
                else:
                    # Standard creation
                    error = exception_class(test_message)
                    assert str(error) == test_message

                assert isinstance(error, exception_class)

                return {"error": error, "message": test_message}

            def _test_inheritance_validation(self, exception_name: str, config: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR6301, ARG002
                """Test exception inheritance relationships.

                Returns:
                    dict[str, Any]: Dictionary with error and validated parents.
                """
                exception_class = config["class"]
                parent_classes = config["parent_classes"]
                test_message = config["test_messages"][0]

                error = exception_class(test_message)

                # Test inheritance chain
                for parent_class in parent_classes:
                    assert isinstance(error, parent_class)

                return {"error": error, "validated_parents": parent_classes}

            def _test_attribute_validation(self, exception_name: str, config: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR6301
                """Test exception-specific attributes.

                Returns:
                    dict[str, Any]: Dictionary with attribute test results.
                """
                exception_class = config["class"]
                config["has_attributes"]
                test_message = config["test_messages"][0]

                results: dict[str, Any] = {}

                if exception_name == "ffmpeg_error":
                    # Test with command
                    command = "ffmpeg -i input.mp4 -c:v libx264 output.mp4"
                    error_with_cmd = exception_class(test_message, command=command)
                    assert error_with_cmd.command == command
                    assert not error_with_cmd.stderr

                    # Test with stderr
                    stderr = "Error: Unknown encoder 'libx265'"
                    error_with_stderr = exception_class(test_message, stderr=stderr)
                    assert not error_with_stderr.command
                    assert error_with_stderr.stderr == stderr

                    # Test with both
                    error_full = exception_class(test_message, command=command, stderr=stderr)
                    assert error_full.command == command
                    assert error_full.stderr == stderr

                    results["command_test"] = error_with_cmd
                    results["stderr_test"] = error_with_stderr
                    results["full_test"] = error_full

                elif exception_name == "resource_error":
                    # Test with resource type
                    resource_type = "memory"
                    error_with_type = exception_class(test_message, resource_type=resource_type)
                    assert error_with_type.resource_type == resource_type

                    results["resource_type_test"] = error_with_type

                return results

            def _test_scenario_validation(self, exception_name: str, config: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR6301, C901
                """Test exception-specific scenarios.

                Returns:
                    dict[str, Any]: Dictionary with scenario test results.
                """
                exception_class = config["class"]
                config["test_messages"]

                results: dict[str, Any] = {}

                if exception_name == "rife_error":
                    # Test RIFE-specific scenarios
                    rife_scenarios = [
                        "RIFE model not found",
                        "Insufficient memory for RIFE processing",
                        "RIFE executable not found",
                        "Input images have incompatible dimensions",
                    ]

                    for scenario in rife_scenarios:
                        error = exception_class(scenario)
                        assert scenario in str(error)
                        assert isinstance(error, ProcessingError)

                    results["rife_scenarios"] = rife_scenarios

                elif exception_name == "sanchez_error":
                    # Test Sanchez-specific scenarios
                    sanchez_scenarios = [
                        "Sanchez executable not found",
                        "Invalid satellite data format",
                        "Unsupported image resolution",
                        "Failed to apply false color enhancement",
                    ]

                    for scenario in sanchez_scenarios:
                        error = exception_class(scenario)
                        assert scenario in str(error)
                        assert isinstance(error, ProcessingError)

                    results["sanchez_scenarios"] = sanchez_scenarios

                elif exception_name == "input_error":
                    # Test input validation scenarios
                    input_scenarios = [
                        "No PNG files found in input directory",
                        "Image dimensions are too small",
                        "Unsupported file format",
                        "Input path does not exist",
                    ]

                    for scenario in input_scenarios:
                        error = exception_class(scenario)
                        assert scenario in str(error)
                        assert isinstance(error, PipelineError)
                        assert not isinstance(error, ProcessingError)

                    results["input_scenarios"] = input_scenarios

                elif exception_name == "output_error":
                    # Test output operation scenarios
                    output_scenarios = [
                        "Insufficient disk space",
                        "Permission denied writing to output directory",
                        "Output file already exists and cannot be overwritten",
                        "Invalid output path",
                    ]

                    for scenario in output_scenarios:
                        error = exception_class(scenario)
                        assert scenario in str(error)
                        assert isinstance(error, PipelineError)
                        assert not isinstance(error, ProcessingError)

                    results["output_scenarios"] = output_scenarios

                elif exception_name == "resource_error":
                    # Test different resource types
                    resource_scenarios = [
                        ("Insufficient memory", "memory"),
                        ("Disk space full", "disk"),
                        ("CPU overloaded", "cpu"),
                        ("Too many open files", "file_handles"),
                        ("Network bandwidth exceeded", "network"),
                    ]

                    for message, resource_type in resource_scenarios:
                        error = exception_class(message, resource_type=resource_type)
                        assert message in str(error)
                        assert error.resource_type == resource_type
                        assert isinstance(error, PipelineError)
                        assert not isinstance(error, ProcessingError)

                    results["resource_scenarios"] = resource_scenarios

                elif exception_name == "configuration_error":
                    # Test configuration scenarios
                    config_scenarios = [
                        "Missing required configuration parameter 'fps'",
                        "Invalid encoder settings",
                        "Conflicting pipeline options",
                        "Unsupported processing mode",
                    ]

                    for scenario in config_scenarios:
                        error = exception_class(scenario)
                        assert scenario in str(error)
                        assert isinstance(error, PipelineError)
                        assert not isinstance(error, ProcessingError)

                    results["config_scenarios"] = config_scenarios

                return results

            def _test_hierarchy_integration(self) -> dict[str, Any]:
                """Test complete exception hierarchy structure.

                Returns:
                    dict[str, Any]: Dictionary with instances and hierarchy validation status.
                """
                # Create instances of all exception types
                instances = {}
                for name, config in self.exception_configs.items():
                    exception_class = config["class"]
                    test_messages = config.get("test_messages", [])
                    message = test_messages[0] if test_messages else "Test error"

                    if name == "ffmpeg_error":
                        instances[name] = exception_class(message, command="test", stderr="test")
                    elif name == "resource_error":
                        instances[name] = exception_class(message, resource_type="memory")
                    else:
                        instances[name] = exception_class(message)

                # Test processing error inheritance
                processing_exceptions = ["processing_error", "ffmpeg_error", "rife_error", "sanchez_error"]
                for exc_name in processing_exceptions:
                    exc = instances[exc_name]
                    assert isinstance(exc, ProcessingError)
                    assert isinstance(exc, PipelineError)
                    assert isinstance(exc, Exception)

                # Test direct pipeline error inheritance
                direct_pipeline_exceptions = ["input_error", "output_error", "resource_error", "configuration_error"]
                for exc_name in direct_pipeline_exceptions:
                    exc = instances[exc_name]
                    assert isinstance(exc, PipelineError)
                    assert not isinstance(exc, ProcessingError)
                    assert isinstance(exc, Exception)

                return {"instances": instances, "hierarchy_validated": True}

            def _test_catching_patterns(self) -> dict[str, Any]:  # noqa: PLR6301
                """Test exception catching patterns.

                Returns:
                    dict[str, Any]: Dictionary with catching patterns validation status.
                """
                results: dict[str, Any] = {}

                def raise_ffmpeg_error() -> Never:
                    msg = "FFmpeg failed"
                    raise FFmpegError(msg, command="ffmpeg -i test.mp4", stderr="Codec error")

                def raise_rife_error() -> Never:
                    msg = "RIFE interpolation failed"
                    raise RIFEError(msg)

                def raise_resource_error() -> Never:
                    msg = "Out of memory"
                    raise ResourceError(msg, resource_type="memory")

                # Test specific exception catching
                with pytest.raises(FFmpegError):
                    raise_ffmpeg_error()

                with pytest.raises(RIFEError):
                    raise_rife_error()

                with pytest.raises(ResourceError):
                    raise_resource_error()

                # Test processing error catching (for tool-specific errors)
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

                results["catching_patterns_validated"] = True
                return results

            def _test_context_preservation(self) -> dict[str, Any]:  # noqa: PLR6301
                """Test exception context preservation.

                Returns:
                    dict[str, Any]: Dictionary with context preservation test results.
                """
                # FFmpeg error with context
                command = "ffmpeg -i input.mp4 -c:v libx264 output.mp4"
                stderr = "Error: Codec 'libx264' not found"
                ffmpeg_error = FFmpegError("Encoding failed", command=command, stderr=stderr)

                assert ffmpeg_error.command == command
                assert ffmpeg_error.stderr == stderr

                # Resource error with context
                resource_error = ResourceError("Memory exhausted", resource_type="memory")
                assert resource_error.resource_type == "memory"

                return {"ffmpeg_context": ffmpeg_error, "resource_context": resource_error}

            def _test_realistic_scenarios(self) -> dict[str, Any]:  # noqa: PLR6301
                """Test realistic pipeline error scenarios.

                Returns:
                    dict[str, Any]: Dictionary with realistic scenario test results.
                """
                results: dict[str, Any] = {}

                def simulate_ffmpeg_encoding() -> Never:
                    command = "ffmpeg -i satellite_data.mp4 -c:v libx265 -crf 23 output.mp4"
                    stderr = "Unknown encoder 'libx265'"
                    msg = "Video encoding failed"
                    raise FFmpegError(msg, command=command, stderr=stderr)

                def simulate_rife_interpolation() -> Never:
                    msg = "Failed to interpolate frames: model file corrupted"
                    raise RIFEError(msg)

                def simulate_resource_constraint() -> Never:
                    msg = "Insufficient memory for 4K processing"
                    raise ResourceError(msg, resource_type="memory")

                def simulate_input_validation() -> Never:
                    msg = "No valid PNG files found in input directory"
                    raise InputError(msg)

                scenarios = [
                    (simulate_ffmpeg_encoding, FFmpegError, ProcessingError),
                    (simulate_rife_interpolation, RIFEError, ProcessingError),
                    (simulate_resource_constraint, ResourceError, PipelineError),
                    (simulate_input_validation, InputError, PipelineError),
                ]

                for i, (scenario_func, specific_type, parent_type) in enumerate(scenarios):
                    # Should be catchable as specific type
                    with pytest.raises(specific_type):
                        scenario_func()

                    # Should be catchable as parent type
                    with pytest.raises(parent_type):
                        scenario_func()

                    # Should be catchable as base pipeline error
                    with pytest.raises(PipelineError):
                        scenario_func()

                    results[f"scenario_{i}"] = {"specific": specific_type, "parent": parent_type}

                return results

            def _test_exception_chaining(self) -> dict[str, Any]:  # noqa: PLR6301
                """Test exception chaining in pipeline context.

                Returns:
                    dict[str, Any]: Dictionary with exception chain validation status.
                """

                def low_level_operation() -> Never:
                    msg = "File not found"
                    raise OSError(msg)

                def pipeline_operation() -> None:
                    try:
                        low_level_operation()
                    except OSError as e:
                        msg = "Failed to read input file"
                        raise InputError(msg) from e

                def high_level_pipeline() -> None:
                    try:
                        pipeline_operation()
                    except InputError as e:
                        msg = "Pipeline initialization failed"
                        raise PipelineError(msg) from e

                with pytest.raises(PipelineError) as exc_info:
                    high_level_pipeline()

                # Check exception chain
                assert exc_info.value.__cause__ is not None
                assert isinstance(exc_info.value.__cause__, InputError)
                assert exc_info.value.__cause__.__cause__ is not None
                assert isinstance(exc_info.value.__cause__.__cause__, OSError)

                return {"exception_chain_validated": True, "chain_length": 3}

            def _test_message_context(self) -> dict[str, Any]:  # noqa: PLR6301
                """Test error message context integration.

                Returns:
                    dict[str, Any]: Dictionary with message context test results.
                """
                # FFmpeg error with full context
                ffmpeg_error = FFmpegError(
                    "Failed to encode video with HEVC codec",
                    command="ffmpeg -i input.mp4 -c:v libx265 -preset slow output.mp4",
                    stderr="x265 [error]: cpu-independent minimium VBV buffer size",
                )

                assert "HEVC codec" in str(ffmpeg_error)
                assert ffmpeg_error.command == "ffmpeg -i input.mp4 -c:v libx265 -preset slow output.mp4"
                assert "VBV buffer" in ffmpeg_error.stderr

                # Resource error with specific context
                resource_error = ResourceError(
                    "Processing failed due to memory constraints during 4K frame interpolation",
                    resource_type="memory",
                )

                assert "4K frame interpolation" in str(resource_error)
                assert resource_error.resource_type == "memory"

                # Input error with validation details
                input_error = InputError(
                    "Input validation failed: expected at least 2 PNG files, found 0 in '/data/frames/'",
                )

                assert "at least 2 PNG files" in str(input_error)
                assert "/data/frames/" in str(input_error)

                return {
                    "ffmpeg_context": ffmpeg_error,
                    "resource_context": resource_error,
                    "input_context": input_error,
                }

        return {
            "manager": ExceptionTestManager(),
            "exception_types": list(ExceptionTestManager().exception_configs.keys()),
        }

    def test_exception_creation_validation(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test exception creation and basic validation."""
        manager = exception_test_components["manager"]

        for exception_name, config in manager.exception_configs.items():
            results = manager._test_creation_validation(exception_name, config)  # noqa: SLF001

            # Verify basic creation worked
            assert results["error"] is not None
            assert str(results["error"]) == results["message"]

    def test_exception_inheritance_validation(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test exception inheritance relationships."""
        manager = exception_test_components["manager"]

        for exception_name, config in manager.exception_configs.items():
            results = manager._test_inheritance_validation(exception_name, config)  # noqa: SLF001

            # Verify inheritance validation
            assert len(results["validated_parents"]) > 0
            assert results["error"] is not None

    def test_exception_attribute_validation(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test exception-specific attributes."""
        manager = exception_test_components["manager"]

        for exception_name, config in manager.exception_configs.items():
            if config["has_attributes"]:
                results = manager._test_attribute_validation(exception_name, config)  # noqa: SLF001
                assert len(results) > 0  # Should have attribute tests

    def test_exception_scenario_validation(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test exception-specific scenarios."""
        manager = exception_test_components["manager"]

        scenario_exceptions = [
            "rife_error",
            "sanchez_error",
            "input_error",
            "output_error",
            "resource_error",
            "configuration_error",
        ]

        for exception_name in scenario_exceptions:
            config = manager.exception_configs[exception_name]
            results = manager._test_scenario_validation(exception_name, config)  # noqa: SLF001
            assert len(results) > 0  # Should have scenario tests

    def test_exception_hierarchy_integration(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test complete exception hierarchy structure."""
        manager = exception_test_components["manager"]

        results = manager._test_hierarchy_integration()  # noqa: SLF001

        assert results["hierarchy_validated"] is True
        assert len(results["instances"]) == len(manager.exception_configs)

    def test_exception_catching_patterns(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test exception catching patterns."""
        manager = exception_test_components["manager"]

        results = manager._test_catching_patterns()  # noqa: SLF001

        assert results["catching_patterns_validated"] is True

    def test_exception_context_preservation(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test exception context preservation."""
        manager = exception_test_components["manager"]

        results = manager._test_context_preservation()  # noqa: SLF001

        assert "ffmpeg_context" in results
        assert "resource_context" in results

    def test_realistic_pipeline_scenarios(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test realistic pipeline error scenarios."""
        manager = exception_test_components["manager"]

        results = manager._test_realistic_scenarios()  # noqa: SLF001

        # Should have tested 4 scenarios
        assert len([k for k in results if k.startswith("scenario_")]) == 4

    def test_exception_chaining_integration(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test exception chaining in pipeline context."""
        manager = exception_test_components["manager"]

        results = manager._test_exception_chaining()  # noqa: SLF001

        assert results["exception_chain_validated"] is True
        assert results["chain_length"] == 3

    def test_message_context_integration(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test error message context integration."""
        manager = exception_test_components["manager"]

        results = manager._test_message_context()  # noqa: SLF001

        assert "ffmpeg_context" in results
        assert "resource_context" in results
        assert "input_context" in results

    @pytest.mark.parametrize(
        "exception_name,test_messages",
        [
            ("pipeline_error", ["Pipeline processing failed", "General pipeline error"]),
            ("processing_error", ["Video processing failed", "Processing step error"]),
            ("ffmpeg_error", ["Encoding failed", "FFmpeg execution error"]),
            ("rife_error", ["Frame interpolation failed", "RIFE model error"]),
            ("sanchez_error", ["Image processing failed", "Sanchez executable error"]),
            ("input_error", ["Invalid input file format", "No PNG files found"]),
            ("output_error", ["Failed to write output file", "Insufficient disk space"]),
            ("resource_error", ["Insufficient resources", "Memory exhausted"]),
            ("configuration_error", ["Invalid pipeline configuration", "Missing required parameter"]),
        ],
    )
    def test_exception_message_variations(  # noqa: PLR6301
        self,
        exception_test_components: dict[str, Any],
        exception_name: str,
        test_messages: list[str],
    ) -> None:
        """Test exception creation with various messages."""
        manager = exception_test_components["manager"]
        config = manager.exception_configs[exception_name]
        exception_class = config["class"]

        for message in test_messages:
            if exception_name == "ffmpeg_error":
                error = exception_class(message)
                assert str(error) == message
                assert not error.command
                assert not error.stderr
            elif exception_name == "resource_error":
                error = exception_class(message)
                assert str(error) == message
                assert not error.resource_type
            else:
                error = exception_class(message)
                assert str(error) == message

            assert isinstance(error, exception_class)

    def test_exception_edge_cases(self, exception_test_components: dict[str, Any]) -> None:  # noqa: ARG002, PLR6301
        """Test exception edge cases and error conditions."""
        # Test empty messages
        for exception_class in [
            PipelineError,
            ProcessingError,
            FFmpegError,
            RIFEError,
            SanchezError,
            InputError,
            OutputError,
            ResourceError,
            ConfigurationError,
        ]:
            error = exception_class("")
            assert not str(error)
            assert isinstance(error, exception_class)

        # Test special characters in messages
        special_message = "Error with special chars: !@#$%^&*()_+ 中文 🚀"
        for exception_class in [PipelineError, ProcessingError, InputError]:
            error = exception_class(special_message)
            assert str(error) == special_message

        # Test very long messages
        long_message = "A" * 1000
        error = PipelineError(long_message)
        assert str(error) == long_message
        assert len(str(error)) == 1000

    def test_exception_performance_validation(self, exception_test_components: dict[str, Any]) -> None:  # noqa: PLR6301
        """Test exception creation and validation performance."""
        manager = exception_test_components["manager"]

        # Test batch creation
        exceptions_created = []
        for i in range(100):
            for exception_name, config in manager.exception_configs.items():
                exception_class = config["class"]
                message = f"Test error {i}"

                if exception_name == "ffmpeg_error":
                    error = exception_class(message, command=f"command_{i}", stderr=f"stderr_{i}")
                elif exception_name == "resource_error":
                    error = exception_class(message, resource_type="memory")
                else:
                    error = exception_class(message)

                exceptions_created.append(error)

        # Verify all exceptions were created correctly
        assert len(exceptions_created) == 100 * len(manager.exception_configs)

        # Test inheritance checks are still valid
        processing_count = 0
        pipeline_count = 0

        for error in exceptions_created:
            if isinstance(error, ProcessingError):
                processing_count += 1
            if isinstance(error, PipelineError):
                pipeline_count += 1

        # Should have 4 processing error types * 100 = 400 processing errors
        assert processing_count == 400
        # Should have all 9 exception types * 100 = 900 pipeline errors
        assert pipeline_count == 900
