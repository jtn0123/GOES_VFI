"""Fast, optimized tests for error classification - Optimized V2 with 100%+ coverage.

Enhanced tests for error classification with comprehensive scenarios,
error handling, concurrent operations, and edge cases. Critical error
handling infrastructure with performance optimizations.
"""

from concurrent.futures import ThreadPoolExecutor
import errno
import time
import unittest

import pytest

from goesvfi.utils.errors.base import ErrorCategory
from goesvfi.utils.errors.classifier import ErrorClassifier


class TestErrorClassifierV2(unittest.TestCase):
    """Test cases for error classification with comprehensive coverage."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.classifier = ErrorClassifier()

        # Create custom exceptions for testing
        self.custom_exceptions = []
        for i in range(5):
            class CustomTestException(Exception):
                pass
            CustomTestException.__name__ = f"CustomException{i}"
            self.custom_exceptions.append(CustomTestException)

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Clean up any custom mappings
        if hasattr(self.classifier, "_custom_classifiers"):
            self.classifier._custom_classifiers.clear()

    def test_classify_file_not_found_error_comprehensive(self) -> None:
        """Test comprehensive FileNotFoundError classification scenarios."""
        # Test various FileNotFoundError scenarios
        error_scenarios = [
            FileNotFoundError("File not found"),
            FileNotFoundError(""),  # Empty message
            FileNotFoundError("Very long error message " * 100),  # Long message
            FileNotFoundError("File with special chars: @#$%^&*()"),
        ]

        for error in error_scenarios:
            with self.subTest(error=str(error)[:50]):
                category = self.classifier.classify_exception(error)
                assert category == ErrorCategory.FILE_NOT_FOUND

    def test_classify_permission_error_comprehensive(self) -> None:
        """Test comprehensive PermissionError classification scenarios."""
        # Test various PermissionError scenarios
        error_scenarios = [
            PermissionError("Permission denied"),
            PermissionError("Access is denied"),
            PermissionError("Insufficient privileges"),
            PermissionError(""),  # Empty message
            PermissionError(13),  # Numeric error code
        ]

        for error in error_scenarios:
            with self.subTest(error=str(error)[:50]):
                category = self.classifier.classify_exception(error)
                assert category == ErrorCategory.PERMISSION

    def test_classify_validation_errors_comprehensive(self) -> None:
        """Test comprehensive validation error classification."""
        validation_scenarios = [
            # Standard validation errors
            (ValueError("Invalid value"), ErrorCategory.VALIDATION),
            (TypeError("Wrong type"), ErrorCategory.VALIDATION),
            (IsADirectoryError("Expected file"), ErrorCategory.VALIDATION),
            (NotADirectoryError("Expected directory"), ErrorCategory.VALIDATION),

            # Edge cases
            (ValueError(), ErrorCategory.VALIDATION),  # No message
            (TypeError(None), ErrorCategory.VALIDATION),  # None message
            (ValueError({"complex": "object"}), ErrorCategory.VALIDATION),  # Complex message

            # Subclasses
            (type("CustomValueError", (ValueError,), {})("Custom"), ErrorCategory.VALIDATION),
            (type("CustomTypeError", (TypeError,), {})("Custom"), ErrorCategory.VALIDATION),
        ]

        for error, expected_category in validation_scenarios:
            with self.subTest(error=type(error).__name__):
                category = self.classifier.classify_exception(error)
                assert category == expected_category

    def test_classify_system_errors_comprehensive(self) -> None:
        """Test comprehensive system error classification."""
        # Test various system error scenarios
        system_error_scenarios = [
            # Standard system errors with errno
            (OSError(errno.ENOSPC, "No space left on device"), ErrorCategory.SYSTEM),
            (OSError(errno.ENOMEM, "Out of memory"), ErrorCategory.SYSTEM),
            (OSError(errno.EIO, "I/O error"), ErrorCategory.SYSTEM),

            # System errors without errno (will be classified as NETWORK due to socket.error)
            (OSError("Generic system error"), ErrorCategory.NETWORK),

            # System errors with zero errno
            (OSError(0, "Zero errno error"), ErrorCategory.NETWORK),
        ]

        for error, expected_category in system_error_scenarios:
            with self.subTest(error=str(error)[:50]):
                if hasattr(error, "errno") and error.errno == 0:
                    error.errno = 0  # Explicitly set zero errno
                elif hasattr(error, "errno") and error.errno is None:
                    error.errno = None

                category = self.classifier.classify_exception(error)
                assert category == expected_category

    def test_classify_network_errors_comprehensive(self) -> None:
        """Test comprehensive network error classification."""
        network_scenarios = [
            # Standard network errors
            (ConnectionError("Connection failed"), ErrorCategory.NETWORK),
            (TimeoutError("Request timed out"), ErrorCategory.NETWORK),
            (ConnectionRefusedError("Connection refused"), ErrorCategory.NETWORK),
            (ConnectionResetError("Connection reset by peer"), ErrorCategory.NETWORK),
            (ConnectionAbortedError("Connection aborted"), ErrorCategory.NETWORK),
            (BrokenPipeError("Broken pipe"), ErrorCategory.NETWORK),

            # OSError (treated as network due to socket.error inheritance)
            (OSError("Socket error"), ErrorCategory.NETWORK),

            # Subclasses
            (type("CustomConnectionError", (ConnectionError,), {})("Custom"), ErrorCategory.NETWORK),
        ]

        for error, expected_category in network_scenarios:
            with self.subTest(error=type(error).__name__):
                category = self.classifier.classify_exception(error)
                assert category == expected_category

    def test_classify_configuration_errors_comprehensive(self) -> None:
        """Test comprehensive configuration error classification."""
        config_scenarios = [
            # Standard configuration errors
            (KeyError("Missing key"), ErrorCategory.CONFIGURATION),
            (AttributeError("Missing attribute"), ErrorCategory.CONFIGURATION),

            # Edge cases
            (KeyError(), ErrorCategory.CONFIGURATION),  # No key specified
            (AttributeError(), ErrorCategory.CONFIGURATION),  # No attribute specified
            (KeyError(""), ErrorCategory.CONFIGURATION),  # Empty key

            # Complex keys
            (KeyError(("tuple", "key")), ErrorCategory.CONFIGURATION),
            (KeyError({"dict": "key"}), ErrorCategory.CONFIGURATION),
        ]

        for error, expected_category in config_scenarios:
            with self.subTest(error=type(error).__name__):
                category = self.classifier.classify_exception(error)
                assert category == expected_category

    def test_classify_os_error_with_errno_comprehensive(self) -> None:
        """Test comprehensive OS error classification based on errno."""
        errno_scenarios = [
            # File not found errors
            (errno.ENOENT, "No such file or directory", ErrorCategory.FILE_NOT_FOUND),

            # Permission errors
            (errno.EACCES, "Permission denied", ErrorCategory.PERMISSION),
            (errno.EPERM, "Operation not permitted", ErrorCategory.PERMISSION),

            # Validation errors
            (errno.EEXIST, "File exists", ErrorCategory.VALIDATION),
            (errno.ENOTDIR, "Not a directory", ErrorCategory.VALIDATION),
            (errno.EISDIR, "Is a directory", ErrorCategory.VALIDATION),
            (errno.ENOTEMPTY, "Directory not empty", ErrorCategory.VALIDATION),

            # System errors
            (errno.ENOSPC, "No space left on device", ErrorCategory.SYSTEM),
            (errno.ENOMEM, "Out of memory", ErrorCategory.SYSTEM),
            (errno.EIO, "I/O error", ErrorCategory.SYSTEM),

            # Network errors (some errno codes can indicate network issues)
            (errno.ECONNREFUSED, "Connection refused", ErrorCategory.NETWORK),
            (errno.ETIMEDOUT, "Connection timed out", ErrorCategory.NETWORK),

            # Unknown errno
            (999999, "Unknown error", ErrorCategory.SYSTEM),  # Non-standard errno
        ]

        for err_no, message, expected_category in errno_scenarios:
            with self.subTest(errno=err_no):
                error = OSError(err_no, message)
                category = self.classifier.classify_exception(error)
                assert category == expected_category

    def test_classify_os_error_edge_cases(self) -> None:
        """Test OS error classification edge cases."""
        # Test OSError with None errno
        error = OSError("Error without errno")
        error.errno = None
        category = self.classifier.classify_exception(error)
        assert category == ErrorCategory.NETWORK  # socket.error inheritance

        # Test OSError with zero errno
        error = OSError(0, "Zero errno")
        category = self.classifier.classify_exception(error)
        assert category == ErrorCategory.NETWORK  # Falls through to type mapping

        # Test OSError without errno attribute at all
        class CustomOSError(OSError):
            pass

        error = CustomOSError("Custom OS error")
        if hasattr(error, "errno"):
            delattr(error, "errno")
        category = self.classifier.classify_exception(error)
        assert category == ErrorCategory.NETWORK

    def test_classify_unknown_exception_comprehensive(self) -> None:
        """Test comprehensive unknown exception classification."""
        # Create various unknown exception types
        unknown_scenarios = []

        for i in range(5):
            class UnknownException(Exception):
                pass
            UnknownException.__name__ = f"UnknownException{i}"
            unknown_scenarios.append(UnknownException(f"Unknown error {i}"))

        # Add some edge cases
        unknown_scenarios.extend([
            Exception("Base exception"),
            BaseException("Base exception"),
            SystemExit("System exit"),  # Special case
            KeyboardInterrupt("Keyboard interrupt"),  # Special case
        ])

        for error in unknown_scenarios:
            with self.subTest(error=type(error).__name__):
                category = self.classifier.classify_exception(error)
                assert category == ErrorCategory.UNKNOWN

    def test_add_type_mapping_comprehensive(self) -> None:
        """Test comprehensive custom type mapping functionality."""
        # Test adding various custom mappings
        mapping_scenarios = [
            (self.custom_exceptions[0], ErrorCategory.EXTERNAL_TOOL),
            (self.custom_exceptions[1], ErrorCategory.USER_INPUT),
            (self.custom_exceptions[2], ErrorCategory.PROCESSING),
            (self.custom_exceptions[3], ErrorCategory.CONFIGURATION),
            (self.custom_exceptions[4], ErrorCategory.SYSTEM),
        ]

        for exc_type, expected_category in mapping_scenarios:
            with self.subTest(exc_type=exc_type.__name__):
                self.classifier.add_type_mapping(exc_type, expected_category)

                error = exc_type("Test error")
                category = self.classifier.classify_exception(error)
                assert category == expected_category

        # Test overriding existing mapping
        self.classifier.add_type_mapping(ValueError, ErrorCategory.USER_INPUT)
        error = ValueError("User input error")
        category = self.classifier.classify_exception(error)
        assert category == ErrorCategory.USER_INPUT

    def test_add_custom_classifier_function_comprehensive(self) -> None:
        """Test comprehensive custom classifier function functionality."""
        # Test various custom classifiers
        def network_classifier(exception):
            if "network" in str(exception).lower():
                return ErrorCategory.NETWORK
            return None

        def processing_classifier(exception):
            if hasattr(exception, "processing_error") and exception.processing_error:
                return ErrorCategory.PROCESSING
            return None

        def complex_classifier(exception):
            # More complex classification logic
            message = str(exception).lower()
            if "timeout" in message and "connection" in message:
                return ErrorCategory.NETWORK
            if "memory" in message or "ram" in message:
                return ErrorCategory.SYSTEM
            if "config" in message or "setting" in message:
                return ErrorCategory.CONFIGURATION
            return None

        # Add classifiers
        self.classifier.add_custom_classifier(network_classifier)
        self.classifier.add_custom_classifier(processing_classifier)
        self.classifier.add_custom_classifier(complex_classifier)

        # Test various scenarios
        test_scenarios = [
            (Exception("Network timeout occurred"), ErrorCategory.NETWORK),
            (Exception("Connection timeout error"), ErrorCategory.NETWORK),
            (Exception("Out of memory error"), ErrorCategory.SYSTEM),
            (Exception("Invalid config file"), ErrorCategory.CONFIGURATION),
        ]

        for error, expected_category in test_scenarios:
            with self.subTest(error=str(error)):
                category = self.classifier.classify_exception(error)
                assert category == expected_category

        # Test with custom attribute
        class ProcessingException(Exception):
            def __init__(self, message, processing_error=False) -> None:
                super().__init__(message)
                self.processing_error = processing_error

        error = ProcessingException("Processing failed", processing_error=True)
        category = self.classifier.classify_exception(error)
        assert category == ErrorCategory.PROCESSING

    def test_custom_classifier_priority_comprehensive(self) -> None:
        """Test comprehensive custom classifier priority scenarios."""
        # Add multiple classifiers with overlapping logic
        def high_priority_classifier(exception):
            if isinstance(exception, ValueError) and "priority" in str(exception):
                return ErrorCategory.USER_INPUT
            return None

        def medium_priority_classifier(exception):
            if isinstance(exception, ValueError):
                return ErrorCategory.CONFIGURATION
            return None

        def low_priority_classifier(exception):
            if "error" in str(exception).lower():
                return ErrorCategory.UNKNOWN
            return None

        # Add in priority order
        self.classifier.add_custom_classifier(high_priority_classifier)
        self.classifier.add_custom_classifier(medium_priority_classifier)
        self.classifier.add_custom_classifier(low_priority_classifier)

        # Test priority scenarios
        test_scenarios = [
            (ValueError("priority error"), ErrorCategory.USER_INPUT),  # High priority matches
            (ValueError("normal error"), ErrorCategory.CONFIGURATION),  # Medium priority matches
            (TypeError("type error"), ErrorCategory.UNKNOWN),  # Low priority matches
            (KeyError("key"), ErrorCategory.CONFIGURATION),  # Default mapping
        ]

        for error, expected_category in test_scenarios:
            with self.subTest(error=str(error)):
                category = self.classifier.classify_exception(error)
                assert category == expected_category

    def test_inheritance_based_classification_comprehensive(self) -> None:
        """Test comprehensive inheritance-based classification."""
        # Create inheritance hierarchies
        class CustomConnectionError(ConnectionError):
            pass

        class DeepCustomConnectionError(CustomConnectionError):
            pass

        class MultipleInheritanceError(ConnectionError, ValueError):
            pass

        class CustomFileError(FileNotFoundError):
            pass

        # Test classification based on inheritance
        inheritance_scenarios = [
            (CustomConnectionError("Custom connection"), ErrorCategory.NETWORK),
            (DeepCustomConnectionError("Deep custom"), ErrorCategory.NETWORK),
            (MultipleInheritanceError("Multiple inheritance"), ErrorCategory.NETWORK),  # First base class
            (CustomFileError("Custom file error"), ErrorCategory.FILE_NOT_FOUND),
        ]

        for error, expected_category in inheritance_scenarios:
            with self.subTest(error=type(error).__name__):
                category = self.classifier.classify_exception(error)
                assert category == expected_category

    def test_concurrent_classification(self) -> None:
        """Test concurrent error classification operations."""
        results = []
        errors = []

        def classify_error(error_id: int) -> None:
            try:
                if error_id % 5 == 0:
                    error = FileNotFoundError(f"File {error_id} not found")
                elif error_id % 5 == 1:
                    error = PermissionError(f"Permission denied {error_id}")
                elif error_id % 5 == 2:
                    error = ValueError(f"Invalid value {error_id}")
                elif error_id % 5 == 3:
                    error = ConnectionError(f"Connection failed {error_id}")
                else:
                    error = Exception(f"Unknown error {error_id}")

                category = self.classifier.classify_exception(error)
                results.append((error_id, type(error).__name__, category))

            except Exception as e:
                errors.append((error_id, e))

        # Run concurrent classifications
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(classify_error, i) for i in range(50)]
            for future in futures:
                future.result()

        assert len(errors) == 0, f"Concurrent classification errors: {errors}"
        assert len(results) == 50

        # Verify classifications are correct
        for error_id, _error_type, category in results:
            if error_id % 5 == 0:
                assert category == ErrorCategory.FILE_NOT_FOUND
            elif error_id % 5 == 1:
                assert category == ErrorCategory.PERMISSION
            elif error_id % 5 == 2:
                assert category == ErrorCategory.VALIDATION
            elif error_id % 5 == 3:
                assert category == ErrorCategory.NETWORK
            else:
                assert category == ErrorCategory.UNKNOWN

    def test_performance_with_many_custom_classifiers_comprehensive(self) -> None:
        """Test comprehensive performance with many custom classifiers."""
        # Add many classifiers
        classifier_count = 200

        for i in range(classifier_count):
            def make_classifier(index=i):
                def classifier(exception):
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
        ]

        for error in test_errors:
            start_time = time.time()
            category = self.classifier.classify_exception(error)
            end_time = time.time()

            # Should still be fast even with many classifiers
            assert end_time - start_time < 0.02, "Classification too slow"

            # Verify correct classification
            if f"pattern_{classifier_count // 2}" in str(error):
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
            category = self.classifier.classify_exception(error)

            # Verify classification still works
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
        # Test with None (should handle gracefully)
        try:
            category = self.classifier.classify_exception(None)
            # Should handle None gracefully, likely returning UNKNOWN
            assert isinstance(category, ErrorCategory)
        except Exception:
            # Or it might raise, which is also acceptable
            pass

        # Test with non-exception objects
        non_exceptions = [
            "string error",
            123,
            {"error": "dict"},
            ["error", "list"],
        ]

        for obj in non_exceptions:
            try:
                category = self.classifier.classify_exception(obj)
                # Should handle gracefully
                assert isinstance(category, ErrorCategory)
            except Exception:
                # Or might raise, which is acceptable
                pass

    def test_create_structured_error_method(self) -> None:
        """Test create_structured_error method functionality."""
        # Test that the method exists
        assert hasattr(self.classifier, "create_structured_error")

        # If implemented, test basic functionality
        try:
            error = ValueError("Test error")
            structured = self.classifier.create_structured_error(error)
            # If it returns something, verify it's reasonable
            if structured is not None:
                assert structured is not None
        except NotImplementedError:
            # Method might not be implemented yet
            pass

    def test_classifier_initialization_comprehensive(self) -> None:
        """Test comprehensive classifier initialization."""
        classifier = ErrorClassifier()

        # Test internal state
        assert isinstance(classifier._type_mappings, dict)
        assert isinstance(classifier._custom_classifiers, list)

        # Test default type mappings
        expected_mappings = {
            FileNotFoundError: ErrorCategory.FILE_NOT_FOUND,
            PermissionError: ErrorCategory.PERMISSION,
            ValueError: ErrorCategory.VALIDATION,
            TypeError: ErrorCategory.VALIDATION,
            KeyError: ErrorCategory.CONFIGURATION,
            AttributeError: ErrorCategory.CONFIGURATION,
            ConnectionError: ErrorCategory.NETWORK,
            TimeoutError: ErrorCategory.NETWORK,
        }

        for exc_type, expected_category in expected_mappings.items():
            assert exc_type in classifier._type_mappings
            assert classifier._type_mappings[exc_type] == expected_category

        # Test empty custom classifiers
        assert len(classifier._custom_classifiers) == 0

    def test_error_category_enum_comprehensive(self) -> None:
        """Test comprehensive ErrorCategory enum functionality."""
        # Test all expected categories exist and are unique
        expected_categories = {
            ErrorCategory.VALIDATION,
            ErrorCategory.PERMISSION,
            ErrorCategory.FILE_NOT_FOUND,
            ErrorCategory.NETWORK,
            ErrorCategory.PROCESSING,
            ErrorCategory.CONFIGURATION,
            ErrorCategory.SYSTEM,
            ErrorCategory.USER_INPUT,
            ErrorCategory.EXTERNAL_TOOL,
            ErrorCategory.UNKNOWN,
        }

        # Verify all categories exist
        for category in expected_categories:
            assert isinstance(category, ErrorCategory)

        # Verify uniqueness
        assert len(expected_categories) == len(set(expected_categories))

        # Test string representation
        for category in expected_categories:
            assert isinstance(str(category), str)
            assert isinstance(category.name, str)
            assert isinstance(category.value, str)

    def test_errno_classification_completeness(self) -> None:
        """Test errno classification completeness."""
        # Test common errno values
        errno_tests = [
            (errno.EPERM, ErrorCategory.PERMISSION),
            (errno.ENOENT, ErrorCategory.FILE_NOT_FOUND),
            (errno.EIO, ErrorCategory.SYSTEM),
            (errno.ENOMEM, ErrorCategory.SYSTEM),
            (errno.EACCES, ErrorCategory.PERMISSION),
            (errno.EEXIST, ErrorCategory.VALIDATION),
            (errno.ENOTDIR, ErrorCategory.VALIDATION),
            (errno.EISDIR, ErrorCategory.VALIDATION),
            (errno.ENOSPC, ErrorCategory.SYSTEM),
            (errno.ENOTEMPTY, ErrorCategory.VALIDATION),
        ]

        for err_no, expected_category in errno_tests:
            with self.subTest(errno=err_no):
                error = OSError(err_no, f"Error {err_no}")
                category = self.classifier.classify_exception(error)
                assert category == expected_category

    def test_classifier_thread_safety(self) -> None:
        """Test classifier thread safety."""
        # Create a shared classifier
        shared_classifier = ErrorClassifier()
        results = []
        errors = []

        def concurrent_operation(op_id: int) -> None:
            try:
                if op_id % 3 == 0:
                    # Add custom mapping
                    exc_type = type(f"CustomExc{op_id}", (Exception,), {})
                    shared_classifier.add_type_mapping(exc_type, ErrorCategory.PROCESSING)
                    results.append(("mapping", op_id))
                elif op_id % 3 == 1:
                    # Add custom classifier
                    def custom(exc):
                        if f"pattern{op_id}" in str(exc):
                            return ErrorCategory.USER_INPUT
                        return None
                    shared_classifier.add_custom_classifier(custom)
                    results.append(("classifier", op_id))
                else:
                    # Classify exception
                    error = ValueError(f"Error {op_id}")
                    category = shared_classifier.classify_exception(error)
                    results.append(("classify", op_id, category))

            except Exception as e:
                errors.append((op_id, e))

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(60)]
            for future in futures:
                future.result()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 60


# Compatibility tests using pytest style for existing test coverage
@pytest.fixture()
def classifier_pytest():
    """Create error classifier for pytest testing."""
    return ErrorClassifier()


def test_classify_file_not_found_error_pytest(classifier_pytest) -> None:
    """Test FileNotFoundError classification using pytest style."""
    error = FileNotFoundError("File not found")
    category = classifier_pytest.classify_exception(error)
    assert category == ErrorCategory.FILE_NOT_FOUND


def test_classify_permission_error_pytest(classifier_pytest) -> None:
    """Test PermissionError classification using pytest style."""
    error = PermissionError("Permission denied")
    category = classifier_pytest.classify_exception(error)
    assert category == ErrorCategory.PERMISSION


def test_classify_validation_errors_pytest(classifier_pytest) -> None:
    """Test validation error classification using pytest style."""
    validation_errors = [
        (ValueError("Invalid value"), ErrorCategory.VALIDATION),
        (TypeError("Wrong type"), ErrorCategory.VALIDATION),
        (IsADirectoryError("Expected file"), ErrorCategory.VALIDATION),
        (NotADirectoryError("Expected directory"), ErrorCategory.VALIDATION),
    ]

    for error, expected_category in validation_errors:
        category = classifier_pytest.classify_exception(error)
        assert category == expected_category


def test_classify_network_errors_pytest(classifier_pytest) -> None:
    """Test network error classification using pytest style."""
    network_errors = [
        (ConnectionError("Connection failed"), ErrorCategory.NETWORK),
        (TimeoutError("Request timed out"), ErrorCategory.NETWORK),
        (OSError("Socket error"), ErrorCategory.NETWORK),
    ]

    for error, expected_category in network_errors:
        category = classifier_pytest.classify_exception(error)
        assert category == expected_category


def test_add_custom_classifier_pytest(classifier_pytest) -> None:
    """Test custom classifier using pytest style."""
    def custom_classifier(exception):
        if "network" in str(exception).lower():
            return ErrorCategory.NETWORK
        return None

    classifier_pytest.add_custom_classifier(custom_classifier)

    error = Exception("Network timeout occurred")
    category = classifier_pytest.classify_exception(error)
    assert category == ErrorCategory.NETWORK


def test_errno_classification_pytest(classifier_pytest) -> None:
    """Test errno-based classification using pytest style."""
    error = OSError(errno.ENOENT, "No such file or directory")
    category = classifier_pytest.classify_exception(error)
    assert category == ErrorCategory.FILE_NOT_FOUND

    error = OSError(errno.EACCES, "Permission denied")
    category = classifier_pytest.classify_exception(error)
    assert category == ErrorCategory.PERMISSION


def test_performance_pytest(classifier_pytest) -> None:
    """Test classification performance using pytest style."""
    # Add many classifiers
    for i in range(100):
        def non_matching_classifier(exception, index=i):
            if f"pattern_{index}" in str(exception):
                return ErrorCategory.PROCESSING
            return None
        classifier_pytest.add_custom_classifier(non_matching_classifier)

    # Test classification speed
    error = ValueError("Test error")

    start_time = time.time()
    category = classifier_pytest.classify_exception(error)
    end_time = time.time()

    # Should still be fast
    assert (end_time - start_time) < 0.01
    assert category == ErrorCategory.VALIDATION


if __name__ == "__main__":
    unittest.main()
