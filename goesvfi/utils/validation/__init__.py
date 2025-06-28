"""Validation framework for reducing complexity in validation-heavy functions.

This module provides composable validation utilities that help reduce the complexity
of functions with extensive parameter validation and safety checking.
"""

from pathlib import Path
from typing import Any

from .base import ValidationError, ValidationResult, ValidatorBase
from .path import PathValidator
from .permission import PermissionValidator
from .pipeline import ValidationPipeline


def validate_path_exists(
    path: Path | str | None,
    *,
    must_be_dir: bool = False,
    must_be_file: bool = False,
    field_name: str = "path",
) -> Path:
    """Validate that a path exists and optionally enforce type."""
    if path is None:
        msg = f"{field_name} is required"
        raise ValueError(msg)

    p = Path(path)

    if not p.exists():
        msg = f"{field_name} does not exist: {p}"
        raise FileNotFoundError(msg)

    if must_be_dir and not p.is_dir():
        msg = f"{field_name} is not a directory: {p}"
        raise NotADirectoryError(msg)

    if must_be_file and not p.is_file():
        msg = f"{field_name} is not a file: {p}"
        raise FileNotFoundError(msg)

    return p


def validate_positive_int(value: Any, field_name: str = "value") -> int:
    """Validate that ``value`` is a positive integer."""
    if not isinstance(value, int):
        msg = f"{field_name} must be an int"
        raise TypeError(msg)

    if value <= 0:
        msg = f"{field_name} must be positive, got {value}"
        raise ValueError(msg)

    return value


__all__ = [
    "PathValidator",
    "PermissionValidator",
    "ValidationError",
    "ValidationPipeline",
    "ValidationResult",
    "ValidatorBase",
    "validate_path_exists",
    "validate_positive_int",
]
