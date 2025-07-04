"""Security utilities for GOES_VFI application.

This module provides security validation and sanitization functions
to prevent common vulnerabilities like command injection and path traversal.
"""

import os
import pathlib
import re
from typing import Any

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class SecurityError(Exception):  # pylint: disable=too-few-public-methods
    """Raised when a security validation fails."""


class InputValidator:
    """Validates and sanitizes user inputs to prevent security vulnerabilities."""

    # Allowed file extensions for different purposes
    ALLOWED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"]
    ALLOWED_VIDEO_EXTENSIONS = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    ALLOWED_CONFIG_EXTENSIONS = [".toml", ".json", ".yaml", ".yml"]

    # Allowed FFmpeg encoders (whitelist approach)
    ALLOWED_FFMPEG_ENCODERS = [
        "Software x265",
        "Software x264",
        "Hardware HEVC (VideoToolbox)",
        "Hardware H.264 (VideoToolbox)",
        "None (copy original)",
        "Hardware HEVC (NVENC)",
        "Hardware H.264 (NVENC)",
        "Hardware HEVC (QSV)",
        "Hardware H.264 (QSV)",
    ]

    # Allowed Sanchez arguments with validation patterns
    ALLOWED_SANCHEZ_ARGS = {
        "res_km": r"^\d+(\.\d+)?$",
        "false_colour": r"^(true|false)$",
        "crop": r"^[\d,]+$",
        "timestamp": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        "output": r"^[\w\-./]+$",
        "interpolate": r"^(true|false)$",
        "brightness": r"^[+-]?\d+(\.\d+)?$",
        "contrast": r"^[+-]?\d+(\.\d+)?$",
        "saturation": r"^[+-]?\d+(\.\d+)?$",
    }

    @staticmethod
    def validate_file_path(
        path: str,
        allowed_extensions: list[str] | None = None,
        must_exist: bool = False,
    ) -> bool:
        """Validate file path to prevent directory traversal and ensure safety.

        Args:
            path: File path to validate
            allowed_extensions: List of allowed file extensions (e.g., ['.png', '.jpg'])
            must_exist: If True, file must exist on filesystem

        Returns:
            True if path is valid and safe

        Raises:
            SecurityError: If path contains security issues
        """
        if not path or not isinstance(path, str):
            msg = "Path must be a non-empty string"
            raise SecurityError(msg)

        # Normalize path and resolve any symlinks
        try:
            normalized = os.path.normpath(os.path.abspath(path))
        except (OSError, ValueError) as e:
            msg = f"Invalid path format: {e}"
            raise SecurityError(msg) from e

        # Check for directory traversal attempts
        if ".." in path or (path.startswith("/") and not os.path.isabs(path)):
            msg = "Path contains directory traversal attempts"
            raise SecurityError(msg)

        # Validate extension if specified
        if allowed_extensions:
            _, ext = os.path.splitext(normalized)
            if ext.lower() not in [e.lower() for e in allowed_extensions]:
                msg = f"File extension '{ext}' not allowed. Allowed: {allowed_extensions}"
                raise SecurityError(msg)

        # Check if file exists if required
        if must_exist and not os.path.exists(normalized):
            msg = f"File does not exist: {normalized}"
            raise SecurityError(msg)

        # Check if path is within reasonable bounds (prevent extremely long paths)
        if len(normalized) > 4096:  # Most filesystems have much shorter limits
            msg = "Path too long"
            raise SecurityError(msg)

        LOGGER.debug("Path validation passed: %s", normalized)
        return True

    @staticmethod
    def validate_numeric_range(value: float, min_val: float, max_val: float, name: str = "value") -> bool:
        """Validate that a numeric value is within acceptable bounds.

        Args:
            value: Numeric value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            name: Name of the value for error messages

        Returns:
            True if value is within range

        Raises:
            SecurityError: If value is out of range
        """
        # Check for invalid types (including booleans which are subclass of int)
        if not isinstance(value, int | float) or isinstance(value, bool):
            msg = f"{name} must be a number"
            raise SecurityError(msg)

        # Check for infinity and NaN values
        import math
        if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
            msg = f"{name} must be a number"
            raise SecurityError(msg)

        if not min_val <= value <= max_val:
            msg = f"{name} must be between {min_val} and {max_val}, got {value}"
            raise SecurityError(msg)

        return True

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename by removing/replacing dangerous characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for filesystem use
        """
        if not filename:
            return "untitled"

        # Remove/replace dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)

        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip(". ")

        # Ensure filename isn't empty after sanitization
        if not sanitized:
            sanitized = "untitled"

        # Handle Windows reserved names
        windows_reserved = [
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
        ]
        
        # Check if the base name (without extension) is a reserved name
        name_part, ext_part = os.path.splitext(sanitized)
        if name_part.upper() in windows_reserved:
            sanitized = name_part + "_" + ext_part

        # Limit length
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            max_name_len = 255 - len(ext)
            sanitized = name[:max_name_len] + ext

        return sanitized

    @staticmethod
    def validate_ffmpeg_encoder(encoder: str) -> bool:
        """Validate that FFmpeg encoder is from allowed list.

        Args:
            encoder: Encoder name to validate

        Returns:
            True if encoder is allowed

        Raises:
            SecurityError: If encoder is not in whitelist
        """
        if encoder not in InputValidator.ALLOWED_FFMPEG_ENCODERS:
            msg = f"FFmpeg encoder '{encoder}' not allowed. Allowed: {InputValidator.ALLOWED_FFMPEG_ENCODERS}"
            raise SecurityError(msg)
        return True

    @staticmethod
    def validate_sanchez_argument(key: str, value: Any) -> bool:
        """Validate Sanchez processor arguments to prevent command injection.

        Args:
            key: Argument name
            value: Argument value

        Returns:
            True if argument is valid

        Raises:
            SecurityError: If argument is invalid or potentially dangerous
        """
        if key not in InputValidator.ALLOWED_SANCHEZ_ARGS:
            msg = f"Sanchez argument '{key}' not allowed"
            raise SecurityError(msg)

        pattern = InputValidator.ALLOWED_SANCHEZ_ARGS[key]
        if not re.match(pattern, str(value)):
            msg = f"Sanchez argument '{key}' has invalid value: {value}"
            raise SecurityError(msg)

        return True

    @staticmethod
    def validate_command_args(args: list[str], max_args: int = 100) -> bool:
        """Validate command line arguments for subprocess execution.

        Args:
            args: List of command arguments
            max_args: Maximum number of arguments allowed

        Returns:
            True if arguments are safe

        Raises:
            SecurityError: If arguments contain dangerous patterns
        """
        if len(args) > max_args:
            msg = f"Too many command arguments: {len(args)} > {max_args}"
            raise SecurityError(msg)

        # Check for dangerous patterns in arguments
        dangerous_patterns = [
            r"[;&|`$()]",  # Shell metacharacters
            r"\\x[0-9a-fA-F]{2}",  # Hex escape sequences
            r"%[0-9a-fA-F]{2}",  # URL encoding
        ]

        for arg in args:
            if not isinstance(arg, str):
                msg = f"Command argument must be string, got {type(arg)}"
                raise SecurityError(msg)

            for pattern in dangerous_patterns:
                if re.search(pattern, arg):
                    msg = f"Dangerous pattern found in argument: {arg}"
                    raise SecurityError(msg)

        return True


class SecureFileHandler:
    """Handles file operations with security considerations."""

    @staticmethod
    def create_secure_temp_file(suffix: str = "", prefix: str = "goesvfi_") -> pathlib.Path:
        """Create a temporary file with secure permissions.

        Args:
            suffix: File suffix/extension
            prefix: File prefix

        Returns:
            Path to created temporary file
        """
        import tempfile

        # Create temporary file with restrictive permissions
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        temp_path = pathlib.Path(path)

        # Set restrictive permissions (owner only)
        temp_path.chmod(0o600)

        # Close the file descriptor (we just need the path)
        os.close(fd)

        LOGGER.debug("Created secure temporary file: %s", temp_path)
        return temp_path

    @staticmethod
    def create_secure_config_dir(config_dir: pathlib.Path) -> None:
        """Create configuration directory with secure permissions.

        Args:
            config_dir: Path to configuration directory
        """
        config_dir.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions (owner only)
        config_dir.chmod(0o700)

        LOGGER.info("Created secure config directory: %s", config_dir)


def secure_subprocess_call(command: list[str], **kwargs: Any) -> Any:
    """Execute subprocess with security validations.

    Args:
        command: Command and arguments to execute
        **kwargs: Additional arguments for subprocess.run

    Returns:
        Result from subprocess.run

    Raises:
        SecurityError: If command fails security validation
    """
    import subprocess

    # Validate command arguments
    InputValidator.validate_command_args(command)

    # Set secure defaults
    secure_kwargs = {
        "shell": False,  # Never use shell
        "check": True,
        "capture_output": True,
        "text": True,
        "timeout": kwargs.get("timeout", 300),  # 5 minute default timeout
    }

    # Override with user-provided kwargs
    secure_kwargs.update(kwargs)

    # Ensure shell is never enabled
    if secure_kwargs.get("shell"):
        msg = "Shell execution not allowed for security reasons"
        raise SecurityError(msg)

    LOGGER.info("Executing secure subprocess: %s with %s args", command[0], len(command) - 1)

    try:
        return subprocess.run(command, **secure_kwargs)
    except subprocess.TimeoutExpired as e:
        msg = f"Command timed out after {secure_kwargs['timeout']} seconds"
        raise SecurityError(msg) from e
    except Exception as e:
        LOGGER.exception("Subprocess execution failed: %s", e)
        raise
