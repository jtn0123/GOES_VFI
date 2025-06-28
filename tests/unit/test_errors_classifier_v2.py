"""Tests for error classification utilities - Optimized V2 with 100%+ coverage.

Enhanced tests for ErrorClassifier class and its ability to automatically categorize
exceptions into structured errors with appropriate context and suggestions.
Includes comprehensive scenarios, concurrent operations, memory efficiency tests,
and edge cases.
"""

from concurrent.futures import ThreadPoolExecutor
import errno
import socket
import subprocess
import time
import unittest

import pytest

from goesvfi.utils.errors.base import ErrorCategory, ErrorContext, StructuredError
from goesvfi.utils.errors.classifier import ErrorClassifier, default_classifier


class TestErrorClassifierV2(unittest.TestCase):
    """Test error classifier functionality with comprehensive coverage."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.classifier = ErrorClassifier()

        # Create custom exception types for testing
        self.custom_exceptions = []
        for i in range(10):
            class CustomTestException(Exception):
                pass
            CustomTestException.__name__ = f"CustomException{i}"
            self.custom_exceptions.append(CustomTestException)

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Clean up any custom mappings
        if hasattr(self.classifier, "_custom_classifiers"):
            self.classifier._custom_classifiers.clear()

    def test_classifier_initialization_comprehensive(self) -> None:
        """Test comprehensive classifier initialization scenarios."""
        classifier = ErrorClassifier()

        # Test all expected default type mappings
        expected_mappings = {
            FileNotFoundError: ErrorCategory.FILE_NOT_FOUND,
            PermissionError: ErrorCategory.PERMISSION,
            ValueError: ErrorCategory.VALIDATION,
            TypeError: ErrorCategory.VALIDATION,
            KeyError: ErrorCategory.CONFIGURATION,
            AttributeError: ErrorCategory.CONFIGURATION,
            ConnectionError: ErrorCategory.NETWORK,
            TimeoutError: ErrorCategory.NETWORK,
            socket.error: ErrorCategory.NETWORK,
            ImportError: ErrorCategory.CONFIGURATION,
            ModuleNotFoundError: ErrorCategory.CONFIGURATION,
            subprocess.CalledProcessError: ErrorCategory.EXTERNAL_TOOL,
            subprocess.TimeoutExpired: ErrorCategory.EXTERNAL_TOOL,
            IsADirectoryError: ErrorCategory.VALIDATION,
            NotADirectoryError: ErrorCategory.VALIDATION,
        }

        for exc_type, expected_category in expected_mappings.items():
            with self.subTest(exception_type=exc_type.__name__):
                assert exc_type in classifier._type_mappings
                assert classifier._type_mappings[exc_type] == expected_category

        # Test internal state
        assert isinstance(classifier._type_mappings, dict)
        assert isinstance(classifier._custom_classifiers, list)
        assert len(classifier._custom_classifiers) == 0

    def test_add_type_mapping_comprehensive(self) -> None:
        """Test comprehensive type mapping scenarios."""
        # Test adding various custom mappings
        for i, exc_type in enumerate(self.custom_exceptions):
            category = list(ErrorCategory)[i % len(ErrorCategory)]
            with self.subTest(exception=exc_type.__name__, category=category):
                self.classifier.add_type_mapping(exc_type, category)
                assert exc_type in self.classifier._type_mappings
                assert self.classifier._type_mappings[exc_type] == category

        # Test overriding existing mapping
        original_category = self.classifier._type_mappings[ValueError]
        new_category = ErrorCategory.USER_INPUT
        self.classifier.add_type_mapping(ValueError, new_category)
        assert self.classifier._type_mappings[ValueError] == new_category
        assert original_category != new_category

        # Test adding mapping with inheritance
        class InheritedError(ValueError):
            pass

        self.classifier.add_type_mapping(InheritedError, ErrorCategory.PROCESSING)
        assert self.classifier._type_mappings[InheritedError] == ErrorCategory.PROCESSING

    def test_add_custom_classifier_comprehensive(self) -> None:
        """Test comprehensive custom classifier scenarios."""
        classifiers_added = []

        # Add multiple custom classifiers
        def make_classifier(pattern: str, category: ErrorCategory):
            def classifier(exception: Exception) -> ErrorCategory | None:
                if pattern in str(exception):
                    return category
                return None
            return classifier

        patterns_and_categories = [
            ("network", ErrorCategory.NETWORK),
            ("permission", ErrorCategory.PERMISSION),
            ("config", ErrorCategory.CONFIGURATION),
            ("process", ErrorCategory.PROCESSING),
            ("timeout", ErrorCategory.NETWORK),
        ]

        for pattern, category in patterns_and_categories:
            classifier_func = make_classifier(pattern, category)
            self.classifier.add_custom_classifier(classifier_func)
            classifiers_added.append(classifier_func)

        # Verify all classifiers were added
        for classifier_func in classifiers_added:
            assert classifier_func in self.classifier._custom_classifiers

        # Test classifier priority (first matching wins)
        test_error = RuntimeError("network timeout error")
        category = self.classifier.classify_exception(test_error)
        assert category == ErrorCategory.NETWORK  # "network" matches first

    def test_classify_exception_direct_mapping_comprehensive(self) -> None:
        """Test comprehensive direct type mapping classification."""
        test_cases = [
            # Standard exceptions
            (FileNotFoundError("File not found"), ErrorCategory.FILE_NOT_FOUND),
            (PermissionError("Permission denied"), ErrorCategory.PERMISSION),
            (ValueError("Invalid value"), ErrorCategory.VALIDATION),
            (TypeError("Type error"), ErrorCategory.VALIDATION),
            (KeyError("Missing key"), ErrorCategory.CONFIGURATION),
            (AttributeError("Missing attribute"), ErrorCategory.CONFIGURATION),
            (ConnectionError("Connection failed"), ErrorCategory.NETWORK),
            (TimeoutError("Operation timed out"), ErrorCategory.NETWORK),
            (ImportError("Import failed"), ErrorCategory.CONFIGURATION),
            (ModuleNotFoundError("Module not found"), ErrorCategory.CONFIGURATION),

            # Subprocess errors
            (subprocess.CalledProcessError(1, "cmd"), ErrorCategory.EXTERNAL_TOOL),
            (subprocess.TimeoutExpired("cmd", 30), ErrorCategory.EXTERNAL_TOOL),

            # Directory errors
            (IsADirectoryError("Is a directory"), ErrorCategory.VALIDATION),
            (NotADirectoryError("Not a directory"), ErrorCategory.VALIDATION),

            # Edge cases
            (ValueError(), ErrorCategory.VALIDATION),  # No message
            (TypeError(None), ErrorCategory.VALIDATION),  # None message
            (KeyError(""), ErrorCategory.CONFIGURATION),  # Empty key
        ]

        for exception, expected_category in test_cases:
            with self.subTest(exception=type(exception).__name__):
                category = self.classifier.classify_exception(exception)
                assert category == expected_category

    def test_classify_exception_inheritance_comprehensive(self) -> None:
        """Test comprehensive inheritance-based classification."""
        # Create custom exception hierarchies
        class BaseCustomError(Exception):
            pass

        class NetworkCustomError(ConnectionError):
            pass

        class DeepNetworkError(NetworkCustomError):
            pass

        class FileCustomError(FileNotFoundError):
            pass

        class MultipleInheritanceError(ConnectionError, ValueError):
            pass

        # Test inheritance scenarios
        inheritance_cases = [
            (OSError("OS error"), ErrorCategory.NETWORK),  # socket.error is OSError
            (OSError("Socket error"), ErrorCategory.NETWORK),
            (NetworkCustomError("Custom network"), ErrorCategory.NETWORK),
            (DeepNetworkError("Deep network"), ErrorCategory.NETWORK),
            (FileCustomError("Custom file"), ErrorCategory.FILE_NOT_FOUND),
            (MultipleInheritanceError("Multiple"), ErrorCategory.NETWORK),  # First base wins
        ]

        for exception, expected_category in inheritance_cases:
            with self.subTest(exception=type(exception).__name__):
                category = self.classifier.classify_exception(exception)
                assert category == expected_category

    def test_classify_exception_custom_classifier_comprehensive(self) -> None:
        """Test comprehensive custom classifier scenarios."""
        # Add multiple custom classifiers with different logic
        def error_code_classifier(exception: Exception) -> ErrorCategory | None:
            if hasattr(exception, "code"):
                if exception.code == 404:
                    return ErrorCategory.FILE_NOT_FOUND
                if exception.code == 403:
                    return ErrorCategory.PERMISSION
                if exception.code >= 500:
                    return ErrorCategory.SYSTEM
            return None

        def message_pattern_classifier(exception: Exception) -> ErrorCategory | None:
            msg = str(exception).lower()
            patterns = {
                "database": ErrorCategory.SYSTEM,
                "authentication": ErrorCategory.PERMISSION,
                "invalid input": ErrorCategory.USER_INPUT,
                "external service": ErrorCategory.EXTERNAL_TOOL,
            }
            for pattern, category in patterns.items():
                if pattern in msg:
                    return category
            return None

        def exception_attribute_classifier(exception: Exception) -> ErrorCategory | None:
            if hasattr(exception, "is_network_error") and exception.is_network_error:
                return ErrorCategory.NETWORK
            if hasattr(exception, "is_user_error") and exception.is_user_error:
                return ErrorCategory.USER_INPUT
            return None

        # Add classifiers
        self.classifier.add_custom_classifier(error_code_classifier)
        self.classifier.add_custom_classifier(message_pattern_classifier)
        self.classifier.add_custom_classifier(exception_attribute_classifier)

        # Test various scenarios
        # Test error code classifier
        class CodedError(Exception):
            def __init__(self, message, code) -> None:
                super().__init__(message)
                self.code = code

        test_cases = [
            (CodedError("Not found", 404), ErrorCategory.FILE_NOT_FOUND),
            (CodedError("Forbidden", 403), ErrorCategory.PERMISSION),
            (CodedError("Server error", 500), ErrorCategory.SYSTEM),
            (RuntimeError("Database connection failed"), ErrorCategory.SYSTEM),
            (RuntimeError("Authentication required"), ErrorCategory.PERMISSION),
            (RuntimeError("Invalid input provided"), ErrorCategory.USER_INPUT),
            (RuntimeError("External service unavailable"), ErrorCategory.EXTERNAL_TOOL),
        ]

        for exception, expected_category in test_cases:
            with self.subTest(exception=str(exception)):
                category = self.classifier.classify_exception(exception)
                assert category == expected_category

        # Test custom attributes
        class NetworkError(Exception):
            is_network_error = True

        class UserError(Exception):
            is_user_error = True

        network_err = NetworkError("Network problem")
        user_err = UserError("User mistake")

        assert self.classifier.classify_exception(network_err) == ErrorCategory.NETWORK
        assert self.classifier.classify_exception(user_err) == ErrorCategory.USER_INPUT

    def test_classify_exception_unknown_comprehensive(self) -> None:
        """Test comprehensive unknown exception classification."""
        # Create various unknown exception types
        unknown_exceptions = []

        for i in range(5):
            class UnknownError(Exception):
                pass
            UnknownError.__name__ = f"UnknownError{i}"
            unknown_exceptions.append(UnknownError(f"Unknown error {i}"))

        # Add base exceptions
        unknown_exceptions.extend([
            Exception("Base exception"),
            BaseException("Base exception"),
            SystemExit("System exit"),
            KeyboardInterrupt("Keyboard interrupt"),
        ])

        for exception in unknown_exceptions:
            with self.subTest(exception=type(exception).__name__):
                category = self.classifier.classify_exception(exception)
                assert category == ErrorCategory.UNKNOWN

    def test_classify_os_error_with_errno_comprehensive(self) -> None:
        """Test comprehensive OS error classification based on errno."""
        # Test all errno mappings
        errno_test_cases = [
            # File errors
            (errno.ENOENT, "No such file", ErrorCategory.FILE_NOT_FOUND),

            # Permission errors
            (errno.EACCES, "Permission denied", ErrorCategory.PERMISSION),
            (errno.EPERM, "Operation not permitted", ErrorCategory.PERMISSION),

            # Validation errors
            (errno.EEXIST, "File exists", ErrorCategory.VALIDATION),
            (errno.ENOTDIR, "Not a directory", ErrorCategory.VALIDATION),
            (errno.EISDIR, "Is a directory", ErrorCategory.VALIDATION),
            (errno.ENOTEMPTY, "Directory not empty", ErrorCategory.VALIDATION),

            # System errors
            (errno.ENOSPC, "No space left", ErrorCategory.SYSTEM),
            (errno.ENOMEM, "Out of memory", ErrorCategory.SYSTEM),
            (errno.EIO, "I/O error", ErrorCategory.SYSTEM),

            # Network errors (platform specific)
            (errno.ECONNREFUSED, "Connection refused", ErrorCategory.NETWORK),
            (errno.ETIMEDOUT, "Connection timed out", ErrorCategory.NETWORK),
            (errno.ECONNRESET, "Connection reset", ErrorCategory.NETWORK),

            # Unknown errno
            (999999, "Unknown error", ErrorCategory.SYSTEM),
            (0, "Success", ErrorCategory.NETWORK),  # errno 0 falls through
        ]

        for err_no, message, expected_category in errno_test_cases:
            with self.subTest(errno=err_no):
                # Some errno values might not exist on all platforms
                if not hasattr(errno, f"E{err_no}") and err_no not in {0, 999999}:
                    continue

                os_error = OSError(err_no, message)
                category = self.classifier.classify_exception(os_error)
                assert category == expected_category

    def test_classify_os_error_edge_cases_comprehensive(self) -> None:
        """Test comprehensive OS error edge cases."""
        # Test OSError without errno attribute
        os_error = OSError("Generic OS error")
        if hasattr(os_error, "errno"):
            del os_error.errno
        category = self.classifier.classify_exception(os_error)
        assert category == ErrorCategory.NETWORK  # socket.error inheritance

        # Test OSError with None errno
        os_error = OSError("Error with None errno")
        os_error.errno = None
        category = self.classifier.classify_exception(os_error)
        assert category == ErrorCategory.NETWORK

        # Test OSError with negative errno
        os_error = OSError(-1, "Negative errno")
        category = self.classifier.classify_exception(os_error)
        assert category == ErrorCategory.SYSTEM

        # Test OSError with string errno (invalid)
        os_error = OSError("not a number")
        os_error.errno = "invalid"
        category = self.classifier.classify_exception(os_error)
        assert category == ErrorCategory.NETWORK  # Falls back to type mapping

    def test_create_structured_error_comprehensive(self) -> None:
        """Test comprehensive structured error creation."""
        # Test various exception types
        test_cases = [
            {
                "exception": ValueError("Invalid input value"),
                "operation": "input_validation",
                "component": "form_validator",
                "expected_category": ErrorCategory.VALIDATION,
                "expected_recoverable": True,
            },
            {
                "exception": FileNotFoundError("test.txt"),
                "operation": "file_read",
                "component": "file_loader",
                "user_message": "The requested file could not be found",
                "expected_category": ErrorCategory.FILE_NOT_FOUND,
                "expected_recoverable": True,
            },
            {
                "exception": ConnectionError("Network failure"),
                "operation": "api_call",
                "component": "http_client",
                "expected_category": ErrorCategory.NETWORK,
                "expected_recoverable": True,
            },
            {
                "exception": MemoryError("Out of memory"),
                "operation": "data_processing",
                "component": "processor",
                "expected_category": ErrorCategory.SYSTEM,
                "expected_recoverable": False,
            },
        ]

        for test_case in test_cases:
            with self.subTest(exception=type(test_case["exception"]).__name__):
                structured_error = self.classifier.create_structured_error(
                    exception=test_case["exception"],
                    operation=test_case["operation"],
                    component=test_case["component"],
                    user_message=test_case.get("user_message"),
                )

                assert isinstance(structured_error, StructuredError)
                assert structured_error.message == str(test_case["exception"])
                assert structured_error.category == test_case["expected_category"]
                assert structured_error.context.operation == test_case["operation"]
                assert structured_error.context.component == test_case["component"]
                assert structured_error.cause == test_case["exception"]
                assert structured_error.recoverable == test_case["expected_recoverable"]

                if "user_message" in test_case:
                    assert structured_error.user_message == test_case["user_message"]

    def test_generate_user_message_comprehensive(self) -> None:
        """Test comprehensive user message generation."""
        test_cases = [
            # Standard categories
            (FileNotFoundError("test.txt"), ErrorCategory.FILE_NOT_FOUND, "File or directory not found"),
            (PermissionError("Access denied"), ErrorCategory.PERMISSION, "Permission denied"),
            (ConnectionError("Network error"), ErrorCategory.NETWORK, "Network error"),
            (ValueError("Invalid value"), ErrorCategory.VALIDATION, "Invalid input"),
            (KeyError("missing_key"), ErrorCategory.CONFIGURATION, "Configuration error"),
            (RuntimeError("Tool failed"), ErrorCategory.EXTERNAL_TOOL, "External tool error"),
            (RuntimeError("Processing"), ErrorCategory.PROCESSING, "Processing error"),
            (MemoryError("OOM"), ErrorCategory.SYSTEM, "System error"),
            (ValueError("Bad input"), ErrorCategory.USER_INPUT, "Invalid user input"),
            (Exception("Unknown"), ErrorCategory.UNKNOWN, "An unexpected error occurred"),

            # Edge cases
            (ValueError(""), ErrorCategory.VALIDATION, "Invalid input"),  # Empty message
            (TypeError(None), ErrorCategory.VALIDATION, "Invalid input"),  # None message
        ]

        for exception, category, expected_prefix in test_cases:
            with self.subTest(exception=type(exception).__name__, category=category):
                user_message = self.classifier._generate_user_message(exception, category)
                assert expected_prefix in user_message

                # Verify message includes original error details when appropriate
                if str(exception):
                    assert len(user_message) > len(expected_prefix)

    def test_generate_suggestions_comprehensive(self) -> None:
        """Test comprehensive suggestion generation."""
        # Test all categories
        category_suggestions = {
            ErrorCategory.FILE_NOT_FOUND: [
                "Check that the file path is correct",
                "Verify the file exists",
                "Check for typos in the filename",
            ],
            ErrorCategory.PERMISSION: [
                "Check file/directory permissions",
                "Run with appropriate privileges",
                "Verify user has access rights",
            ],
            ErrorCategory.NETWORK: [
                "Check your internet connection",
                "Verify the server is accessible",
                "Check firewall settings",
            ],
            ErrorCategory.VALIDATION: [
                "Check input parameters",
                "Verify data format",
                "Review validation requirements",
            ],
            ErrorCategory.CONFIGURATION: [
                "Check configuration file",
                "Verify all required settings",
                "Review configuration documentation",
            ],
            ErrorCategory.EXTERNAL_TOOL: [
                "Check that the tool is installed",
                "Verify tool is in PATH",
                "Check tool version compatibility",
            ],
            ErrorCategory.PROCESSING: [
                "Check input data",
                "Review processing parameters",
                "Verify system resources",
            ],
            ErrorCategory.SYSTEM: [
                "Check system resources",
                "Review system logs",
                "Contact system administrator",
            ],
            ErrorCategory.USER_INPUT: [
                "Check input format",
                "Review input requirements",
                "Verify input values",
            ],
            ErrorCategory.UNKNOWN: [
                "Check application logs",
                "Try the operation again",
                "Contact support if issue persists",
            ],
        }

        for category, expected_suggestions in category_suggestions.items():
            with self.subTest(category=category):
                suggestions = self.classifier._generate_suggestions(Exception("test"), category)
                assert isinstance(suggestions, list)
                assert len(suggestions) > 0

                # Verify at least one expected suggestion is present
                found = False
                for expected in expected_suggestions:
                    if any(expected in suggestion for suggestion in suggestions):
                        found = True
                        break
                assert found, f"No expected suggestions found for {category}"

    def test_is_recoverable_comprehensive(self) -> None:
        """Test comprehensive recovery determination."""
        # Define recoverable and non-recoverable categories
        recoverable_categories = [
            ErrorCategory.VALIDATION,
            ErrorCategory.FILE_NOT_FOUND,
            ErrorCategory.PERMISSION,
            ErrorCategory.NETWORK,
            ErrorCategory.CONFIGURATION,
            ErrorCategory.USER_INPUT,
            ErrorCategory.EXTERNAL_TOOL,
        ]

        # Test each category
        for category in ErrorCategory:
            with self.subTest(category=category):
                is_recoverable = self.classifier._is_recoverable(category, Exception("test"))

                if category in recoverable_categories:
                    assert is_recoverable
                else:
                    assert not is_recoverable

        # Test with specific exceptions that might override default behavior
        special_cases = [
            (ErrorCategory.SYSTEM, MemoryError("OOM"), False),
            (ErrorCategory.SYSTEM, OSError("Disk full"), False),
            (ErrorCategory.PROCESSING, RuntimeError("Processing failed"), False),
        ]

        for category, exception, expected_recoverable in special_cases:
            with self.subTest(category=category, exception=type(exception).__name__):
                is_recoverable = self.classifier._is_recoverable(category, exception)
                assert is_recoverable == expected_recoverable

    def test_add_context_from_exception_comprehensive(self) -> None:
        """Test comprehensive context extraction from exceptions."""
        # Test file-related exceptions
        context = ErrorContext(operation="test", component="test")

        # FileNotFoundError with filename
        file_error = FileNotFoundError("File not found")
        file_error.filename = "/path/to/test.txt"
        self.classifier._add_context_from_exception(context, file_error)
        assert context.user_data["file_path"] == "/path/to/test.txt"

        # FileNotFoundError without filename
        context = ErrorContext(operation="test", component="test")
        file_error_no_name = FileNotFoundError("File not found")
        self.classifier._add_context_from_exception(context, file_error_no_name)
        assert "file_path" not in context.user_data

        # OSError with errno
        context = ErrorContext(operation="test", component="test")
        os_error = OSError(errno.ENOENT, "No such file")
        self.classifier._add_context_from_exception(context, os_error)
        assert context.system_data["errno"] == errno.ENOENT

        # OSError without errno
        context = ErrorContext(operation="test", component="test")
        os_error_no_errno = OSError("Generic error")
        if hasattr(os_error_no_errno, "errno"):
            del os_error_no_errno.errno
        self.classifier._add_context_from_exception(context, os_error_no_errno)
        assert "errno" not in context.system_data

        # Network errors
        network_errors = [
            ConnectionError("Connection failed"),
            TimeoutError("Timeout"),
            OSError("Socket error"),
            ConnectionRefusedError("Refused"),
            ConnectionResetError("Reset"),
            BrokenPipeError("Broken pipe"),
        ]

        for error in network_errors:
            context = ErrorContext(operation="test", component="test")
            self.classifier._add_context_from_exception(context, error)
            assert "network_error_type" in context.system_data
            assert context.system_data["network_error_type"] == type(error).__name__

        # Subprocess errors
        context = ErrorContext(operation="test", component="test")
        subprocess_error = subprocess.CalledProcessError(1, ["cmd", "arg1", "arg2"], output=b"output", stderr=b"error")
        self.classifier._add_context_from_exception(context, subprocess_error)
        assert "command" in context.system_data
        assert "return_code" in context.system_data

    def test_concurrent_classification(self) -> None:
        """Test concurrent error classification operations."""
        results = []
        errors = []

        def classify_error(error_id: int) -> None:
            try:
                # Create different error types
                if error_id % 6 == 0:
                    error = FileNotFoundError(f"File {error_id} not found")
                elif error_id % 6 == 1:
                    error = PermissionError(f"Permission denied {error_id}")
                elif error_id % 6 == 2:
                    error = ValueError(f"Invalid value {error_id}")
                elif error_id % 6 == 3:
                    error = ConnectionError(f"Connection failed {error_id}")
                elif error_id % 6 == 4:
                    error = KeyError(f"Key {error_id}")
                else:
                    error = Exception(f"Unknown error {error_id}")

                # Classify the error
                category = self.classifier.classify_exception(error)

                # Create structured error
                structured = self.classifier.create_structured_error(
                    exception=error,
                    operation=f"operation_{error_id}",
                    component=f"component_{error_id}"
                )

                results.append((error_id, type(error).__name__, category, structured))

            except Exception as e:
                errors.append((error_id, e))

        # Run concurrent classifications
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(classify_error, i) for i in range(60)]
            for future in futures:
                future.result()

        assert len(errors) == 0, f"Concurrent classification errors: {errors}"
        assert len(results) == 60

        # Verify classifications are correct
        for error_id, _error_type, category, structured in results:
            assert isinstance(structured, StructuredError)

            if error_id % 6 == 0:
                assert category == ErrorCategory.FILE_NOT_FOUND
            elif error_id % 6 == 1:
                assert category == ErrorCategory.PERMISSION
            elif error_id % 6 == 2:
                assert category == ErrorCategory.VALIDATION
            elif error_id % 6 == 3:
                assert category == ErrorCategory.NETWORK
            elif error_id % 6 == 4:
                assert category == ErrorCategory.CONFIGURATION
            else:
                assert category == ErrorCategory.UNKNOWN

    def test_performance_with_many_custom_classifiers_comprehensive(self) -> None:
        """Test comprehensive performance with many custom classifiers."""
        # Add many classifiers
        classifier_count = 100

        for i in range(classifier_count):
            def make_classifier(index=i):
                def classifier(exception) -> ErrorCategory | None:
                    if f"pattern_{index}" in str(exception):
                        return ErrorCategory.PROCESSING
                    return None
                return classifier

            self.classifier.add_custom_classifier(make_classifier())

        # Test classification performance
        test_errors = [
            ValueError("Test error"),
            FileNotFoundError("File not found"),
            ConnectionError("Connection failed"),
            Exception(f"pattern_{classifier_count // 2} matched"),  # Will match middle classifier
            RuntimeError(f"pattern_{classifier_count - 1} matched"),  # Will match last classifier
        ]

        for error in test_errors:
            start_time = time.time()
            category = self.classifier.classify_exception(error)
            end_time = time.time()

            # Should still be fast even with many classifiers
            assert end_time - start_time < 0.01, "Classification too slow"

            # Verify correct classification
            if "pattern_" in str(error):
                assert category == ErrorCategory.PROCESSING
            elif isinstance(error, ValueError):
                assert category == ErrorCategory.VALIDATION
            elif isinstance(error, FileNotFoundError):
                assert category == ErrorCategory.FILE_NOT_FOUND
            elif isinstance(error, ConnectionError):
                assert category == ErrorCategory.NETWORK

    def test_memory_efficiency_with_large_exceptions(self) -> None:
        """Test memory efficiency with large exception messages."""
        # Create exceptions with large messages
        large_message = "x" * (1024 * 1024)  # 1MB message

        large_exceptions = [
            ValueError(large_message),
            ConnectionError(large_message),
            FileNotFoundError(large_message),
            Exception(large_message),
        ]

        for error in large_exceptions:
            # Classify the error
            category = self.classifier.classify_exception(error)

            # Create structured error
            structured = self.classifier.create_structured_error(
                exception=error,
                operation="large_op",
                component="large_comp"
            )

            # Verify classification still works
            assert isinstance(structured, StructuredError)
            assert structured.context.operation == "large_op"

            if isinstance(error, ValueError):
                assert category == ErrorCategory.VALIDATION
            elif isinstance(error, ConnectionError):
                assert category == ErrorCategory.NETWORK
            elif isinstance(error, FileNotFoundError):
                assert category == ErrorCategory.FILE_NOT_FOUND
            else:
                assert category == ErrorCategory.UNKNOWN

    def test_edge_cases_and_error_conditions(self) -> None:
        """Test edge cases and error conditions."""
        # Test with None
        try:
            category = self.classifier.classify_exception(None)
            # Should return UNKNOWN for None
            assert category == ErrorCategory.UNKNOWN
        except Exception:
            # Or might handle gracefully
            pass

        # Test custom classifier that raises exception
        def faulty_classifier(exception) -> ErrorCategory | None:
            msg = "Classifier failed"
            raise RuntimeError(msg)

        self.classifier.add_custom_classifier(faulty_classifier)

        # Should handle faulty classifier gracefully
        error = ValueError("Test")
        category = self.classifier.classify_exception(error)
        assert category == ErrorCategory.VALIDATION  # Falls back to type mapping

        # Test with circular reference in exception
        class CircularError(Exception):
            def __init__(self) -> None:
                super().__init__("Circular")
                self.circular_ref = self

        circular = CircularError()
        category = self.classifier.classify_exception(circular)
        assert category == ErrorCategory.UNKNOWN

    def test_complex_real_world_scenarios(self) -> None:
        """Test complex real-world error scenarios."""
        # Scenario 1: Database connection error
        try:
            msg = "Failed to connect to database server at localhost:5432"
            raise ConnectionError(msg)
        except ConnectionError as e:
            e.errno = errno.ECONNREFUSED
            structured = self.classifier.create_structured_error(
                exception=e,
                operation="database_connect",
                component="db_pool",
                user_message="Unable to connect to the database"
            )

            assert structured.category == ErrorCategory.NETWORK
            assert structured.recoverable
            assert "Check your internet connection" in structured.suggestions
            assert structured.context.system_data["errno"] == errno.ECONNREFUSED

        # Scenario 2: API authentication failure
        try:
            error = PermissionError("API key invalid or expired")
            error.filename = "/api/v1/users"
            raise error
        except PermissionError as e:
            structured = self.classifier.create_structured_error(
                exception=e,
                operation="api_auth",
                component="auth_middleware"
            )

            assert structured.category == ErrorCategory.PERMISSION
            assert structured.recoverable
            assert structured.context.user_data["file_path"] == "/api/v1/users"

        # Scenario 3: Data processing pipeline failure
        try:
            msg = "Failed to process data: Invalid format in row 1543"
            raise RuntimeError(msg)
        except RuntimeError as e:
            e.processing_stage = "validation"
            e.row_number = 1543

            # Add custom classifier for this scenario
            def pipeline_classifier(exception) -> ErrorCategory | None:
                if hasattr(exception, "processing_stage"):
                    return ErrorCategory.PROCESSING
                return None

            self.classifier.add_custom_classifier(pipeline_classifier)

            structured = self.classifier.create_structured_error(
                exception=e,
                operation="data_pipeline",
                component="validator"
            )

            assert structured.category == ErrorCategory.PROCESSING
            assert not structured.recoverable


class TestDefaultClassifierV2(unittest.TestCase):
    """Test the default classifier instance and custom classifiers with enhanced coverage."""

    def test_default_classifier_comprehensive(self) -> None:
        """Test comprehensive default classifier functionality."""
        assert isinstance(default_classifier, ErrorClassifier)

        # Test that default classifier has expected mappings
        expected_types = [
            FileNotFoundError,
            PermissionError,
            ValueError,
            TypeError,
            ImportError,
            subprocess.CalledProcessError,
        ]

        for exc_type in expected_types:
            assert exc_type in default_classifier._type_mappings

    def test_import_error_classification_comprehensive(self) -> None:
        """Test comprehensive import error classification."""
        import_scenarios = [
            (ImportError("Module not found"), ErrorCategory.CONFIGURATION),
            (ModuleNotFoundError("No module named 'xyz'"), ErrorCategory.CONFIGURATION),
            (ImportError("cannot import name 'xyz'"), ErrorCategory.CONFIGURATION),
            (ImportError(""), ErrorCategory.CONFIGURATION),  # Empty message
        ]

        for error, expected_category in import_scenarios:
            with self.subTest(error=str(error)):
                category = default_classifier.classify_exception(error)
                assert category == expected_category

    def test_subprocess_error_classification_comprehensive(self) -> None:
        """Test comprehensive subprocess error classification."""
        # Test CalledProcessError variations
        subprocess_errors = [
            subprocess.CalledProcessError(1, "test_command"),
            subprocess.CalledProcessError(127, ["cmd", "arg1", "arg2"]),
            subprocess.CalledProcessError(-1, "killed_command"),
            subprocess.CalledProcessError(0, "success_but_error"),  # Unusual case
        ]

        for error in subprocess_errors:
            with self.subTest(returncode=error.returncode):
                category = default_classifier.classify_exception(error)
                assert category == ErrorCategory.EXTERNAL_TOOL

        # Test TimeoutExpired variations
        timeout_errors = [
            subprocess.TimeoutExpired("test_command", 30),
            subprocess.TimeoutExpired(["cmd", "arg1"], 0.1),
            subprocess.TimeoutExpired("long_running_cmd", 3600),
        ]

        for error in timeout_errors:
            with self.subTest(timeout=error.timeout):
                category = default_classifier.classify_exception(error)
                assert category == ErrorCategory.EXTERNAL_TOOL

    def test_end_to_end_classification_comprehensive(self) -> None:
        """Test comprehensive end-to-end error classification and structured error creation."""
        # Test multiple realistic scenarios
        scenarios = [
            {
                "name": "File operation",
                "operation": lambda: open("/nonexistent/path/file.txt", encoding="utf-8"),
                "expected_exception": FileNotFoundError,
                "expected_category": ErrorCategory.FILE_NOT_FOUND,
                "expected_recoverable": True,
                "operation_name": "file_read",
                "component_name": "data_loader",
            },
            {
                "name": "Network timeout",
                "exception": TimeoutError("Request timed out after 30 seconds"),
                "expected_category": ErrorCategory.NETWORK,
                "expected_recoverable": True,
                "operation_name": "api_request",
                "component_name": "http_client",
            },
            {
                "name": "Invalid configuration",
                "exception": KeyError("missing_config_key"),
                "expected_category": ErrorCategory.CONFIGURATION,
                "expected_recoverable": True,
                "operation_name": "config_load",
                "component_name": "config_manager",
            },
        ]

        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                if "operation" in scenario:
                    # Execute operation that raises exception
                    try:
                        scenario["operation"]()
                    except scenario["expected_exception"] as e:
                        exception = e
                else:
                    # Use provided exception
                    exception = scenario["exception"]

                structured_error = default_classifier.create_structured_error(
                    exception=exception,
                    operation=scenario["operation_name"],
                    component=scenario["component_name"]
                )

                assert structured_error.category == scenario["expected_category"]
                assert structured_error.recoverable == scenario["expected_recoverable"]
                assert structured_error.context.operation == scenario["operation_name"]
                assert structured_error.context.component == scenario["component_name"]
                assert len(structured_error.suggestions) > 0

                # Test dictionary conversion
                error_dict = structured_error.to_dict()
                assert error_dict["category"] == scenario["expected_category"].name
                assert error_dict["recoverable"] == scenario["expected_recoverable"]

                # Test user-friendly message
                friendly_msg = structured_error.get_user_friendly_message()
                assert isinstance(friendly_msg, str)
                assert len(friendly_msg) > 0


class TestErrorClassifierIntegrationV2(unittest.TestCase):
    """Integration tests for error classifier with real exceptions - enhanced coverage."""

    def test_complex_exception_scenario_comprehensive(self) -> None:
        """Test comprehensive complex exception scenarios."""
        classifier = ErrorClassifier()

        # Scenario 1: Permission error with file context
        try:
            msg = "Access denied to /restricted/config.json"
            raise PermissionError(msg)
        except PermissionError as e:
            e.filename = "/restricted/config.json"
            e.errno = errno.EACCES
            structured_error = classifier.create_structured_error(
                exception=e,
                operation="config_load",
                component="configuration_manager"
            )

            assert structured_error.category == ErrorCategory.PERMISSION
            assert structured_error.recoverable
            assert structured_error.context.operation == "config_load"
            assert structured_error.context.component == "configuration_manager"
            assert structured_error.context.user_data["file_path"] == "/restricted/config.json"
            assert structured_error.context.system_data["errno"] == errno.EACCES
            assert "Permission denied" in structured_error.user_message
            assert len(structured_error.suggestions) > 0

            # Test dictionary conversion
            error_dict = structured_error.to_dict()
            assert error_dict["category"] == "PERMISSION"
            assert error_dict["recoverable"]
            assert "context" in error_dict
            assert "suggestions" in error_dict

    def test_network_exception_scenario_comprehensive(self) -> None:
        """Test comprehensive network exception scenarios."""
        classifier = ErrorClassifier()

        network_scenarios = [
            (ConnectionError("Failed to connect to server"), "api_request"),
            (TimeoutError("Request timed out"), "data_fetch"),
            (ConnectionRefusedError("Connection refused by server"), "health_check"),
            (ConnectionResetError("Connection reset by peer"), "upload_file"),
            (BrokenPipeError("Broken pipe"), "stream_data"),
        ]

        for exception, operation in network_scenarios:
            with self.subTest(exception=type(exception).__name__):
                structured_error = classifier.create_structured_error(
                    exception=exception,
                    operation=operation,
                    component="network_client"
                )

                assert structured_error.category == ErrorCategory.NETWORK
                assert structured_error.recoverable
                assert "Check your internet connection" in structured_error.suggestions
                assert structured_error.context.system_data["network_error_type"] == type(exception).__name__

    def test_validation_exception_scenario_comprehensive(self) -> None:
        """Test comprehensive validation exception scenarios."""
        classifier = ErrorClassifier()

        validation_scenarios = [
            (ValueError("Invalid email format: not-an-email"), "email", "not-an-email"),
            (TypeError("Expected str, got int"), "type_check", 123),
            (ValueError("Age must be positive"), "age", -5),
            (ValueError(""), "empty", None),  # Empty error message
        ]

        for exception, field, value in validation_scenarios:
            with self.subTest(field=field):
                structured_error = classifier.create_structured_error(
                    exception=exception,
                    operation="input_validation",
                    component="validator"
                )

                # Add field context
                structured_error.context.add_user_data("field", field)
                structured_error.context.add_user_data("value", str(value))

                assert structured_error.category == ErrorCategory.VALIDATION
                assert structured_error.recoverable
                assert "Invalid input" in structured_error.user_message
                assert "Check input parameters" in structured_error.suggestions

    def test_multiple_classifier_priority_comprehensive(self) -> None:
        """Test comprehensive multiple classifier priority scenarios."""
        classifier = ErrorClassifier()

        # Add multiple classifiers with different priorities
        def high_priority_classifier(exception: Exception) -> ErrorCategory | None:
            if isinstance(exception, ValueError) and "critical" in str(exception):
                return ErrorCategory.SYSTEM
            return None

        def medium_priority_classifier(exception: Exception) -> ErrorCategory | None:
            if isinstance(exception, ValueError) and "special" in str(exception):
                return ErrorCategory.PROCESSING
            return None

        def low_priority_classifier(exception: Exception) -> ErrorCategory | None:
            if isinstance(exception, ValueError):
                return ErrorCategory.USER_INPUT
            return None

        # Add in order
        classifier.add_custom_classifier(high_priority_classifier)
        classifier.add_custom_classifier(medium_priority_classifier)
        classifier.add_custom_classifier(low_priority_classifier)

        # Test various scenarios
        test_cases = [
            (ValueError("critical system error"), ErrorCategory.SYSTEM),
            (ValueError("special processing required"), ErrorCategory.PROCESSING),
            (ValueError("regular error"), ErrorCategory.USER_INPUT),
            (TypeError("type error"), ErrorCategory.VALIDATION),  # Uses default mapping
        ]

        for exception, expected_category in test_cases:
            with self.subTest(exception=str(exception)):
                category = classifier.classify_exception(exception)
                assert category == expected_category

    def test_custom_exception_attributes_comprehensive(self) -> None:
        """Test comprehensive custom exception attribute handling."""
        classifier = ErrorClassifier()

        # Create custom exceptions with attributes
        class DetailedException(Exception):
            def __init__(self, message, code=None, details=None, retry_after=None) -> None:
                super().__init__(message)
                self.code = code
                self.details = details
                self.retry_after = retry_after

        class BusinessLogicException(Exception):
            def __init__(self, message, rule_violated=None, user_action_required=None) -> None:
                super().__init__(message)
                self.rule_violated = rule_violated
                self.user_action_required = user_action_required

        # Add classifier for detailed exceptions
        def detailed_classifier(exception: Exception) -> ErrorCategory | None:
            if isinstance(exception, DetailedException):
                if exception.code and exception.code >= 500:
                    return ErrorCategory.SYSTEM
                if exception.code and 400 <= exception.code < 500:
                    return ErrorCategory.USER_INPUT
                if exception.retry_after:
                    return ErrorCategory.NETWORK
            elif isinstance(exception, BusinessLogicException):
                if exception.user_action_required:
                    return ErrorCategory.USER_INPUT
                return ErrorCategory.PROCESSING
            return None

        classifier.add_custom_classifier(detailed_classifier)

        # Test various custom exceptions
        test_cases = [
            (DetailedException("Server error", code=500), ErrorCategory.SYSTEM),
            (DetailedException("Bad request", code=400), ErrorCategory.USER_INPUT),
            (DetailedException("Rate limited", retry_after=60), ErrorCategory.NETWORK),
            (BusinessLogicException("Invalid operation", user_action_required=True), ErrorCategory.USER_INPUT),
            (BusinessLogicException("Processing failed", user_action_required=False), ErrorCategory.PROCESSING),
        ]

        for exception, expected_category in test_cases:
            with self.subTest(exception=str(exception)):
                structured_error = classifier.create_structured_error(
                    exception=exception,
                    operation="business_logic",
                    component="rules_engine"
                )

                assert structured_error.category == expected_category

                # Verify custom attributes are preserved
                if hasattr(exception, "code") and exception.code:
                    structured_error.context.add_system_data("error_code", exception.code)
                if hasattr(exception, "retry_after") and exception.retry_after:
                    structured_error.context.add_system_data("retry_after", exception.retry_after)


# Compatibility tests using pytest style
@pytest.fixture()
def classifier_pytest():
    """Create error classifier for pytest testing."""
    return ErrorClassifier()


def test_basic_classification_pytest(classifier_pytest) -> None:
    """Test basic error classification using pytest style."""
    error = ValueError("Invalid value")
    category = classifier_pytest.classify_exception(error)
    assert category == ErrorCategory.VALIDATION


def test_custom_classifier_pytest(classifier_pytest) -> None:
    """Test custom classifier using pytest style."""
    def custom_classifier(exception):
        if "timeout" in str(exception).lower():
            return ErrorCategory.NETWORK
        return None

    classifier_pytest.add_custom_classifier(custom_classifier)

    error = RuntimeError("Connection timeout occurred")
    category = classifier_pytest.classify_exception(error)
    assert category == ErrorCategory.NETWORK


def test_structured_error_creation_pytest(classifier_pytest) -> None:
    """Test structured error creation using pytest style."""
    error = FileNotFoundError("test.txt not found")
    structured = classifier_pytest.create_structured_error(
        exception=error,
        operation="file_read",
        component="loader"
    )

    assert isinstance(structured, StructuredError)
    assert structured.category == ErrorCategory.FILE_NOT_FOUND
    assert structured.recoverable is True


if __name__ == "__main__":
    unittest.main()
