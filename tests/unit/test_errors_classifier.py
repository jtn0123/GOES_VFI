"""
Tests for error classification utilities.

Tests the ErrorClassifier class and its ability to automatically categorize
exceptions into structured errors with appropriate context and suggestions.
"""

import errno
import socket
import subprocess
from typing import Optional
from unittest.mock import Mock

import pytest

from goesvfi.utils.errors.base import ErrorCategory, ErrorContext, StructuredError
from goesvfi.utils.errors.classifier import ErrorClassifier, default_classifier


class TestErrorClassifier:
    """Test error classifier functionality."""

    def test_classifier_initialization(self):
        """Test classifier initialization with default mappings."""
        classifier = ErrorClassifier()
        
        # Check that default type mappings are set
        assert FileNotFoundError in classifier._type_mappings
        assert classifier._type_mappings[FileNotFoundError] == ErrorCategory.FILE_NOT_FOUND
        assert PermissionError in classifier._type_mappings
        assert classifier._type_mappings[PermissionError] == ErrorCategory.PERMISSION
        assert ValueError in classifier._type_mappings
        assert classifier._type_mappings[ValueError] == ErrorCategory.VALIDATION

    def test_add_type_mapping(self):
        """Test adding custom exception type mappings."""
        classifier = ErrorClassifier()
        
        class CustomError(Exception):
            pass
        
        classifier.add_type_mapping(CustomError, ErrorCategory.PROCESSING)
        
        assert CustomError in classifier._type_mappings
        assert classifier._type_mappings[CustomError] == ErrorCategory.PROCESSING

    def test_add_custom_classifier(self):
        """Test adding custom classification functions."""
        classifier = ErrorClassifier()
        
        def custom_classifier(exception: Exception) -> Optional[ErrorCategory]:
            if isinstance(exception, RuntimeError) and "network" in str(exception):
                return ErrorCategory.NETWORK
            return None
        
        classifier.add_custom_classifier(custom_classifier)
        
        assert custom_classifier in classifier._custom_classifiers

    def test_classify_exception_direct_mapping(self):
        """Test classifying exceptions with direct type mappings."""
        classifier = ErrorClassifier()
        
        test_cases = [
            (FileNotFoundError("File not found"), ErrorCategory.FILE_NOT_FOUND),
            (PermissionError("Permission denied"), ErrorCategory.PERMISSION),
            (ValueError("Invalid value"), ErrorCategory.VALIDATION),
            (TypeError("Type error"), ErrorCategory.VALIDATION),
            (KeyError("Missing key"), ErrorCategory.CONFIGURATION),
            (ConnectionError("Connection failed"), ErrorCategory.NETWORK),
            (TimeoutError("Operation timed out"), ErrorCategory.NETWORK),
        ]
        
        for exception, expected_category in test_cases:
            category = classifier.classify_exception(exception)
            assert category == expected_category, f"Failed for {type(exception).__name__}"

    def test_classify_exception_inheritance(self):
        """Test classifying exceptions using inheritance."""
        classifier = ErrorClassifier()
        
        # OSError should map to SYSTEM
        os_error = OSError("OS error")
        category = classifier.classify_exception(os_error)
        assert category == ErrorCategory.SYSTEM
        
        # socket.error should map to NETWORK
        sock_error = socket.error("Socket error")
        category = classifier.classify_exception(sock_error)
        assert category == ErrorCategory.NETWORK

    def test_classify_exception_custom_classifier(self):
        """Test classification using custom classifiers."""
        classifier = ErrorClassifier()
        
        def custom_classifier(exception: Exception) -> Optional[ErrorCategory]:
            if isinstance(exception, RuntimeError) and "custom" in str(exception):
                return ErrorCategory.PROCESSING
            return None
        
        classifier.add_custom_classifier(custom_classifier)
        
        # Should use custom classifier
        custom_error = RuntimeError("This is a custom error")
        category = classifier.classify_exception(custom_error)
        assert category == ErrorCategory.PROCESSING
        
        # Should fall back to default for non-matching RuntimeError
        regular_error = RuntimeError("Regular runtime error")
        category = classifier.classify_exception(regular_error)
        assert category == ErrorCategory.UNKNOWN

    def test_classify_exception_unknown(self):
        """Test classifying unknown exception types."""
        classifier = ErrorClassifier()
        
        class UnknownError(Exception):
            pass
        
        unknown_error = UnknownError("Unknown error")
        category = classifier.classify_exception(unknown_error)
        assert category == ErrorCategory.UNKNOWN

    def test_classify_os_error_with_errno(self):
        """Test classifying OSError with specific errno values."""
        classifier = ErrorClassifier()
        
        test_cases = [
            (errno.ENOENT, ErrorCategory.FILE_NOT_FOUND),
            (errno.EACCES, ErrorCategory.PERMISSION),
            (errno.EPERM, ErrorCategory.PERMISSION),
            (errno.EEXIST, ErrorCategory.VALIDATION),
            (errno.ENOTDIR, ErrorCategory.VALIDATION),
            (errno.EISDIR, ErrorCategory.VALIDATION),
            (errno.ENOSPC, ErrorCategory.SYSTEM),
            (errno.ENOTEMPTY, ErrorCategory.VALIDATION),
        ]
        
        for errno_code, expected_category in test_cases:
            os_error = OSError()
            os_error.errno = errno_code
            category = classifier.classify_exception(os_error)
            assert category == expected_category, f"Failed for errno {errno_code}"

    def test_classify_os_error_unknown_errno(self):
        """Test classifying OSError with unknown errno."""
        classifier = ErrorClassifier()
        
        os_error = OSError()
        os_error.errno = 99999  # Unknown errno
        category = classifier.classify_exception(os_error)
        assert category == ErrorCategory.SYSTEM

    def test_classify_os_error_no_errno(self):
        """Test classifying OSError without errno."""
        classifier = ErrorClassifier()
        
        os_error = OSError("Generic OS error")
        category = classifier.classify_exception(os_error)
        assert category == ErrorCategory.SYSTEM

    def test_create_structured_error_basic(self):
        """Test creating structured error from exception."""
        classifier = ErrorClassifier()
        
        original_exception = ValueError("Invalid input value")
        structured_error = classifier.create_structured_error(
            exception=original_exception,
            operation="input_validation",
            component="form_validator"
        )
        
        assert isinstance(structured_error, StructuredError)
        assert structured_error.message == "Invalid input value"
        assert structured_error.category == ErrorCategory.VALIDATION
        assert structured_error.context.operation == "input_validation"
        assert structured_error.context.component == "form_validator"
        assert structured_error.cause == original_exception
        assert structured_error.recoverable is True

    def test_create_structured_error_with_user_message(self):
        """Test creating structured error with custom user message."""
        classifier = ErrorClassifier()
        
        original_exception = FileNotFoundError("test.txt")
        structured_error = classifier.create_structured_error(
            exception=original_exception,
            operation="file_read",
            component="file_loader",
            user_message="The requested file could not be found"
        )
        
        assert structured_error.user_message == "The requested file could not be found"

    def test_generate_user_message(self):
        """Test user message generation for different categories."""
        classifier = ErrorClassifier()
        
        test_cases = [
            (FileNotFoundError("test.txt"), ErrorCategory.FILE_NOT_FOUND, "File or directory not found"),
            (PermissionError("Access denied"), ErrorCategory.PERMISSION, "Permission denied"),
            (ConnectionError("Network error"), ErrorCategory.NETWORK, "Network error"),
            (ValueError("Invalid value"), ErrorCategory.VALIDATION, "Invalid input"),
            (KeyError("missing_key"), ErrorCategory.CONFIGURATION, "Configuration error"),
            (RuntimeError("External tool failed"), ErrorCategory.EXTERNAL_TOOL, "External tool error"),
        ]
        
        for exception, category, expected_prefix in test_cases:
            user_message = classifier._generate_user_message(exception, category)
            assert expected_prefix in user_message

    def test_generate_suggestions(self):
        """Test suggestion generation for different categories."""
        classifier = ErrorClassifier()
        
        test_cases = [
            (ErrorCategory.FILE_NOT_FOUND, ["Check that the file path is correct"]),
            (ErrorCategory.PERMISSION, ["Check file/directory permissions"]),
            (ErrorCategory.NETWORK, ["Check your internet connection"]),
            (ErrorCategory.VALIDATION, ["Check input parameters"]),
            (ErrorCategory.CONFIGURATION, ["Check configuration file"]),
            (ErrorCategory.EXTERNAL_TOOL, ["Check that the tool is installed"]),
        ]
        
        for category, expected_suggestions in test_cases:
            suggestions = classifier._generate_suggestions(Exception(), category)
            for expected in expected_suggestions:
                assert any(expected in suggestion for suggestion in suggestions)

    def test_is_recoverable(self):
        """Test recovery determination for different categories."""
        classifier = ErrorClassifier()
        
        recoverable_categories = [
            ErrorCategory.VALIDATION,
            ErrorCategory.FILE_NOT_FOUND,
            ErrorCategory.PERMISSION,
            ErrorCategory.NETWORK,
            ErrorCategory.CONFIGURATION,
            ErrorCategory.USER_INPUT,
            ErrorCategory.EXTERNAL_TOOL,
        ]
        
        non_recoverable_categories = [
            ErrorCategory.PROCESSING,
            ErrorCategory.SYSTEM,
            ErrorCategory.UNKNOWN,
        ]
        
        for category in recoverable_categories:
            assert classifier._is_recoverable(category, Exception()) is True
        
        for category in non_recoverable_categories:
            assert classifier._is_recoverable(category, Exception()) is False

    def test_add_context_from_exception_file_errors(self):
        """Test adding context data from file-related exceptions."""
        classifier = ErrorClassifier()
        context = ErrorContext(operation="test", component="test")
        
        # Test FileNotFoundError with filename
        file_error = FileNotFoundError("File not found")
        file_error.filename = "/path/to/test.txt"
        classifier._add_context_from_exception(context, file_error)
        
        assert context.user_data["file_path"] == "/path/to/test.txt"

    def test_add_context_from_exception_os_error(self):
        """Test adding context data from OSError."""
        classifier = ErrorClassifier()
        context = ErrorContext(operation="test", component="test")
        
        os_error = OSError("OS error")
        os_error.errno = errno.ENOENT
        classifier._add_context_from_exception(context, os_error)
        
        assert context.system_data["errno"] == errno.ENOENT

    def test_add_context_from_exception_network_errors(self):
        """Test adding context data from network exceptions."""
        classifier = ErrorClassifier()
        context = ErrorContext(operation="test", component="test")
        
        network_errors = [
            ConnectionError("Connection failed"),
            TimeoutError("Timeout"),
            socket.error("Socket error"),
        ]
        
        for error in network_errors:
            context = ErrorContext(operation="test", component="test")
            classifier._add_context_from_exception(context, error)
            assert "network_error_type" in context.system_data


class TestDefaultClassifier:
    """Test the default classifier instance and custom classifiers."""

    def test_default_classifier_exists(self):
        """Test that default classifier is properly initialized."""
        assert isinstance(default_classifier, ErrorClassifier)

    def test_import_error_classification(self):
        """Test classification of import errors."""
        import_error = ImportError("Module not found")
        category = default_classifier.classify_exception(import_error)
        assert category == ErrorCategory.CONFIGURATION

    def test_subprocess_error_classification(self):
        """Test classification of subprocess errors."""
        # Test CalledProcessError
        called_process_error = subprocess.CalledProcessError(1, "test_command")
        category = default_classifier.classify_exception(called_process_error)
        assert category == ErrorCategory.EXTERNAL_TOOL
        
        # Test TimeoutExpired
        timeout_error = subprocess.TimeoutExpired("test_command", 30)
        category = default_classifier.classify_exception(timeout_error)
        assert category == ErrorCategory.EXTERNAL_TOOL

    def test_end_to_end_classification(self):
        """Test end-to-end error classification and structured error creation."""
        # Test a realistic scenario
        try:
            # Simulate file operation that fails
            with open("/nonexistent/path/file.txt", "r") as f:
                f.read()
        except FileNotFoundError as e:
            structured_error = default_classifier.create_structured_error(
                exception=e,
                operation="file_read",
                component="data_loader"
            )
            
            assert structured_error.category == ErrorCategory.FILE_NOT_FOUND
            assert structured_error.recoverable is True
            assert "file_read" in structured_error.context.operation
            assert "data_loader" in structured_error.context.component
            assert len(structured_error.suggestions) > 0
            assert "Check that the file path is correct" in structured_error.suggestions


class TestErrorClassifierIntegration:
    """Integration tests for error classifier with real exceptions."""

    def test_complex_exception_scenario(self):
        """Test classifier with complex exception scenario."""
        classifier = ErrorClassifier()
        
        # Create a mock exception that would occur in real usage
        try:
            raise PermissionError("Access denied to /restricted/config.json")
        except PermissionError as e:
            e.filename = "/restricted/config.json"
            structured_error = classifier.create_structured_error(
                exception=e,
                operation="config_load",
                component="configuration_manager"
            )
            
            # Verify comprehensive error structure
            assert structured_error.category == ErrorCategory.PERMISSION
            assert structured_error.recoverable is True
            assert structured_error.context.operation == "config_load"
            assert structured_error.context.component == "configuration_manager"
            assert "/restricted/config.json" in structured_error.context.user_data["file_path"]
            assert "Permission denied" in structured_error.user_message
            assert len(structured_error.suggestions) > 0
            
            # Test dictionary conversion
            error_dict = structured_error.to_dict()
            assert error_dict["category"] == "PERMISSION"
            assert error_dict["recoverable"] is True

    def test_network_exception_scenario(self):
        """Test classifier with network exception scenario."""
        classifier = ErrorClassifier()
        
        connection_error = ConnectionError("Failed to connect to server")
        structured_error = classifier.create_structured_error(
            exception=connection_error,
            operation="api_request",
            component="http_client"
        )
        
        assert structured_error.category == ErrorCategory.NETWORK
        assert structured_error.recoverable is True
        assert "Check your internet connection" in structured_error.suggestions
        assert "network_error_type" in structured_error.context.system_data

    def test_validation_exception_scenario(self):
        """Test classifier with validation exception scenario."""
        classifier = ErrorClassifier()
        
        validation_error = ValueError("Invalid email format: not-an-email")
        structured_error = classifier.create_structured_error(
            exception=validation_error,
            operation="user_input_validation",
            component="form_validator"
        )
        
        assert structured_error.category == ErrorCategory.VALIDATION
        assert structured_error.recoverable is True
        assert "Invalid input" in structured_error.user_message
        assert "Check input parameters" in structured_error.suggestions

    def test_multiple_classifier_priority(self):
        """Test that custom classifiers take priority over default mappings."""
        classifier = ErrorClassifier()
        
        # Add custom classifier that overrides default behavior
        def priority_classifier(exception: Exception) -> Optional[ErrorCategory]:
            if isinstance(exception, ValueError) and "special" in str(exception):
                return ErrorCategory.PROCESSING
            return None
        
        classifier.add_custom_classifier(priority_classifier)
        
        # Regular ValueError should use default mapping
        regular_error = ValueError("Regular validation error")
        category = classifier.classify_exception(regular_error)
        assert category == ErrorCategory.VALIDATION
        
        # Special ValueError should use custom classifier
        special_error = ValueError("This is a special error")
        category = classifier.classify_exception(special_error)
        assert category == ErrorCategory.PROCESSING