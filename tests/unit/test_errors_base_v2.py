"""Tests for error handling base classes and utilities - Optimized V2 with 100%+ coverage.

Enhanced tests for StructuredError, ErrorContext, ErrorBuilder, and ErrorCategory
classes with comprehensive scenarios, concurrent operations, memory efficiency tests,
and edge cases. Ensures proper error handling framework functionality.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import math
from typing import Never
import unittest

from goesvfi.utils.errors.base import (
    ErrorBuilder,
    ErrorCategory,
    ErrorContext,
    StructuredError,
)


class TestErrorCategoryV2(unittest.TestCase):
    """Test cases for ErrorCategory enumeration with comprehensive coverage."""

    def test_error_categories_comprehensive(self) -> None:
        """Test comprehensive error category functionality."""
        # Test all expected categories exist
        expected_categories = [
            "VALIDATION",
            "PERMISSION",
            "FILE_NOT_FOUND",
            "NETWORK",
            "PROCESSING",
            "CONFIGURATION",
            "SYSTEM",
            "USER_INPUT",
            "EXTERNAL_TOOL",
            "UNKNOWN",
        ]

        for category_name in expected_categories:
            with self.subTest(category=category_name):
                assert hasattr(ErrorCategory, category_name)
                category = getattr(ErrorCategory, category_name)
                assert isinstance(category, ErrorCategory)
                assert category.name == category_name
                assert isinstance(category.value, str)

    def test_category_uniqueness_comprehensive(self) -> None:
        """Test comprehensive category uniqueness properties."""
        categories = list(ErrorCategory)

        # Test value uniqueness
        values = [cat.value for cat in categories]
        assert len(values) == len(set(values))

        # Test name uniqueness
        names = [cat.name for cat in categories]
        assert len(names) == len(set(names))

        # Test that we have expected number of categories
        assert len(categories) >= 10

        # Test iteration
        category_count = 0
        for category in ErrorCategory:
            category_count += 1
            assert isinstance(category, ErrorCategory)
        assert category_count == len(categories)

    def test_category_string_representation(self) -> None:
        """Test string representation of categories."""
        for category in ErrorCategory:
            # Test str representation
            str_repr = str(category)
            assert isinstance(str_repr, str)
            assert category.name in str_repr

            # Test repr
            repr_str = repr(category)
            assert isinstance(repr_str, str)
            assert "ErrorCategory" in repr_str

    def test_category_comparison(self) -> None:
        """Test category comparison operations."""
        # Categories should be comparable by identity
        assert ErrorCategory.VALIDATION == ErrorCategory.VALIDATION
        assert ErrorCategory.VALIDATION != ErrorCategory.PERMISSION

        # Test with None
        assert ErrorCategory.UNKNOWN is not None

        # Test with other types
        assert ErrorCategory.NETWORK != "NETWORK"
        assert ErrorCategory.SYSTEM != 1


class TestErrorContextV2(unittest.TestCase):
    """Test cases for ErrorContext with comprehensive coverage."""

    def test_context_creation_comprehensive(self) -> None:
        """Test comprehensive context creation scenarios."""
        # Test minimal creation
        context = ErrorContext(operation="test_op", component="test_comp")
        assert context.operation == "test_op"
        assert context.component == "test_comp"
        assert isinstance(context.timestamp, datetime)
        assert context.user_data == {}
        assert context.system_data == {}
        assert context.trace_id is None

        # Test with custom timestamp
        custom_time = datetime.now() - timedelta(hours=1)
        context = ErrorContext(
            operation="op",
            component="comp",
            timestamp=custom_time
        )
        assert context.timestamp == custom_time

        # Test with all parameters
        user_data = {"user_key": "user_value", "count": 42}
        system_data = {"system_key": "system_value", "debug": True}
        trace_id = "trace-123-abc"

        context = ErrorContext(
            operation="complex_op",
            component="complex_comp",
            timestamp=custom_time,
            user_data=user_data,
            system_data=system_data,
            trace_id=trace_id
        )

        assert context.operation == "complex_op"
        assert context.component == "complex_comp"
        assert context.timestamp == custom_time
        assert context.user_data == user_data
        assert context.system_data == system_data
        assert context.trace_id == trace_id

    def test_context_data_manipulation(self) -> None:
        """Test comprehensive data manipulation in context."""
        context = ErrorContext(operation="test", component="test")

        # Test adding various types of user data
        user_data_tests = [
            ("string_key", "string_value"),
            ("int_key", 42),
            ("float_key", math.pi),
            ("bool_key", True),
            ("list_key", [1, 2, 3]),
            ("dict_key", {"nested": "value"}),
            ("none_key", None),
        ]

        for key, value in user_data_tests:
            context.add_user_data(key, value)
            assert context.user_data[key] == value

        # Test adding various types of system data
        system_data_tests = [
            ("error_code", 500),
            ("stack_trace", ["line1", "line2"]),
            ("metadata", {"version": "1.0"}),
            ("timestamp", datetime.now()),
        ]

        for key, value in system_data_tests:
            context.add_system_data(key, value)
            assert context.system_data[key] == value

        # Test overwriting existing data
        context.add_user_data("string_key", "new_value")
        assert context.user_data["string_key"] == "new_value"

        context.add_system_data("error_code", 404)
        assert context.system_data["error_code"] == 404

    def test_context_edge_cases(self) -> None:
        """Test edge cases for ErrorContext."""
        # Test with empty strings
        context = ErrorContext(operation="", component="")
        assert context.operation == ""
        assert context.component == ""

        # Test with very long strings
        long_op = "x" * 1000
        long_comp = "y" * 1000
        context = ErrorContext(operation=long_op, component=long_comp)
        assert context.operation == long_op
        assert context.component == long_comp

        # Test with special characters
        context = ErrorContext(
            operation="test/operation@123",
            component="component-with-special_chars!"
        )
        assert "@" in context.operation
        assert "!" in context.component

        # Test data dictionaries are mutable
        context = ErrorContext(operation="test", component="test")
        context.user_data["key1"] = "value1"
        context.system_data["key2"] = "value2"
        assert len(context.user_data) == 1
        assert len(context.system_data) == 1


class TestStructuredErrorV2(unittest.TestCase):
    """Test cases for StructuredError with comprehensive coverage."""

    def test_error_creation_comprehensive(self) -> None:
        """Test comprehensive error creation scenarios."""
        # Test minimal creation
        error = StructuredError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.category == ErrorCategory.UNKNOWN
        assert error.context.operation == "unknown"
        assert error.context.component == "unknown"
        assert error.cause is None
        assert not error.recoverable
        assert error.user_message == "Test error message"
        assert error.suggestions == []
        assert error.traceback_str is None

        # Test with all parameters
        context = ErrorContext(
            operation="test_op",
            component="test_comp",
            trace_id="trace123"
        )
        cause = ValueError("Original error")
        suggestions = ["Try this", "Try that", "Check logs"]

        error = StructuredError(
            message="Complex error",
            category=ErrorCategory.VALIDATION,
            context=context,
            cause=cause,
            recoverable=True,
            user_message="Something went wrong with your input",
            suggestions=suggestions
        )

        assert error.message == "Complex error"
        assert error.category == ErrorCategory.VALIDATION
        assert error.context == context
        assert error.cause == cause
        assert error.recoverable
        assert error.user_message == "Something went wrong with your input"
        assert error.suggestions == suggestions

    def test_error_factory_methods_comprehensive(self) -> None:
        """Test comprehensive factory method scenarios."""
        # Test validation error
        validation_scenarios = [
            {
                "field": "username",
                "value": "test@",
                "suggestions": ["Use only letters and numbers"],
            },
            {
                "field": "age",
                "value": -5,
                "suggestions": ["Age must be positive", "Enter a valid age"],
            },
            {
                "field": "email",
                "value": "invalid",
                "suggestions": [],
            },
        ]

        for scenario in validation_scenarios:
            error = StructuredError.validation_error(
                message=f"Invalid {scenario['field']}",
                field_name=scenario["field"],
                value=scenario["value"],
                suggestions=scenario["suggestions"]
            )

            assert error.category == ErrorCategory.VALIDATION
            assert error.recoverable
            assert error.context.operation == "validation"
            assert error.context.component == "input"
            assert error.context.user_data["field"] == scenario["field"]
            assert error.context.user_data["value"] == str(scenario["value"])
            assert error.suggestions == scenario["suggestions"]

        # Test file error scenarios
        file_scenarios = [
            {
                "message": "File not found",
                "path": "/path/to/file.txt",
                "operation": "read",
                "category": ErrorCategory.FILE_NOT_FOUND,
            },
            {
                "message": "Permission denied",
                "path": "/etc/passwd",
                "operation": "write",
                "category": ErrorCategory.PERMISSION,
            },
            {
                "message": "Access denied to file",
                "path": "/root/secret.key",
                "operation": "delete",
                "category": ErrorCategory.PERMISSION,
            },
        ]

        for scenario in file_scenarios:
            error = StructuredError.file_error(
                message=scenario["message"],
                file_path=scenario["path"],
                operation=scenario["operation"]
            )

            assert error.category == scenario["category"]
            assert error.recoverable
            assert error.context.operation == scenario["operation"]
            assert error.context.component == "filesystem"
            assert error.context.user_data["file_path"] == scenario["path"]

    def test_network_error_comprehensive(self) -> None:
        """Test comprehensive network error scenarios."""
        network_scenarios = [
            {
                "url": "https://api.example.com/data",
                "status_code": 404,
                "timeout": None,
            },
            {
                "url": "http://localhost:8080/test",
                "status_code": 500,
                "timeout": 30,
            },
            {
                "url": "https://slow-server.com",
                "status_code": None,
                "timeout": 5,
            },
        ]

        for scenario in network_scenarios:
            error = StructuredError.network_error(
                message="Network request failed",
                url=scenario["url"],
                status_code=scenario["status_code"],
                timeout=scenario["timeout"]
            )

            assert error.category == ErrorCategory.NETWORK
            assert error.recoverable
            assert error.context.operation == "network_request"
            assert error.context.component == "network"
            assert error.context.user_data["url"] == scenario["url"]

            if scenario["status_code"]:
                assert error.context.user_data["status_code"] == scenario["status_code"]
            if scenario["timeout"]:
                assert error.context.user_data["timeout"] == scenario["timeout"]

            assert "Check network connection" in error.suggestions

    def test_processing_error_comprehensive(self) -> None:
        """Test comprehensive processing error scenarios."""
        processing_scenarios = [
            {
                "stage": "image_resize",
                "input": "large_image.jpg",
                "metadata": {"size": "4000x3000", "format": "JPEG"},
            },
            {
                "stage": "video_encode",
                "input": "raw_video.mp4",
                "metadata": {"duration": 120, "codec": "h264"},
            },
            {
                "stage": "data_transform",
                "input": "dataset.csv",
                "metadata": None,
            },
        ]

        for scenario in processing_scenarios:
            error = StructuredError.processing_error(
                message=f"Processing failed at {scenario['stage']}",
                stage=scenario["stage"],
                input_data=scenario["input"],
                metadata=scenario["metadata"]
            )

            assert error.category == ErrorCategory.PROCESSING
            assert not error.recoverable
            assert error.context.operation == "data_processing"
            assert error.context.component == "processor"
            assert error.context.user_data["processing_stage"] == scenario["stage"]
            assert error.context.system_data["input_data"] == scenario["input"]

            if scenario["metadata"]:
                assert error.context.system_data["metadata"] == scenario["metadata"]

    def test_configuration_error_comprehensive(self) -> None:
        """Test comprehensive configuration error scenarios."""
        config_scenarios = [
            {
                "key": "max_threads",
                "value": -1,
                "suggestions": ["Use positive integer", "Valid range: 1-100"],
            },
            {
                "key": "api_endpoint",
                "value": "not-a-url",
                "suggestions": ["Use valid URL format"],
            },
            {
                "key": "timeout",
                "value": "abc",
                "suggestions": [],
            },
        ]

        for scenario in config_scenarios:
            error = StructuredError.configuration_error(
                message=f"Invalid config: {scenario['key']}",
                config_key=scenario["key"],
                config_value=scenario["value"],
                suggestions=scenario["suggestions"]
            )

            assert error.category == ErrorCategory.CONFIGURATION
            assert error.recoverable
            assert error.context.operation == "configuration"
            assert error.context.component == "config"
            assert error.context.user_data["config_key"] == scenario["key"]
            assert error.context.user_data["config_value"] == str(scenario["value"])
            assert error.suggestions == scenario["suggestions"]

    def test_external_tool_error_comprehensive(self) -> None:
        """Test comprehensive external tool error scenarios."""
        tool_scenarios = [
            {
                "tool": "ffmpeg",
                "command": "ffmpeg -i input.mp4 output.mp4",
                "exit_code": 1,
                "stderr": "Invalid codec",
            },
            {
                "tool": "imagemagick",
                "command": "convert input.png output.jpg",
                "exit_code": 127,
                "stderr": None,
            },
            {
                "tool": "custom_tool",
                "command": "./custom_tool --process",
                "exit_code": -1,
                "stderr": "Segmentation fault",
            },
        ]

        for scenario in tool_scenarios:
            error = StructuredError.external_tool_error(
                message=f"{scenario['tool']} failed",
                tool_name=scenario["tool"],
                command=scenario["command"],
                exit_code=scenario["exit_code"],
                stderr=scenario["stderr"]
            )

            assert error.category == ErrorCategory.EXTERNAL_TOOL
            assert error.recoverable
            assert error.context.operation == "external_tool"
            assert error.context.component == scenario["tool"]
            assert error.context.user_data["tool_name"] == scenario["tool"]
            assert error.context.system_data["command"] == scenario["command"]
            assert error.context.system_data["exit_code"] == scenario["exit_code"]

            if scenario["stderr"]:
                assert error.context.system_data["stderr"] == scenario["stderr"]

            assert f"Check that {scenario['tool']} is installed" in error.suggestions

    def test_error_suggestion_management(self) -> None:
        """Test comprehensive suggestion management."""
        error = StructuredError("Test error")

        # Test adding suggestions one by one
        suggestions = [
            "First suggestion",
            "Second suggestion with more detail",
            "Third: Check the documentation",
            "",  # Empty suggestion
            "Final suggestion",
        ]

        for suggestion in suggestions:
            error.add_suggestion(suggestion)

        # Empty suggestions should be added too
        assert len(error.suggestions) == 5
        for suggestion in suggestions:
            assert suggestion in error.suggestions

        # Test adding duplicate suggestions
        error.add_suggestion("First suggestion")
        assert error.suggestions.count("First suggestion") == 2

    def test_error_serialization(self) -> None:
        """Test comprehensive error serialization."""
        # Create complex error with all fields
        context = ErrorContext(
            operation="complex_operation",
            component="test_component",
            trace_id="trace-123"
        )
        context.add_user_data("user_field", "user_value")
        context.add_user_data("user_number", 42)
        context.add_system_data("system_field", "system_value")
        context.add_system_data("system_list", [1, 2, 3])

        cause = ValueError("Original cause")

        error = StructuredError(
            message="Complex error for serialization",
            category=ErrorCategory.PROCESSING,
            context=context,
            cause=cause,
            recoverable=True,
            user_message="User-friendly message",
            suggestions=["Suggestion 1", "Suggestion 2"]
        )

        # Test to_dict
        error_dict = error.to_dict()

        assert error_dict["message"] == "Complex error for serialization"
        assert error_dict["category"] == "PROCESSING"
        assert error_dict["user_message"] == "User-friendly message"
        assert error_dict["recoverable"]
        assert error_dict["suggestions"] == ["Suggestion 1", "Suggestion 2"]

        # Check context serialization
        context_dict = error_dict["context"]
        assert context_dict["operation"] == "complex_operation"
        assert context_dict["component"] == "test_component"
        assert context_dict["trace_id"] == "trace-123"
        assert context_dict["user_data"]["user_field"] == "user_value"
        assert context_dict["user_data"]["user_number"] == 42
        assert context_dict["system_data"]["system_field"] == "system_value"
        assert context_dict["system_data"]["system_list"] == [1, 2, 3]

        # Check cause serialization
        assert error_dict["cause"]["type"] == "ValueError"
        assert error_dict["cause"]["message"] == "Original cause"

    def test_user_friendly_message_generation(self) -> None:
        """Test comprehensive user-friendly message generation."""
        # Test with suggestions
        error = StructuredError(
            "Technical error",
            user_message="Something went wrong",
            suggestions=["Try refreshing", "Check your connection", "Contact support"]
        )

        friendly = error.get_user_friendly_message()
        assert "Something went wrong" in friendly
        assert "• Try refreshing" in friendly
        assert "• Check your connection" in friendly
        assert "• Contact support" in friendly

        # Test without suggestions
        error = StructuredError(
            "Technical error",
            user_message="Operation failed"
        )

        friendly = error.get_user_friendly_message()
        assert friendly == "Operation failed"

        # Test with empty user message (falls back to technical message)
        error = StructuredError("Technical message only")
        friendly = error.get_user_friendly_message()
        assert friendly == "Technical message only"

    def test_error_with_traceback(self) -> None:
        """Test error with traceback capture."""
        try:
            # Create a real exception with traceback
            def inner_function() -> Never:
                msg = "Inner error"
                raise ValueError(msg)

            def outer_function() -> None:
                inner_function()

            outer_function()
        except ValueError as e:
            error = StructuredError("Wrapped error", cause=e)

            assert error.cause == e
            assert error.traceback_str is not None
            assert "inner_function" in error.traceback_str
            assert "outer_function" in error.traceback_str
            assert "ValueError: Inner error" in error.traceback_str

    def test_concurrent_error_creation(self) -> None:
        """Test concurrent error creation."""
        results = []
        errors = []

        def create_error(error_id: int) -> None:
            try:
                if error_id % 5 == 0:
                    error = StructuredError.validation_error(
                        f"Validation error {error_id}",
                        field_name=f"field_{error_id}",
                        value=error_id
                    )
                elif error_id % 5 == 1:
                    error = StructuredError.file_error(
                        f"File error {error_id}",
                        file_path=f"/path/file_{error_id}"
                    )
                elif error_id % 5 == 2:
                    error = StructuredError.network_error(
                        f"Network error {error_id}",
                        url=f"http://example.com/{error_id}"
                    )
                elif error_id % 5 == 3:
                    error = StructuredError.processing_error(
                        f"Processing error {error_id}",
                        stage=f"stage_{error_id}"
                    )
                else:
                    error = StructuredError(f"Generic error {error_id}")

                results.append((error_id, error))

            except Exception as e:
                errors.append((error_id, e))

        # Run concurrent error creation
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_error, i) for i in range(50)]
            for future in futures:
                future.result()

        assert len(errors) == 0
        assert len(results) == 50

        # Verify all errors were created correctly
        for error_id, error in results:
            assert isinstance(error, StructuredError)
            assert str(error_id) in error.message


class TestErrorBuilderV2(unittest.TestCase):
    """Test cases for ErrorBuilder with comprehensive coverage."""

    def test_builder_basic_usage(self) -> None:
        """Test basic builder usage."""
        error = ErrorBuilder("Test message").build()

        assert error.message == "Test message"
        assert error.category == ErrorCategory.UNKNOWN
        assert not error.recoverable
        assert error.context.operation == "unknown"
        assert error.context.component == "unknown"

    def test_builder_fluent_interface_comprehensive(self) -> None:
        """Test comprehensive fluent interface usage."""
        cause = RuntimeError("Root cause")

        error = (
            ErrorBuilder("Complex error message")
            .with_category(ErrorCategory.PROCESSING)
            .with_operation("data_processing")
            .with_component("image_processor")
            .with_cause(cause)
            .as_recoverable(True)
            .with_user_message("Processing failed, please try again")
            .add_suggestion("Check input format")
            .add_suggestion("Reduce file size")
            .add_suggestion("Use supported format")
            .add_user_data("input_file", "test.jpg")
            .add_user_data("file_size", 1024000)
            .add_system_data("processor_version", "2.0")
            .add_system_data("memory_used", 512)
            .build()
        )

        assert error.message == "Complex error message"
        assert error.category == ErrorCategory.PROCESSING
        assert error.context.operation == "data_processing"
        assert error.context.component == "image_processor"
        assert error.cause == cause
        assert error.recoverable
        assert error.user_message == "Processing failed, please try again"
        assert len(error.suggestions) == 3
        assert error.context.user_data["input_file"] == "test.jpg"
        assert error.context.user_data["file_size"] == 1024000
        assert error.context.system_data["processor_version"] == "2.0"
        assert error.context.system_data["memory_used"] == 512

    def test_builder_method_chaining_order(self) -> None:
        """Test that builder methods can be called in any order."""
        # Test different ordering of method calls
        error1 = (
            ErrorBuilder("Error 1")
            .with_category(ErrorCategory.NETWORK)
            .with_operation("test")
            .as_recoverable(True)
            .build()
        )

        error2 = (
            ErrorBuilder("Error 2")
            .as_recoverable(True)
            .with_operation("test")
            .with_category(ErrorCategory.NETWORK)
            .build()
        )

        # Both should produce equivalent errors
        assert error1.category == error2.category
        assert error1.context.operation == error2.context.operation
        assert error1.recoverable == error2.recoverable

    def test_builder_with_multiple_data_additions(self) -> None:
        """Test adding multiple data entries."""
        error = (
            ErrorBuilder("Test")
            .add_user_data("key1", "value1")
            .add_user_data("key2", "value2")
            .add_user_data("key3", "value3")
            .add_system_data("sys1", 100)
            .add_system_data("sys2", 200)
            .add_system_data("sys3", 300)
            .build()
        )

        assert len(error.context.user_data) == 3
        assert len(error.context.system_data) == 3
        assert error.context.user_data["key2"] == "value2"
        assert error.context.system_data["sys2"] == 200

    def test_builder_edge_cases(self) -> None:
        """Test builder edge cases."""
        # Test with empty message
        error = ErrorBuilder("").build()
        assert error.message == ""

        # Test with None values
        error = (
            ErrorBuilder("Test")
            .with_cause(None)
            .with_user_message(None)
            .build()
        )
        assert error.cause is None
        assert error.user_message is None

        # Test overwriting values
        error = (
            ErrorBuilder("Test")
            .with_category(ErrorCategory.NETWORK)
            .with_category(ErrorCategory.SYSTEM)  # Overwrite
            .with_operation("op1")
            .with_operation("op2")  # Overwrite
            .build()
        )
        assert error.category == ErrorCategory.SYSTEM
        assert error.context.operation == "op2"

    def test_builder_concurrent_usage(self) -> None:
        """Test concurrent builder usage."""
        results = []
        errors = []

        def build_error(builder_id: int) -> None:
            try:
                error = (
                    ErrorBuilder(f"Error {builder_id}")
                    .with_category(list(ErrorCategory)[builder_id % len(ErrorCategory)])
                    .with_operation(f"op_{builder_id}")
                    .with_component(f"comp_{builder_id}")
                    .as_recoverable(builder_id % 2 == 0)
                    .add_user_data("id", builder_id)
                    .add_system_data("thread", builder_id)
                    .build()
                )
                results.append((builder_id, error))

            except Exception as e:
                errors.append((builder_id, e))

        # Run concurrent builds
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(build_error, i) for i in range(50)]
            for future in futures:
                future.result()

        assert len(errors) == 0
        assert len(results) == 50

        # Verify all errors were built correctly
        for builder_id, error in results:
            assert str(builder_id) in error.message
            assert error.context.user_data["id"] == builder_id


class TestErrorIntegrationV2(unittest.TestCase):
    """Integration tests for error handling components."""

    def test_complex_error_scenario(self) -> None:
        """Test complex real-world error scenario."""
        # Simulate file processing error
        try:
            # Simulate nested operations
            def read_file(path) -> Never:
                msg = f"Cannot read {path}"
                raise FileNotFoundError(msg)

            def process_file(path):
                try:
                    return read_file(path)
                except FileNotFoundError as e:
                    # Wrap in processing error
                    msg = f"Processing failed for {path}"
                    raise RuntimeError(msg) from e

            def handle_request(file_path):
                try:
                    return process_file(file_path)
                except RuntimeError as e:
                    # Create structured error
                    context = ErrorContext(
                        operation="file_processing",
                        component="request_handler",
                        trace_id="req-123"
                    )
                    context.add_user_data("requested_file", file_path)
                    context.add_user_data("user_id", "user-456")
                    context.add_system_data("server_id", "srv-001")
                    context.add_system_data("timestamp", datetime.now().isoformat())

                    error = StructuredError(
                        message="Failed to process user file request",
                        category=ErrorCategory.PROCESSING,
                        context=context,
                        cause=e,
                        recoverable=True,
                        user_message="The requested file could not be processed",
                        suggestions=[
                            "Verify the file exists",
                            "Check file permissions",
                            "Ensure the file path is correct",
                            "Try uploading the file again"
                        ]
                    )
                    raise error

            # Trigger the error scenario
            handle_request("/nonexistent/file.txt")

        except StructuredError as error:
            # Verify the complete error structure
            assert error.message == "Failed to process user file request"
            assert error.category == ErrorCategory.PROCESSING
            assert error.recoverable
            assert error.context.trace_id == "req-123"
            assert error.context.user_data["requested_file"] == "/nonexistent/file.txt"
            assert len(error.suggestions) == 4

            # Check cause chain
            assert isinstance(error.cause, RuntimeError)
            assert isinstance(error.cause.__cause__, FileNotFoundError)

            # Test serialization
            error_dict = error.to_dict()
            assert "PROCESSING" in error_dict["category"]
            assert "trace_id" in error_dict["context"]

            # Test user-friendly message
            friendly = error.get_user_friendly_message()
            assert "file could not be processed" in friendly
            assert "Verify the file exists" in friendly

    def test_error_propagation_chain(self) -> None:
        """Test error propagation through multiple layers."""
        # Create a chain of errors
        root_cause = ConnectionError("Network timeout")

        db_error = StructuredError(
            "Database connection failed",
            category=ErrorCategory.NETWORK,
            cause=root_cause,
            context=ErrorContext("db_connect", "database"),
            recoverable=True
        )

        service_error = StructuredError(
            "User service unavailable",
            category=ErrorCategory.EXTERNAL_TOOL,
            cause=db_error,
            context=ErrorContext("get_user", "user_service"),
            recoverable=True,
            user_message="Cannot retrieve user information"
        )

        api_error = StructuredError(
            "API request failed",
            category=ErrorCategory.PROCESSING,
            cause=service_error,
            context=ErrorContext("handle_request", "api"),
            recoverable=False,
            user_message="Request could not be completed",
            suggestions=["Try again later", "Contact support"]
        )

        # Verify the error chain
        assert api_error.cause == service_error
        assert service_error.cause == db_error
        assert db_error.cause == root_cause

        # Test error chain serialization
        api_dict = api_error.to_dict()
        assert "cause" in api_dict
        assert api_dict["cause"]["message"] == "User service unavailable"

    def test_memory_efficiency_with_large_errors(self) -> None:
        """Test memory efficiency with large error data."""
        # Create error with large data
        large_string = "x" * (1024 * 1024)  # 1MB string
        large_list = list(range(10000))

        error = (
            ErrorBuilder("Large error")
            .add_user_data("large_string", large_string)
            .add_user_data("large_list", large_list)
            .add_system_data("large_dict", {str(i): i for i in range(1000)})
            .build()
        )

        # Verify data is stored
        assert len(error.context.user_data["large_string"]) == 1024 * 1024
        assert len(error.context.user_data["large_list"]) == 10000

        # Test serialization doesn't fail
        error_dict = error.to_dict()
        assert "large_string" in error_dict["context"]["user_data"]


# Compatibility tests using pytest style
class TestErrorCategoryPytest:
    """Pytest-style tests for ErrorCategory."""

    def test_categories_exist_pytest(self) -> None:
        """Test categories exist using pytest style."""
        assert hasattr(ErrorCategory, "VALIDATION")
        assert hasattr(ErrorCategory, "NETWORK")
        assert hasattr(ErrorCategory, "UNKNOWN")

    def test_category_values_pytest(self) -> None:
        """Test category values using pytest style."""
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.UNKNOWN.value == "unknown"


class TestErrorContextPytest:
    """Pytest-style tests for ErrorContext."""

    def test_context_creation_pytest(self) -> None:
        """Test context creation using pytest style."""
        context = ErrorContext(operation="test", component="test")
        assert context.operation == "test"
        assert context.component == "test"
        assert isinstance(context.timestamp, datetime)

    def test_add_data_pytest(self) -> None:
        """Test adding data using pytest style."""
        context = ErrorContext(operation="test", component="test")
        context.add_user_data("key", "value")
        context.add_system_data("sys", 123)

        assert context.user_data["key"] == "value"
        assert context.system_data["sys"] == 123


class TestStructuredErrorPytest:
    """Pytest-style tests for StructuredError."""

    def test_error_creation_pytest(self) -> None:
        """Test error creation using pytest style."""
        error = StructuredError("Test error")
        assert str(error) == "Test error"
        assert error.category == ErrorCategory.UNKNOWN
        assert error.recoverable is False

    def test_validation_error_pytest(self) -> None:
        """Test validation error using pytest style."""
        error = StructuredError.validation_error(
            "Invalid input",
            field_name="username",
            value="test@"
        )
        assert error.category == ErrorCategory.VALIDATION
        assert error.recoverable is True
        assert error.context.user_data["field"] == "username"


class TestErrorBuilderPytest:
    """Pytest-style tests for ErrorBuilder."""

    def test_builder_basic_pytest(self) -> None:
        """Test basic builder using pytest style."""
        error = ErrorBuilder("Test").build()
        assert error.message == "Test"
        assert error.category == ErrorCategory.UNKNOWN

    def test_builder_fluent_pytest(self) -> None:
        """Test fluent interface using pytest style."""
        error = (
            ErrorBuilder("Test")
            .with_category(ErrorCategory.NETWORK)
            .as_recoverable(True)
            .build()
        )
        assert error.category == ErrorCategory.NETWORK
        assert error.recoverable is True


if __name__ == "__main__":
    unittest.main()
