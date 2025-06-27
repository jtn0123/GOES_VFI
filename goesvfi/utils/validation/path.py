"""Path validation utilities.

Reduces complexity in functions that perform extensive file/directory validation.
"""

import os
from pathlib import Path
from typing import Any

from .base import ValidationResult, ValidatorBase


class PathValidator(ValidatorBase):
    """Validator for file and directory paths."""

    def __init__(
        self,
        field_name: str | None = None,
        must_exist: bool = True,
        must_be_file: bool = False,
        must_be_dir: bool = False,
        must_be_readable: bool = False,
        must_be_writable: bool = False,
        allowed_extensions: list | None = None,
        create_if_missing: bool = False,
    ) -> None:
        super().__init__(field_name)
        self.must_exist = must_exist
        self.must_be_file = must_be_file
        self.must_be_dir = must_be_dir
        self.must_be_readable = must_be_readable
        self.must_be_writable = must_be_writable
        self.allowed_extensions = allowed_extensions or []
        self.create_if_missing = create_if_missing

    def validate(self, value: Any, context: dict[str, Any] | None = None) -> ValidationResult:
        """Validate a path value."""
        # Basic validation
        path_result = self._validate_path_input(value)
        if not path_result.is_valid:
            return path_result

        path = Path(value) if isinstance(value, str) else value
        result = ValidationResult.success()

        # Existence checks
        existence_result = self._check_path_existence(path, value)
        result = result.merge(existence_result)
        if not existence_result.is_valid:
            return result

        # Skip further checks if path doesn't exist and that's okay
        if not path.exists() and not self.must_exist:
            return result

        # Type and permission checks
        type_result = self._check_path_type(path, value)
        permission_result = self._check_path_permissions(path, value)
        extension_result = self._check_file_extensions(path, value)

        return result.merge(type_result).merge(permission_result).merge(extension_result)

    def _validate_path_input(self, value: Any) -> ValidationResult:
        """Validate the input value can be converted to a Path."""
        if value is None:
            return ValidationResult.failure(self._create_error("Path cannot be None", value))

        try:
            if isinstance(value, str | Path):
                return ValidationResult.success()

            return ValidationResult.failure(
                self._create_error(f"Path must be string or Path object, got {type(value)}", value)
            )
        except Exception as e:
            return ValidationResult.failure(self._create_error(f"Invalid path format: {e}", value))

    def _check_path_existence(self, path: Path, value: Any) -> ValidationResult:
        """Check path existence and create if needed."""
        result = ValidationResult.success()

        if self.must_exist and not path.exists():
            if self.create_if_missing:
                return self._create_missing_path(path, value)
            result.add_error(self._create_error(f"Path does not exist: {path}", value))

        return result

    def _create_missing_path(self, path: Path, value: Any) -> ValidationResult:
        """Create missing path if configured to do so."""
        result = ValidationResult.success()

        try:
            if self.must_be_dir:
                path.mkdir(parents=True, exist_ok=True)
                result.add_warning(f"Created directory: {path}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                result.add_warning(f"Created parent directory: {path.parent}")
        except Exception as e:
            result.add_error(self._create_error(f"Could not create path {path}: {e}", value))

        return result

    def _check_path_type(self, path: Path, value: Any) -> ValidationResult:
        """Check if path is the correct type (file vs directory)."""
        result = ValidationResult.success()

        if self.must_be_file and not path.is_file():
            result.add_error(self._create_error(f"Path must be a file: {path}", value))

        if self.must_be_dir and not path.is_dir():
            result.add_error(self._create_error(f"Path must be a directory: {path}", value))

        return result

    def _check_path_permissions(self, path: Path, value: Any) -> ValidationResult:
        """Check path permissions."""
        result = ValidationResult.success()

        if self.must_be_readable and not os.access(path, os.R_OK):
            result.add_error(self._create_error(f"Path is not readable: {path}", value))

        if self.must_be_writable and not os.access(path, os.W_OK):
            result.add_error(self._create_error(f"Path is not writable: {path}", value))

        return result

    def _check_file_extensions(self, path: Path, value: Any) -> ValidationResult:
        """Check file extensions if configured."""
        result = ValidationResult.success()

        if self.allowed_extensions and path.is_file():
            extension = path.suffix.lower()
            if extension not in self.allowed_extensions:
                result.add_error(
                    self._create_error(
                        f"File extension '{extension}' not allowed. Allowed: {self.allowed_extensions}",
                        value,
                    )
                )

        return result


class DirectoryValidator(PathValidator):
    """Specialized validator for directories."""

    def __init__(
        self,
        field_name: str | None = None,
        must_exist: bool = True,
        must_be_readable: bool = True,
        must_be_writable: bool = False,
        create_if_missing: bool = False,
        min_free_space_mb: int | None = None,
    ) -> None:
        super().__init__(
            field_name=field_name,
            must_exist=must_exist,
            must_be_dir=True,
            must_be_readable=must_be_readable,
            must_be_writable=must_be_writable,
            create_if_missing=create_if_missing,
        )
        self.min_free_space_mb = min_free_space_mb

    def validate(self, value: Any, context: dict[str, Any] | None = None) -> ValidationResult:
        """Validate directory with additional directory-specific checks."""
        result = super().validate(value, context)

        if not result.is_valid:
            return result

        path = Path(value) if isinstance(value, str) else value

        # Check free space if required
        if self.min_free_space_mb and path.exists():
            try:
                import shutil

                free_space = shutil.disk_usage(path).free
                free_space_mb = free_space / (1024 * 1024)

                if free_space_mb < self.min_free_space_mb:
                    result.add_error(
                        self._create_error(
                            f"Insufficient free space: {free_space_mb:.1f}MB available, "
                            f"{self.min_free_space_mb}MB required",
                            value,
                        )
                    )
            except Exception as e:
                result.add_warning(f"Could not check free space: {e}")

        return result


class FileValidator(PathValidator):
    """Specialized validator for files."""

    def __init__(
        self,
        field_name: str | None = None,
        must_exist: bool = True,
        must_be_readable: bool = True,
        allowed_extensions: list | None = None,
        max_size_mb: int | None = None,
        min_size_bytes: int = 0,
    ) -> None:
        super().__init__(
            field_name=field_name,
            must_exist=must_exist,
            must_be_file=True,
            must_be_readable=must_be_readable,
            allowed_extensions=allowed_extensions,
        )
        self.max_size_mb = max_size_mb
        self.min_size_bytes = min_size_bytes

    def validate(self, value: Any, context: dict[str, Any] | None = None) -> ValidationResult:
        """Validate file with additional file-specific checks."""
        result = super().validate(value, context)

        if not result.is_valid:
            return result

        path = Path(value) if isinstance(value, str) else value

        # Check file size if it exists
        if path.exists() and path.is_file():
            try:
                file_size = path.stat().st_size

                if file_size < self.min_size_bytes:
                    result.add_error(
                        self._create_error(
                            f"File too small: {file_size} bytes, minimum {self.min_size_bytes} bytes",
                            value,
                        )
                    )

                if self.max_size_mb:
                    max_size_bytes = self.max_size_mb * 1024 * 1024
                    if file_size > max_size_bytes:
                        result.add_error(
                            self._create_error(
                                f"File too large: {file_size / (1024 * 1024):.1f}MB, maximum {self.max_size_mb}MB",
                                value,
                            )
                        )
            except Exception as e:
                result.add_warning(f"Could not check file size: {e}")

        return result
