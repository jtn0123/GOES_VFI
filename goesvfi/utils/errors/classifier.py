"""
Error classification utilities.

Automatically categorizes exceptions to reduce complexity in error handling code.
"""

import errno
import socket
from typing import Callable, Dict, Optional, Type

from .base import ErrorCategory, ErrorContext, StructuredError


class ErrorClassifier:
    """
    Automatically classifies exceptions into structured errors.

    Reduces complexity by centralizing error classification logic.
    """

    def __init__(self) -> None:
        # Map exception types to categories
        self._type_mappings: Dict[Type[Exception], ErrorCategory] = {
            FileNotFoundError: ErrorCategory.FILE_NOT_FOUND,
            PermissionError: ErrorCategory.PERMISSION,
            IsADirectoryError: ErrorCategory.VALIDATION,
            NotADirectoryError: ErrorCategory.VALIDATION,
            OSError: ErrorCategory.SYSTEM,
            IOError: ErrorCategory.SYSTEM,
            ValueError: ErrorCategory.VALIDATION,
            TypeError: ErrorCategory.VALIDATION,
            KeyError: ErrorCategory.CONFIGURATION,
            AttributeError: ErrorCategory.CONFIGURATION,
            ConnectionError: ErrorCategory.NETWORK,
            TimeoutError: ErrorCategory.NETWORK,
            socket.error: ErrorCategory.NETWORK,
        }

        # Custom classification functions
        self._custom_classifiers: list[Callable[[Exception], Optional[ErrorCategory]]] = []

    def add_type_mapping(self, exception_type: Type[Exception], category: ErrorCategory) -> None:
        """Add a custom exception type mapping."""
        self._type_mappings[exception_type] = category

    def add_custom_classifier(self, classifier_func: Callable[[Exception], Optional[ErrorCategory]]) -> None:
        """Add a custom classification function."""
        self._custom_classifiers.append(classifier_func)

    def classify_exception(self, exception: Exception) -> ErrorCategory:
        """
        Classify an exception into an error category.

        Args:
            exception: The exception to classify

        Returns:
            ErrorCategory for the exception
        """
        # Try custom classifiers first
        for classifier in self._custom_classifiers:
            category = classifier(exception)
            if category is not None:
                return category

        # Special handling for OSError with errno (before checking type mappings)
        # This needs to come first because socket.error is OSError in Python 3
        if isinstance(exception, OSError) and hasattr(exception, "errno") and exception.errno:
            errno_category = self._classify_os_error(exception)
            # Return the errno-based classification directly
            return errno_category

        # Check direct type mappings
        exception_type = type(exception)
        if exception_type in self._type_mappings:
            return self._type_mappings[exception_type]

        # Check parent class mappings
        for exc_type, category in self._type_mappings.items():
            if isinstance(exception, exc_type):
                return category

        return ErrorCategory.UNKNOWN

    def _classify_os_error(self, exception: OSError) -> ErrorCategory:
        """Classify OSError based on errno."""
        if hasattr(exception, "errno") and exception.errno:
            errno_mappings = {
                errno.ENOENT: ErrorCategory.FILE_NOT_FOUND,
                errno.EACCES: ErrorCategory.PERMISSION,
                errno.EPERM: ErrorCategory.PERMISSION,
                errno.EEXIST: ErrorCategory.VALIDATION,
                errno.ENOTDIR: ErrorCategory.VALIDATION,
                errno.EISDIR: ErrorCategory.VALIDATION,
                errno.ENOSPC: ErrorCategory.SYSTEM,
                errno.ENOTEMPTY: ErrorCategory.VALIDATION,
            }
            return errno_mappings.get(exception.errno, ErrorCategory.SYSTEM)

        return ErrorCategory.SYSTEM

    def create_structured_error(
        self,
        exception: Exception,
        operation: str = "unknown",
        component: str = "unknown",
        user_message: Optional[str] = None,
    ) -> StructuredError:
        """
        Create a structured error from an exception.

        Args:
            exception: The original exception
            operation: The operation that failed
            component: The component where the error occurred
            user_message: Optional user-friendly message

        Returns:
            StructuredError with appropriate classification and context
        """
        category = self.classify_exception(exception)

        # Generate appropriate user message and suggestions
        if user_message is None:
            user_message = self._generate_user_message(exception, category)

        suggestions = self._generate_suggestions(exception, category)

        # Determine if error is recoverable
        recoverable = self._is_recoverable(category, exception)

        from .base import ErrorContext

        context = ErrorContext(operation=operation, component=component)
        self._add_context_from_exception(context, exception)

        return StructuredError(
            message=str(exception),
            category=category,
            context=context,
            cause=exception,
            recoverable=recoverable,
            user_message=user_message,
            suggestions=suggestions,
        )

    def _generate_user_message(self, exception: Exception, category: ErrorCategory) -> str:
        """Generate a user-friendly message based on exception and category."""
        if category == ErrorCategory.FILE_NOT_FOUND:
            return f"File or directory not found: {exception}"
        elif category == ErrorCategory.PERMISSION:
            return f"Permission denied: {exception}"
        elif category == ErrorCategory.NETWORK:
            return f"Network error: {exception}"
        elif category == ErrorCategory.VALIDATION:
            return f"Invalid input: {exception}"
        elif category == ErrorCategory.CONFIGURATION:
            return f"Configuration error: {exception}"
        elif category == ErrorCategory.EXTERNAL_TOOL:
            return f"External tool error: {exception}"
        else:
            return str(exception)

    def _generate_suggestions(self, exception: Exception, category: ErrorCategory) -> list[str]:
        """Generate helpful suggestions based on exception and category."""
        suggestions = []

        if category == ErrorCategory.FILE_NOT_FOUND:
            suggestions.extend(
                [
                    "Check that the file path is correct",
                    "Ensure the file exists",
                    "Verify you have permission to access the directory",
                ]
            )
        elif category == ErrorCategory.PERMISSION:
            suggestions.extend(
                [
                    "Check file/directory permissions",
                    "Run with appropriate privileges",
                    "Ensure you own the file or have necessary access rights",
                ]
            )
        elif category == ErrorCategory.NETWORK:
            suggestions.extend(
                [
                    "Check your internet connection",
                    "Verify the server is accessible",
                    "Check firewall settings",
                ]
            )
        elif category == ErrorCategory.VALIDATION:
            suggestions.extend(
                [
                    "Check input parameters",
                    "Verify data format is correct",
                    "Ensure all required fields are provided",
                ]
            )
        elif category == ErrorCategory.CONFIGURATION:
            suggestions.extend(
                [
                    "Check configuration file",
                    "Verify all required settings are present",
                    "Check for typos in configuration keys",
                ]
            )
        elif category == ErrorCategory.EXTERNAL_TOOL:
            suggestions.extend(
                [
                    "Check that the tool is installed",
                    "Verify the tool is in your PATH",
                    "Check tool version compatibility",
                ]
            )

        return suggestions

    def _is_recoverable(self, category: ErrorCategory, exception: Exception) -> bool:
        """Determine if an error is potentially recoverable."""
        recoverable_categories = {
            ErrorCategory.VALIDATION,
            ErrorCategory.FILE_NOT_FOUND,
            ErrorCategory.PERMISSION,
            ErrorCategory.NETWORK,
            ErrorCategory.CONFIGURATION,
            ErrorCategory.USER_INPUT,
            ErrorCategory.EXTERNAL_TOOL,
        }
        return category in recoverable_categories

    def _add_context_from_exception(self, context: ErrorContext, exception: Exception) -> None:
        """Add relevant context data from the exception."""
        if isinstance(exception, (FileNotFoundError, PermissionError, IsADirectoryError)):
            if hasattr(exception, "filename") and exception.filename:
                context.add_user_data("file_path", str(exception.filename))

        if isinstance(exception, OSError) and hasattr(exception, "errno"):
            context.add_system_data("errno", exception.errno)

        if isinstance(exception, (ConnectionError, TimeoutError, socket.error)):
            context.add_system_data("network_error_type", type(exception).__name__)


# Default classifier instance
default_classifier = ErrorClassifier()


# Add some additional custom classifiers
def _classify_import_errors(exception: Exception) -> Optional[ErrorCategory]:
    """Custom classifier for import errors."""
    if isinstance(exception, ImportError):
        return ErrorCategory.CONFIGURATION
    return None


def _classify_subprocess_errors(exception: Exception) -> Optional[ErrorCategory]:
    """Custom classifier for subprocess errors."""
    import subprocess

    if isinstance(exception, subprocess.CalledProcessError):
        return ErrorCategory.EXTERNAL_TOOL
    if isinstance(exception, subprocess.TimeoutExpired):
        return ErrorCategory.EXTERNAL_TOOL
    return None


# Register custom classifiers
default_classifier.add_custom_classifier(_classify_import_errors)
default_classifier.add_custom_classifier(_classify_subprocess_errors)
