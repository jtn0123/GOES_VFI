"""
Base validation classes and types.

Provides the foundation for composable validation that reduces complexity
in functions with extensive parameter checking.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type


class ValidationError(Exception):
    """Base exception for validation failures."""

    def __init__(self, message: str, field: str | None = None, value: Any = None) -> None:
        self.message = message
        self.field = field
        self.value = value
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with field context."""
        if self.field:
            return f"Validation failed for '{self.field}': {self.message}"
        return f"Validation failed: {self.message}"


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool
    errors: list[ValidationError]
    warnings: list[str]

    @classmethod
    def success(cls: type["ValidationResult"]) -> "ValidationResult":
        """Create a successful validation result."""
        return cls(is_valid=True, errors=[], warnings=[])

    @classmethod
    def failure(cls: type["ValidationResult"], error: ValidationError) -> "ValidationResult":
        """Create a failed validation result."""
        return cls(is_valid=False, errors=[error], warnings=[])

    @classmethod
    def failures(cls: type["ValidationResult"], errors: list[ValidationError]) -> "ValidationResult":
        """Create a failed validation result with multiple errors."""
        return cls(is_valid=False, errors=errors, warnings=[])

    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)

    def add_error(self, error: ValidationError) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.is_valid = False

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another validation result into this one."""
        combined_errors = self.errors + other.errors
        combined_warnings = self.warnings + other.warnings
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=combined_errors,
            warnings=combined_warnings,
        )


class ValidatorBase(ABC):
    """Base class for all validators."""

    def __init__(self, field_name: str | None = None) -> None:
        self.field_name = field_name

    @abstractmethod
    def validate(self, value: Any, context: dict[str, Any] | None = None) -> ValidationResult:
        """
        Validate a value.

        Args:
            value: The value to validate
            context: Optional context for validation (e.g., other field values)

        Returns:
            ValidationResult indicating success or failure
        """

    def _create_error(self, message: str, value: Any = None) -> ValidationError:
        """Create a ValidationError with proper field context."""
        return ValidationError(message, field=self.field_name, value=value)


class CompositeValidator(ValidatorBase):
    """Validator that combines multiple validators."""

    def __init__(self, validators: list[ValidatorBase], field_name: str | None = None) -> None:
        super().__init__(field_name)
        self.validators = validators

    def validate(self, value: Any, context: dict[str, Any] | None = None) -> ValidationResult:
        """Run all validators and combine results."""
        result = ValidationResult.success()

        for validator in self.validators:
            sub_result = validator.validate(value, context)
            result = result.merge(sub_result)

        return result


class ConditionalValidator(ValidatorBase):
    """Validator that only runs if a condition is met."""

    def __init__(
        self,
        validator: ValidatorBase,
        condition_func: Callable[..., bool],
        field_name: str | None = None,
    ) -> None:
        super().__init__(field_name)
        self.validator = validator
        self.condition_func = condition_func

    def validate(self, value: Any, context: dict[str, Any] | None = None) -> ValidationResult:
        """Run validator only if condition is true."""
        if callable(self.condition_func) and self.condition_func(value, context):
            return self.validator.validate(value, context)
        return ValidationResult.success()
