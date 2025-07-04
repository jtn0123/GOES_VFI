"""Base error handling types and classes.

Provides structured error handling that reduces complexity in error-heavy functions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import traceback
from typing import Any


class ErrorCategory(Enum):
    """Categories for classifying errors."""

    VALIDATION = "validation"
    PERMISSION = "permission"
    FILE_NOT_FOUND = "file_not_found"
    NETWORK = "network"
    PROCESSING = "processing"
    CONFIGURATION = "configuration"
    SYSTEM = "system"
    USER_INPUT = "user_input"
    EXTERNAL_TOOL = "external_tool"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for an error."""

    operation: str
    component: str
    timestamp: datetime = field(default_factory=datetime.now)
    user_data: dict[str, Any] = field(default_factory=dict)
    system_data: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None

    def add_user_data(self, key: str, value: Any) -> None:
        """Add user-relevant context data."""
        self.user_data[key] = value

    def add_system_data(self, key: str, value: Any) -> None:
        """Add system/debug context data."""
        self.system_data[key] = value


class StructuredError(Exception):
    """Structured error with rich context and classification.

    Reduces complexity by providing a consistent error format with
    built-in classification and context management.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        context: ErrorContext | None = None,
        cause: Exception | None = None,
        recoverable: bool = False,
        user_message: str | None = None,
        suggestions: list[str] | None = None,
        _explicit_user_message: bool = False,
    ) -> None:
        self.message = message
        self.category = category
        self.context = context or ErrorContext(operation="unknown", component="unknown")
        self.cause = cause
        self.recoverable = recoverable
        # If user_message was explicitly passed (even as None), use it; otherwise default to message
        if _explicit_user_message:
            self.user_message = user_message
        else:
            self.user_message = user_message if user_message is not None else message
        self.suggestions = suggestions or []
        self.traceback_str = traceback.format_exc() if cause else None

        super().__init__(self.message)

    @classmethod
    def validation_error(
        cls: type["StructuredError"],
        message: str,
        field_name: str | None = None,
        value: Any = None,
        suggestions: list[str] | None = None,
    ) -> "StructuredError":
        """Create a validation error."""
        context = ErrorContext(operation="validation", component="input")
        if field_name:
            context.add_user_data("field", field_name)
        if value is not None:
            context.add_user_data("value", str(value))

        return cls(
            message=message,
            category=ErrorCategory.VALIDATION,
            context=context,
            recoverable=True,
            suggestions=suggestions,
        )

    @classmethod
    def file_error(
        cls: type["StructuredError"],
        message: str,
        file_path: str | None = None,
        operation: str = "file_operation",
        cause: Exception | None = None,
    ) -> "StructuredError":
        """Create a file-related error."""
        context = ErrorContext(operation=operation, component="filesystem")
        if file_path:
            context.add_user_data("file_path", file_path)

        category = ErrorCategory.FILE_NOT_FOUND if "not found" in message.lower() else ErrorCategory.PERMISSION

        return cls(
            message=message,
            category=category,
            context=context,
            cause=cause,
            recoverable=True,
        )

    @classmethod
    def network_error(
        cls: type["StructuredError"],
        message: str,
        url: str | None = None,
        status_code: int | None = None,
        timeout: int | None = None,
        cause: Exception | None = None,
    ) -> "StructuredError":
        """Create a network-related error."""
        context = ErrorContext(operation="network_request", component="network")
        if url:
            context.add_user_data("url", url)
        if status_code:
            context.add_user_data("status_code", status_code)
        if timeout:
            context.add_user_data("timeout", timeout)

        return cls(
            message=message,
            category=ErrorCategory.NETWORK,
            context=context,
            cause=cause,
            recoverable=True,
            suggestions=["Check network connection", "Verify URL is accessible"],
        )

    @classmethod
    def processing_error(
        cls: type["StructuredError"],
        message: str,
        stage: str | None = None,
        input_data: str | None = None,
        metadata: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> "StructuredError":
        """Create a processing error."""
        context = ErrorContext(operation="data_processing", component="processor")
        if stage:
            context.add_user_data("processing_stage", stage)
        if input_data:
            context.add_system_data("input_data", input_data)
        if metadata:
            context.add_system_data("metadata", metadata)

        return cls(
            message=message,
            category=ErrorCategory.PROCESSING,
            context=context,
            cause=cause,
            recoverable=False,
        )

    @classmethod
    def configuration_error(
        cls: type["StructuredError"],
        message: str,
        config_key: str | None = None,
        config_value: Any = None,
        suggestions: list[str] | None = None,
    ) -> "StructuredError":
        """Create a configuration error."""
        context = ErrorContext(operation="configuration", component="config")
        if config_key:
            context.add_user_data("config_key", config_key)
        if config_value is not None:
            context.add_user_data("config_value", str(config_value))

        return cls(
            message=message,
            category=ErrorCategory.CONFIGURATION,
            context=context,
            recoverable=True,
            suggestions=suggestions,
        )

    @classmethod
    def external_tool_error(
        cls: type["StructuredError"],
        message: str,
        tool_name: str,
        command: str | None = None,
        exit_code: int | None = None,
        stderr: str | None = None,
        cause: Exception | None = None,
    ) -> "StructuredError":
        """Create an external tool error."""
        context = ErrorContext(operation="external_tool", component=tool_name)
        context.add_user_data("tool_name", tool_name)
        if command:
            context.add_system_data("command", command)
        if exit_code is not None:
            context.add_system_data("exit_code", exit_code)
        if stderr:
            context.add_system_data("stderr", stderr)

        return cls(
            message=message,
            category=ErrorCategory.EXTERNAL_TOOL,
            context=context,
            cause=cause,
            recoverable=True,
            suggestions=[f"Check that {tool_name} is installed"],
        )

    def add_suggestion(self, suggestion: str) -> None:
        """Add a suggestion for resolving the error."""
        self.suggestions.append(suggestion)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        context_dict = {
            "operation": self.context.operation,
            "component": self.context.component,
            "timestamp": self.context.timestamp.isoformat(),
            "user_data": self.context.user_data,
            "system_data": self.context.system_data,
        }
        if self.context.trace_id:
            context_dict["trace_id"] = self.context.trace_id

        cause_dict = None
        if self.cause:
            cause_dict = {"type": type(self.cause).__name__, "message": str(self.cause)}

        return {
            "message": self.message,
            "category": self.category.name,
            "user_message": self.user_message,
            "recoverable": self.recoverable,
            "suggestions": self.suggestions,
            "context": context_dict,
            "cause": cause_dict,
            "traceback": self.traceback_str,
        }

    def get_user_friendly_message(self) -> str:
        """Get a user-friendly error message with suggestions."""
        message = self.user_message or self.message

        if self.suggestions:
            suggestions_text = "\n".join(f"• {suggestion}" for suggestion in self.suggestions)
            message += f"\n\nSuggestions:\n{suggestions_text}"

        return message


class ErrorBuilder:
    """Builder for creating structured errors with fluent interface."""

    def __init__(self, message: str) -> None:
        self.message = message
        self.category = ErrorCategory.UNKNOWN
        self.context = ErrorContext(operation="unknown", component="unknown")
        self.cause: Exception | None = None
        self.recoverable = False
        self.user_message: str | None = None
        self.suggestions: list[str] = []

    def with_category(self, category: ErrorCategory) -> "ErrorBuilder":
        """Set error category."""
        self.category = category
        return self

    def with_operation(self, operation: str) -> "ErrorBuilder":
        """Set operation context."""
        self.context.operation = operation
        return self

    def with_component(self, component: str) -> "ErrorBuilder":
        """Set component context."""
        self.context.component = component
        return self

    def with_cause(self, cause: Exception | None) -> "ErrorBuilder":
        """Set underlying cause."""
        self.cause = cause
        return self

    def as_recoverable(self, recoverable: bool = True) -> "ErrorBuilder":
        """Mark as recoverable or not."""
        self.recoverable = recoverable
        return self

    def with_user_message(self, user_message: str | None) -> "ErrorBuilder":
        """Set user-friendly message."""
        self.user_message = user_message
        return self

    def add_suggestion(self, suggestion: str) -> "ErrorBuilder":
        """Add a suggestion."""
        self.suggestions.append(suggestion)
        return self

    def add_user_data(self, key: str, value: Any) -> "ErrorBuilder":
        """Add user context data."""
        self.context.add_user_data(key, value)
        return self

    def add_system_data(self, key: str, value: Any) -> "ErrorBuilder":
        """Add system context data."""
        self.context.add_system_data(key, value)
        return self

    def build(self) -> StructuredError:
        """Build the structured error."""
        return StructuredError(
            message=self.message,
            category=self.category,
            context=self.context,
            cause=self.cause,
            recoverable=self.recoverable,
            user_message=self.user_message,
            suggestions=self.suggestions,
            _explicit_user_message=True,  # Builder always explicitly sets user_message
        )
