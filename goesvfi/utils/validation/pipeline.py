"""
Validation pipeline for composing multiple validators.

Reduces complexity by providing a clean interface for running multiple validations.
"""

from typing import Any, Dict, List, Optional, Tuple

from .base import ValidationError, ValidationResult, ValidatorBase


class ValidationPipeline:
    """
    Pipeline for running multiple validators in sequence.

    This helps reduce complexity in functions that need to validate many parameters
    by centralizing validation logic and providing clear error reporting.
    """

    def __init__(self, name: Optional[str] = None, fail_fast: bool = False):
        """
        Initialize validation pipeline.

        Args:
            name: Optional name for the pipeline (used in error reporting)
            fail_fast: If True, stop validation on first error
        """
        self.name = name or "ValidationPipeline"
        self.fail_fast = fail_fast
        self.validators: List[Tuple[str, ValidatorBase, Any]] = []

    def add_validator(
        self, field_name: str, validator: ValidatorBase, value: Any
    ) -> "ValidationPipeline":
        """
        Add a validator to the pipeline.

        Args:
            field_name: Name of the field being validated
            validator: Validator instance
            value: Value to validate

        Returns:
            Self for method chaining
        """
        self.validators.append((field_name, validator, value))
        return self

    def add_path_validation(
        self,
        field_name: str,
        path_value: Any,
        must_exist: bool = True,
        must_be_file: bool = False,
        must_be_dir: bool = False,
        must_be_readable: bool = False,
        must_be_writable: bool = False,
        create_if_missing: bool = False,
    ) -> "ValidationPipeline":
        """
        Convenience method to add path validation.

        Returns:
            Self for method chaining
        """
        from .path import PathValidator

        validator = PathValidator(
            field_name=field_name,
            must_exist=must_exist,
            must_be_file=must_be_file,
            must_be_dir=must_be_dir,
            must_be_readable=must_be_readable,
            must_be_writable=must_be_writable,
            create_if_missing=create_if_missing,
        )
        return self.add_validator(field_name, validator, path_value)

    def add_directory_validation(
        self,
        field_name: str,
        dir_value: Any,
        must_exist: bool = True,
        create_if_missing: bool = False,
        must_be_writable: bool = False,
        min_free_space_mb: Optional[int] = None,
    ) -> "ValidationPipeline":
        """
        Convenience method to add directory validation.

        Returns:
            Self for method chaining
        """
        from .path import DirectoryValidator

        validator = DirectoryValidator(
            field_name=field_name,
            must_exist=must_exist,
            create_if_missing=create_if_missing,
            must_be_writable=must_be_writable,
            min_free_space_mb=min_free_space_mb,
        )
        return self.add_validator(field_name, validator, dir_value)

    def add_file_validation(
        self,
        field_name: str,
        file_value: Any,
        must_exist: bool = True,
        allowed_extensions: Optional[list] = None,
        max_size_mb: Optional[int] = None,
    ) -> "ValidationPipeline":
        """
        Convenience method to add file validation.

        Returns:
            Self for method chaining
        """
        from .path import FileValidator

        validator = FileValidator(
            field_name=field_name,
            must_exist=must_exist,
            allowed_extensions=allowed_extensions,
            max_size_mb=max_size_mb,
        )
        return self.add_validator(field_name, validator, file_value)

    def add_executable_validation(
        self, field_name: str, executable_value: Any
    ) -> "ValidationPipeline":
        """
        Convenience method to add executable validation.

        Returns:
            Self for method chaining
        """
        from .permission import ExecutableValidator

        validator = ExecutableValidator(field_name=field_name)
        return self.add_validator(field_name, validator, executable_value)

    def validate(self, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Run all validators in the pipeline.

        Args:
            context: Optional context data shared across validators

        Returns:
            Combined validation result
        """
        overall_result = ValidationResult.success()

        for field_name, validator, value in self.validators:
            try:
                result = validator.validate(value, context)
                overall_result = overall_result.merge(result)

                # Stop on first error if fail_fast is enabled
                if self.fail_fast and not result.is_valid:
                    break

            except Exception as e:
                # Catch any unexpected errors in validators
                error = ValidationError(
                    f"Validator error for '{field_name}': {e}",
                    field=field_name,
                    value=value,
                )
                overall_result.add_error(error)

                if self.fail_fast:
                    break

        return overall_result

    def validate_and_raise(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Run validation and raise ValidationError if any validation fails.

        Args:
            context: Optional context data shared across validators

        Raises:
            ValidationError: If any validation fails
        """
        result = self.validate(context)

        if not result.is_valid:
            # Create a summary error message
            error_messages = [str(error) for error in result.errors]
            summary = (
                f"{self.name} failed with {len(result.errors)} error(s): "
                + "; ".join(error_messages)
            )
            raise ValidationError(summary)

    def clear(self) -> "ValidationPipeline":
        """
        Clear all validators from the pipeline.

        Returns:
            Self for method chaining
        """
        self.validators.clear()
        return self


class ValidationStepBuilder:
    """
    Builder for creating validation steps with fluent interface.

    Helps reduce complexity when building complex validation scenarios.
    """

    def __init__(self):
        self.pipeline = ValidationPipeline()

    def validate_input_directory(
        self,
        path: Any,
        field_name: str = "input_directory",
        create_if_missing: bool = False,
    ) -> "ValidationStepBuilder":
        """Add input directory validation step."""
        self.pipeline.add_directory_validation(
            field_name=field_name,
            dir_value=path,
            must_exist=True,
            must_be_readable=True,
            create_if_missing=create_if_missing,
        )
        return self

    def validate_output_directory(
        self,
        path: Any,
        field_name: str = "output_directory",
        min_free_space_mb: Optional[int] = 100,
    ) -> "ValidationStepBuilder":
        """Add output directory validation step."""
        self.pipeline.add_directory_validation(
            field_name=field_name,
            dir_value=path,
            must_exist=False,
            create_if_missing=True,
            must_be_writable=True,
            min_free_space_mb=min_free_space_mb,
        )
        return self

    def validate_executable(
        self, path: Any, field_name: str = "executable"
    ) -> "ValidationStepBuilder":
        """Add executable validation step."""
        self.pipeline.add_executable_validation(
            field_name=field_name, executable_value=path
        )
        return self

    def validate_input_file(
        self,
        path: Any,
        field_name: str = "input_file",
        allowed_extensions: Optional[list] = None,
        max_size_mb: Optional[int] = None,
    ) -> "ValidationStepBuilder":
        """Add input file validation step."""
        self.pipeline.add_file_validation(
            field_name=field_name,
            file_value=path,
            must_exist=True,
            allowed_extensions=allowed_extensions,
            max_size_mb=max_size_mb,
        )
        return self

    def validate_custom(
        self, field_name: str, validator: ValidatorBase, value: Any
    ) -> "ValidationStepBuilder":
        """Add custom validator."""
        self.pipeline.add_validator(field_name, validator, value)
        return self

    def build(self) -> ValidationPipeline:
        """Build and return the validation pipeline."""
        return self.pipeline

    def validate(self, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Build pipeline and run validation."""
        return self.pipeline.validate(context)

    def validate_and_raise(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Build pipeline and run validation, raising on failure."""
        return self.pipeline.validate_and_raise(context)
