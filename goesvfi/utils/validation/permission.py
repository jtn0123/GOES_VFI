"""
Permission validation utilities.

Reduces complexity in functions that check file permissions and access rights.
"""

import os
import stat
from pathlib import Path
from typing import Any, Dict, Optional

from .base import ValidationResult, ValidatorBase


class PermissionValidator(ValidatorBase):
    """Validator for file/directory permissions and access rights."""

    def __init__(
        self,
        field_name: Optional[str] = None,
        check_read: bool = False,
        check_write: bool = False,
        check_execute: bool = False,
        check_owner_read: bool = False,
        check_owner_write: bool = False,
        check_owner_execute: bool = False,
        check_group_read: bool = False,
        check_group_write: bool = False,
        check_group_execute: bool = False,
        check_other_read: bool = False,
        check_other_write: bool = False,
        check_other_execute: bool = False,
    ):
        super().__init__(field_name)
        self.check_read = check_read
        self.check_write = check_write
        self.check_execute = check_execute
        self.check_owner_read = check_owner_read
        self.check_owner_write = check_owner_write
        self.check_owner_execute = check_owner_execute
        self.check_group_read = check_group_read
        self.check_group_write = check_group_write
        self.check_group_execute = check_group_execute
        self.check_other_read = check_other_read
        self.check_other_write = check_other_write
        self.check_other_execute = check_other_execute

    def validate(
        self, value: Any, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate permissions for a path."""
        # Basic validation
        path_result = self._validate_path_input(value)
        if not path_result.is_valid:
            return path_result
        
        path = Path(value) if isinstance(value, str) else value
        
        if not path.exists():
            return ValidationResult.failure(
                self._create_error(f"Path does not exist: {path}", value)
            )
        
        result = ValidationResult.success()
        
        # Check basic and detailed permissions
        basic_result = self._check_basic_permissions(path, value)
        detailed_result = self._check_detailed_permissions(path, value)
        
        return result.merge(basic_result).merge(detailed_result)
    
    def _validate_path_input(self, value: Any) -> ValidationResult:
        """Validate the input path value."""
        if value is None:
            return ValidationResult.failure(
                self._create_error("Path cannot be None", value)
            )
        
        try:
            Path(value) if isinstance(value, str) else value
            return ValidationResult.success()
        except Exception as e:
            return ValidationResult.failure(
                self._create_error(f"Invalid path: {e}", value)
            )
    
    def _check_basic_permissions(self, path: Path, value: Any) -> ValidationResult:
        """Check basic access permissions (read, write, execute)."""
        result = ValidationResult.success()
        
        if self.check_read and not os.access(path, os.R_OK):
            result.add_error(
                self._create_error(f"No read permission for: {path}", value)
            )
        
        if self.check_write and not os.access(path, os.W_OK):
            result.add_error(
                self._create_error(f"No write permission for: {path}", value)
            )
        
        if self.check_execute and not os.access(path, os.X_OK):
            result.add_error(
                self._create_error(f"No execute permission for: {path}", value)
            )
        
        return result
    
    def _check_detailed_permissions(self, path: Path, value: Any) -> ValidationResult:
        """Check detailed permissions using stat."""
        result = ValidationResult.success()
        
        try:
            file_stat = path.stat()
            mode = file_stat.st_mode
            
            # Check owner, group, and other permissions
            owner_result = self._check_owner_permissions(mode, path, value)
            group_result = self._check_group_permissions(mode, path, value)
            other_result = self._check_other_permissions(mode, path, value)
            
            result = result.merge(owner_result).merge(group_result).merge(other_result)
            
        except Exception as e:
            result.add_warning(f"Could not check detailed permissions: {e}")
        
        return result
    
    def _check_owner_permissions(self, mode: int, path: Path, value: Any) -> ValidationResult:
        """Check owner permissions."""
        result = ValidationResult.success()
        
        if self.check_owner_read and not (mode & stat.S_IRUSR):
            result.add_error(
                self._create_error(f"No owner read permission for: {path}", value)
            )
        
        if self.check_owner_write and not (mode & stat.S_IWUSR):
            result.add_error(
                self._create_error(f"No owner write permission for: {path}", value)
            )
        
        if self.check_owner_execute and not (mode & stat.S_IXUSR):
            result.add_error(
                self._create_error(f"No owner execute permission for: {path}", value)
            )
        
        return result
    
    def _check_group_permissions(self, mode: int, path: Path, value: Any) -> ValidationResult:
        """Check group permissions."""
        result = ValidationResult.success()
        
        if self.check_group_read and not (mode & stat.S_IRGRP):
            result.add_error(
                self._create_error(f"No group read permission for: {path}", value)
            )
        
        if self.check_group_write and not (mode & stat.S_IWGRP):
            result.add_error(
                self._create_error(f"No group write permission for: {path}", value)
            )
        
        if self.check_group_execute and not (mode & stat.S_IXGRP):
            result.add_error(
                self._create_error(f"No group execute permission for: {path}", value)
            )
        
        return result
    
    def _check_other_permissions(self, mode: int, path: Path, value: Any) -> ValidationResult:
        """Check other permissions."""
        result = ValidationResult.success()
        
        if self.check_other_read and not (mode & stat.S_IROTH):
            result.add_error(
                self._create_error(f"No other read permission for: {path}", value)
            )
        
        if self.check_other_write and not (mode & stat.S_IWOTH):
            result.add_error(
                self._create_error(f"No other write permission for: {path}", value)
            )
        
        if self.check_other_execute and not (mode & stat.S_IXOTH):
            result.add_error(
                self._create_error(f"No other execute permission for: {path}", value)
            )
        
        return result


class ExecutableValidator(ValidatorBase):
    """Validator specifically for executable files."""

    def __init__(self, field_name: Optional[str] = None):
        super().__init__(field_name)

    def validate(
        self, value: Any, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate that a file is executable."""
        if value is None:
            return ValidationResult.failure(
                self._create_error("Executable path cannot be None", value)
            )

        try:
            path = Path(value) if isinstance(value, str) else value
        except Exception as e:
            return ValidationResult.failure(
                self._create_error(f"Invalid executable path: {e}", value)
            )

        result = ValidationResult.success()

        if not path.exists():
            result.add_error(
                self._create_error(f"Executable does not exist: {path}", value)
            )
            return result

        if not path.is_file():
            result.add_error(
                self._create_error(f"Executable must be a file: {path}", value)
            )

        if not os.access(path, os.X_OK):
            result.add_error(
                self._create_error(f"File is not executable: {path}", value)
            )

        return result


class WritableDirectoryValidator(ValidatorBase):
    """Validator for writable directories with specific requirements."""

    def __init__(
        self,
        field_name: Optional[str] = None,
        create_if_missing: bool = True,
        min_free_space_mb: Optional[int] = None,
    ):
        super().__init__(field_name)
        self.create_if_missing = create_if_missing
        self.min_free_space_mb = min_free_space_mb

    def validate(
        self, value: Any, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate a writable directory."""
        if value is None:
            return ValidationResult.failure(
                self._create_error("Directory path cannot be None", value)
            )

        try:
            path = Path(value) if isinstance(value, str) else value
        except Exception as e:
            return ValidationResult.failure(
                self._create_error(f"Invalid directory path: {e}", value)
            )

        result = ValidationResult.success()

        # Create directory if it doesn't exist
        if not path.exists():
            if self.create_if_missing:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    result.add_warning(f"Created directory: {path}")
                except Exception as e:
                    result.add_error(
                        self._create_error(
                            f"Could not create directory {path}: {e}", value
                        )
                    )
                    return result
            else:
                result.add_error(
                    self._create_error(f"Directory does not exist: {path}", value)
                )
                return result

        # Check it's actually a directory
        if not path.is_dir():
            result.add_error(
                self._create_error(f"Path is not a directory: {path}", value)
            )
            return result

        # Check write permissions
        if not os.access(path, os.W_OK):
            result.add_error(
                self._create_error(f"Directory is not writable: {path}", value)
            )

        # Check free space if required
        if self.min_free_space_mb:
            try:
                import shutil

                free_space = shutil.disk_usage(path).free
                free_space_mb = free_space / (1024 * 1024)

                if free_space_mb < self.min_free_space_mb:
                    result.add_error(
                        self._create_error(
                            f"Insufficient free space in {path}: {free_space_mb:.1f}MB available, "
                            f"{self.min_free_space_mb}MB required",
                            value,
                        )
                    )
            except Exception as e:
                result.add_warning(f"Could not check free space: {e}")

        return result
