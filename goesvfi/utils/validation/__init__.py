"""
Validation framework for reducing complexity in validation-heavy functions.

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
        raise ValueError(f"{field_name} is required")

    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(f"{field_name} does not exist: {p}")

    if must_be_dir and not p.is_dir():
        raise NotADirectoryError(f"{field_name} is not a directory: {p}")

    if must_be_file and not p.is_file():
        raise FileNotFoundError(f"{field_name} is not a file: {p}")

    return p


def validate_positive_int(value: Any, field_name: str = "value") -> int:
    """Validate that ``value`` is a positive integer."""

    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int")

    if value <= 0:
        raise ValueError(f"{field_name} must be positive, got {value}")

    return value


__all__ = [
    "ValidationError",
    "ValidationResult",
    "ValidatorBase",
    "PathValidator",
    "PermissionValidator",
    "ValidationPipeline",
    "validate_path_exists",
    "validate_positive_int",
]
