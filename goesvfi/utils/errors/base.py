"""
Base error handling types and classes.

Provides structured error handling that reduces complexity in error-heavy functions.
"""

import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Type


class ErrorCategory(Enum):
    """Categories for classifying errors."""

    VALIDATION = auto()
    PERMISSION = auto()
    FILE_NOT_FOUND = auto()
    NETWORK = auto()
    PROCESSING = auto()
    CONFIGURATION = auto()
    SYSTEM = auto()
    USER_INPUT = auto()
    EXTERNAL_TOOL = auto()
    UNKNOWN = auto()


@dataclass
class ErrorContext:
    """Context information for an error."""

    operation: str
    component: str
    timestamp: datetime = field(default_factory=datetime.now)
    user_data: Dict[str, Any] = field(default_factory=dict)
    system_data: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None

    def add_user_data(self, key: str, value: Any) -> None:
        """Add user-relevant context data."""
        self.user_data[key] = value

    def add_system_data(self, key: str, value: Any) -> None:
        """Add system/debug context data."""
        self.system_data[key] = value


class StructuredError(Exception):
    """
    Structured error with rich context and classification.

    Reduces complexity by providing a consistent error format with
    built-in classification and context management.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        recoverable: bool = False,
        user_message: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
    ) -> None:
        self.message = message
        self.category = category
        self.context = context or ErrorContext(operation="unknown", component="unknown")
        self.cause = cause
        self.recoverable = recoverable
        self.user_message = user_message or message
        self.suggestions = suggestions or []
        self.traceback_str = traceback.format_exc() if cause else None

        super().__init__(self.message)

    @classmethod
    def validation_error(
        cls: Type["StructuredError"],
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        suggestions: Optional[List[str]] = None,
    ) -> "StructuredError":
        """Create a validation error."""
        context = ErrorContext(operation="validation", component="input")
        if field:
            context.add_user_data("field", field)
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
        cls: Type["StructuredError"],
        message: str,
        file_path: Optional[str] = None,
        operation: str = "file_operation",
        cause: Optional[Exception] = None,
    ) -> "StructuredError":
        """Create a file-related error."""
        context = ErrorContext(operation=operation, component="filesystem")
        if file_path:
            context.add_user_data("file_path", file_path)

        category = (
            ErrorCategory.FILE_NOT_FOUND
            if "not found" in message.lower()
            else ErrorCategory.PERMISSION
        )

        return cls(
            message=message,
            category=category,
            context=context,
            cause=cause,
            recoverable=True,
        )

    @classmethod
    def network_error(
        cls: Type["StructuredError"],
        message: str,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        cause: Optional[Exception] = None,
    ) -> "StructuredError":
        """Create a network-related error."""
        context = ErrorContext(operation="network_request", component="network")
        if url:
            context.add_user_data("url", url)
        if status_code:
            context.add_user_data("status_code", status_code)

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
        cls: Type["StructuredError"],
        message: str,
        stage: Optional[str] = None,
        input_data: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> "StructuredError":
        """Create a processing error."""
        context = ErrorContext(operation="data_processing", component="processor")
        if stage:
            context.add_user_data("processing_stage", stage)
        if input_data:
            context.add_system_data("input_data", input_data)

        return cls(
            message=message,
            category=ErrorCategory.PROCESSING,
            context=context,
            cause=cause,
            recoverable=False,
        )

    @classmethod
    def configuration_error(
        cls: Type["StructuredError"],
        message: str,
        config_key: Optional[str] = None,
        config_value: Any = None,
        suggestions: Optional[List[str]] = None,
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
        cls: Type["StructuredError"],
        message: str,
        tool_name: str,
        command: Optional[str] = None,
        exit_code: Optional[int] = None,
        cause: Optional[Exception] = None,
    ) -> "StructuredError":
        """Create an external tool error."""
        context = ErrorContext(operation="external_tool", component=tool_name)
        context.add_user_data("tool_name", tool_name)
        if command:
            context.add_system_data("command", command)
        if exit_code is not None:
            context.add_system_data("exit_code", exit_code)

        return cls(
            message=message,
            category=ErrorCategory.EXTERNAL_TOOL,
            context=context,
            cause=cause,
            recoverable=True,
            suggestions=[f"Check that {tool_name} is installed and accessible"],
        )

    def add_suggestion(self, suggestion: str) -> None:
        """Add a suggestion for resolving the error."""
        self.suggestions.append(suggestion)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "message": self.message,
            "category": self.category.name,
            "user_message": self.user_message,
            "recoverable": self.recoverable,
            "suggestions": self.suggestions,
            "context": {
                "operation": self.context.operation,
                "component": self.context.component,
                "timestamp": self.context.timestamp.isoformat(),
                "user_data": self.context.user_data,
                "system_data": self.context.system_data,
            },
            "cause": str(self.cause) if self.cause else None,
            "traceback": self.traceback_str,
        }

    def get_user_friendly_message(self) -> str:
        """Get a user-friendly error message with suggestions."""
        message = self.user_message

        if self.suggestions:
            suggestions_text = "\n".join(
                f"• {suggestion}" for suggestion in self.suggestions
            )
            message += f"\n\nSuggestions:\n{suggestions_text}"

        return message


class ErrorBuilder:
    """Builder for creating structured errors with fluent interface."""

    def __init__(self, message: str) -> None:
        self.message = message
        self.category = ErrorCategory.UNKNOWN
        self.context = ErrorContext(operation="unknown", component="unknown")
        self.cause: Optional[Exception] = None
        self.recoverable = False
        self.user_message: Optional[str] = None
        self.suggestions: List[str] = []

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

    def with_cause(self, cause: Exception) -> "ErrorBuilder":
        """Set underlying cause."""
        self.cause = cause
        return self

    def as_recoverable(self, recoverable: bool = True) -> "ErrorBuilder":
        """Mark as recoverable or not."""
        self.recoverable = recoverable
        return self

    def with_user_message(self, user_message: str) -> "ErrorBuilder":
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
        )
